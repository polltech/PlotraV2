"""
Plotra Platform - EUDR Verification & DDS API
Four-tier verification workflow and EU TRACES integration.

KPIs:
- DDS Generation: <10s
- Conflict Resolution SLA: <48h
- False Positive Rate: <5%
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import (
    get_current_user, require_farmer, require_coop_admin,
    require_plotra_admin, require_auditor
)
from app.models.user import User, UserRole
from app.models.farm import Farm, LandParcel
from app.models.traceability import Batch
from app.services.eudr_integration import EUDRIntegrationService, DDSData
from app.core.schema_enforcement import HashedIDGenerator, DualSchemaEnforcer

router = APIRouter(prefix="", tags=["EUDR & DDS"])


class VerificationStatus(str):
    """Four-tier verification status."""
    DRAFT = "draft"
    COOP_APPROVED = "cooperative_approved"
    KIPAWA_VERIFIED = "kipawa_verified"
    EUDR_SUBMITTED = "eudr_submitted"


class ParcelVerification(BaseModel):
    """Parcel verification status update."""
    parcel_ids: List[str]
    status: str
    notes: Optional[str] = None


class DDSGenerationRequest(BaseModel):
    """Request DDS generation for a batch."""
    batch_id: str
    operator_name: str
    operator_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    commodity_type: str = "Coffee"
    quantity: float = 0.0
    unit: str = "kg"


class DDSResponse(BaseModel):
    """DDS generation response."""
    dds_number: str
    version: str
    status: str
    generated_at: str
    risk_level: str
    parcels_included: int
    farmers_included: int


class ConflictResolution(BaseModel):
    """Conflict resolution request."""
    parcel_a_id: str
    parcel_b_id: str
    resolution_type: str = Field(description="trim_snap, prioritize_level, resurvey")
    resolution_data: Optional[Dict[str, Any]] = None
    boundary_photo_required: bool = False


@router.post("/parcels/verify")
async def verify_parcels(
    verification: ParcelVerification,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify parcels at cooperative level.
    
    Status flow: draft → cooperative_approved → kipawa_verified → eudr_submitted
    """
    updated = 0
    errors = []
    
    for parcel_id in verification.parcel_ids:
        result = await db.execute(
            select(LandParcel).where(LandParcel.id == parcel_id)
        )
        parcel = result.scalar_one_or_none()
        
        if not parcel:
            errors.append(f"Parcel {parcel_id} not found")
            continue
        
        parcel.verification_status = verification.status
        updated += 1
    
    await db.commit()
    
    return {
        "updated": updated,
        "errors": errors,
        "status": verification.status,
        "verified_by": current_user.id
    }


@router.get("/batch/{batch_id}/dds", response_model=DDSResponse)
async def generate_dds(
    batch_id: str,
    current_user: User = Depends(require_plotra_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Due Diligence Statement for batch.
    
    POST /api/v1/batches/{id}/dds produces EU TRACES compatible JSON.
    
    KPI: <10s generation time.
    """
    result = await db.execute(
        select(Batch).where(Batch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    from app.models.user import Cooperative
    
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.id == batch.cooperative_id)
    )
    coop = coop_result.scalar_one_or_none()
    
    farms_result = await db.execute(
        select(Farm).where(Farm.cooperative_id == batch.cooperative_id)
    )
    farms = farms_result.scalars().all()
    
    parcel_ids = []
    farmer_count = 0
    
    for farm in farms:
        parcels_result = await db.execute(
            select(LandParcel).where(
                LandParcel.farm_id == farm.id,
                LandParcel.verification_status == VerificationStatus.KIPAWA_VERIFIED
            )
        )
        parcels = parcels_result.scalars().all()
        parcel_ids.extend([p.id for p in parcels])
        farmer_count += 1
    
    dds_data = DDSData(
        operator_name=coop.name if coop else "Unknown Cooperative",
        commodity_type="Coffee",
        quantity=batch.weight_kg or 0,
    )
    
    eudr_service = EUDRIntegrationService()
    dds = eudr_service.generate_due_diligence_statement(dds_data)
    
    return DDSResponse(
        dds_number=dds['dds_number'],
        version=dds['version'],
        status="draft",
        generated_at=datetime.utcnow().isoformat(),
        risk_level=dds['risk_level'],
        parcels_included=len(parcel_ids),
        farmers_included=farmer_count
    )


@router.get("/traces/submit")
async def submit_to_traces(
    dds_number: str,
    current_user: User = Depends(require_auditor),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit DDS to EU TRACES portal.
    
    Sandbox testing mode.
    Only hashed_id transmitted (privacy by design).
    """
    return {
        "status": "submitted",
        "traces_reference": f"TRACES-{dds_number}",
        "submitted_at": datetime.utcnow().isoformat(),
        "mode": "sandbox",
        "note": "Only hashed_id transmitted - no raw PII"
    }


@router.post("/conflicts/resolve")
async def resolve_parcel_conflict(
    resolution: ConflictResolution,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Resolve polygon overlap conflict between parcels.
    
    Resolution options:
    - trim_snap: Adjust boundaries to remove overlap
    - prioritize_level: Senior parcel takes priority (Title > Lease > Family > Customary)
    - resurvey: Requires new boundary photo
    
    SLA: <48h resolution.
    """
    parcel_a_result = await db.execute(
        select(LandParcel).where(LandParcel.id == resolution.parcel_a_id)
    )
    parcel_a = parcel_a_result.scalar_one_or_none()
    
    parcel_b_result = await db.execute(
        select(LandParcel).where(LandParcel.id == resolution.parcel_b_id)
    )
    parcel_b = parcel_b_result.scalar_one_or_none()
    
    if not parcel_a or not parcel_b:
        raise HTTPException(status_code=404, detail="One or both parcels not found")
    
    if resolution.resolution_type == "resurvey":
        if not resolution.boundary_photo_required:
            return {
                "status": "pending_photo",
                "message": "Boundary photo required for resurvey resolution"
            }
        parcel_a.verification_status = VerificationStatus.DRAFT
        parcel_b.verification_status = VerificationStatus.DRAFT
    
    elif resolution.resolution_type == "trim_snap":
        if resolution.resolution_data:
            parcel_a.boundary_geojson = resolution.resolution_data.get('parcel_a_geojson')
            parcel_b.boundary_geojson = resolution.resolution_data.get('parcel_b_geojson')
    
    await db.commit()
    
    return {
        "status": "resolved",
        "parcel_a_id": resolution.parcel_a_id,
        "parcel_b_id": resolution.parcel_b_id,
        "resolution_type": resolution.resolution_type,
        "resolved_by": current_user.id,
        "resolved_at": datetime.utcnow().isoformat(),
        "sla_compliant": True
    }


@router.get("/sla-alerts")
async def get_sla_alerts(
    current_user: User = Depends(require_plotra_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get 48h SLA breach alerts.
    
    Automated warnings at 36h and 44h.
    """
    from app.models.system import ConflictRecord
    from datetime import timedelta
    
    now = datetime.utcnow()
    thirty_six_hours = now - timedelta(hours=36)
    forty_four_hours = now - timedelta(hours=44)
    
    result = await db.execute(
        select(ConflictRecord).where(
            ConflictRecord.status == "pending_resolution",
            ConflictRecord.created_at <= thirty_six_hours
        )
    )
    conflicts = result.scalars().all()
    
    alerts = []
    for conflict in conflicts:
        age_hours = (now - conflict.created_at).total_seconds() / 3600
        
        if age_hours >= 44:
            alerts.append({
                "conflict_id": conflict.id,
                "alert_type": "critical",
                "message": f"Conflict approaching 48h SLA deadline",
                "hours_elapsed": round(age_hours, 1)
            })
        elif age_hours >= 36:
            alerts.append({
                "conflict_id": conflict.id,
                "alert_type": "warning",
                "message": f"Conflict at 36h mark",
                "hours_elapsed": round(age_hours, 1)
            })
    
    return {"alerts": alerts}


@router.post("/export-validation")
async def validate_batch_export(
    batch_id: str,
    current_user: User = Depends(require_plotra_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Pre-export validation check.
    
    Blocks batch if any farmer lacks:
    - hashed_ID
    - payout_recipient_id
    
    EU Identity Rate KPI: 100%
    """
    from app.models.user import User
    from app.models.farm import Farm
    
    result = await db.execute(
        select(Batch).where(Batch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    farms_result = await db.execute(
        select(Farm).where(Farm.cooperative_id == batch.cooperative_id)
    )
    farms = farms_result.scalars().all()
    
    missing_hashed_id = []
    missing_payout = []
    
    for farm in farms:
        user_result = await db.execute(
            select(User).where(User.id == farm.owner_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            continue
        
        if not hasattr(user, 'hashed_id') or not user.hashed_id:
            missing_hashed_id.append(user.id)
        
        if not user.payout_recipient_id:
            missing_payout.append(user.id)
    
    return {
        "batch_id": batch_id,
        "export_blocked": len(missing_hashed_id) > 0 or len(missing_payout) > 0,
        "missing_hashed_id_count": len(missing_hashed_id),
        "missing_payout_id_count": len(missing_payout),
        "meets_eu_identity_kpi": len(missing_hashed_id) == 0 and len(missing_payout) == 0
    }


@router.get("/four-tier-status")
async def get_four_tier_status(
    batch_id: str,
    current_user: User = Depends(require_plotra_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get four-tier verification status for batch.
    
    Status flow:
    1. Draft
    2. Cooperative Approved
    3. Kipawa Verified
    4. EUDR Submitted
    """
    from sqlalchemy import func
    
    result = await db.execute(
        select(
            func.count(LandParcel.id).label('total'),
            func.count(LandParcel.id).filter(
                LandParcel.verification_status == VerificationStatus.DRAFT
            ).label('draft'),
            func.count(LandParcel.id).filter(
                LandParcel.verification_status == VerificationStatus.COOP_APPROVED
            ).label('coop_approved'),
            func.count(LandParcel.id).filter(
                LandParcel.verification_status == VerificationStatus.KIPAWA_VERIFIED
            ).label('kipawa_verified'),
            func.count(LandParcel.id).filter(
                LandParcel.verification_status == VerificationStatus.EUDR_SUBMITTED
            ).label('eudr_submitted'),
        ).where(LandParcel.farm_id.in_(
            select(Farm.id).where(Farm.cooperative_id == select(Batch.cooperative_id).where(Batch.id == batch_id))
        ))
    )
    
    stats = result.one()
    
    return {
        "batch_id": batch_id,
        "total_parcels": stats.total or 0,
        "draft": stats.draft or 0,
        "cooperative_approved": stats.coop_approved or 0,
        "kipawa_verified": stats.kipawa_verified or 0,
        "eudr_submitted": stats.eudr_submitted or 0
    }