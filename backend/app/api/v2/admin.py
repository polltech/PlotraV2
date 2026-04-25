"""
Plotra Platform - Admin API Endpoints (Tier 3 & 4)
Satellite analysis, user management, and compliance oversight
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File
from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.auth import get_current_user, require_platform_admin, require_admin
from app.models.user import User, UserRole, UserStatus, VerificationStatus, Cooperative, CooperativeMember
from app.models.farm import Farm, FarmParcel, LandDocument
from app.models.traceability import Batch, Delivery
from app.models.satellite import SatelliteObservation, AnalysisStatus
from app.models.compliance import ComplianceStatus, EUDRCompliance
from app.models.traceability import Batch
from app.services.satellite_analysis import satellite_engine
from app.services.eudr_integration import eudr_service, DDSData, CertificateData
from app.api.schemas import (
    AnalysisRequest, AnalysisResponse, ComplianceChecklist,
    ComplianceResponse, DDSRequest, DDSResponse,
    CertificateRequest, CertificateResponse, MessageResponse,
    CooperativeCreate, CooperativeUpdate, CooperativeResponse, CooperativeWithMembers,
    UserResponse
)

router = APIRouter(tags=["Tier 3: Admin APIs"])


@router.get("/farms")
async def get_all_farms(
    page: int = 1,
    page_size: int = 20,
    status_filter: str = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all farms with pagination and optional status filter."""
    from app.models.user import User as UserModel
    query = select(Farm, UserModel).join(UserModel, Farm.owner_id == UserModel.id, isouter=True).options(selectinload(Farm.parcels))
    if status_filter:
        query = query.where(Farm.verification_status == status_filter)

    count_query = select(func.count()).select_from(Farm)
    if status_filter:
        count_query = count_query.where(Farm.verification_status == status_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Farm.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    farms_out = []
    for farm, owner in rows:
        # Compute centroid from parcels if not set
        centroid_lat = farm.centroid_lat
        centroid_lon = farm.centroid_lon
        if (centroid_lat is None or centroid_lon is None) and farm.parcels:
            first_parcel = farm.parcels[0]
            if first_parcel.boundary_geojson:
                coords = first_parcel.boundary_geojson.get('coordinates', [[]])[0]
                if coords and len(coords) > 0:
                    centroid_lat = sum(c[1] for c in coords) / len(coords)
                    centroid_lon = sum(c[0] for c in coords) / len(coords)
        
        farms_out.append({
            "id": farm.id,
            "farm_name": farm.farm_name,
            "farm_code": farm.farm_code,
            "verification_status": farm.verification_status,
            "compliance_status": farm.compliance_status,
            "total_area_hectares": farm.total_area_hectares,
            "coffee_varieties": farm.coffee_varieties,
            "created_at": farm.created_at,
            "owner_name": f"{owner.first_name} {owner.last_name}" if owner else "Unknown",
            "owner_phone": owner.phone if owner else None,
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon,
        })

    return {
        "farms": farms_out,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/wallet/stats")
async def get_wallet_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get wallet/escrow statistics.
    Platform Admins can access.
    """
    # Calculate total wallet/escrow balance (using user model fields since no PaymentEscrow in this version)
    # Note: This version might not have payment escrow implemented
    return {
        "total_balance": 0,
        "total_transactions": 0,
        "recent_transactions": []
    }


@router.get("/payments")
async def get_payments(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all payments with filtering.
    Platform Admins can access.
    """
    # Note: PaymentEscrow model might not exist in this version
    return {
        "payments": [],
        "total": 0
    }


@router.get("/users")
async def get_all_users(
    role: Optional[str] = None,
    role_filter: Optional[str] = None,
    verification_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all users with filtering and pagination.
    Platform Admins and Auditors can access.
    Accepts both ?role=FARMER and ?role_filter=FARMER for compatibility.
    """
    query = select(User)

    role_param = role or role_filter
    if role_param:
        normalized_role = role_param.strip().lower()
        try:
            role_value = UserRole(normalized_role)
        except ValueError:
            try:
                role_value = UserRole[role_param.strip().upper()]
            except KeyError:
                role_value = None
        if role_value:
            query = query.where(User.role == role_value.value)
    if verification_filter:
        normalized_status = verification_filter.strip().lower()
        try:
            status_value = VerificationStatus(normalized_status)
        except ValueError:
            status_value = VerificationStatus[verification_filter.strip().upper()]
        query = query.where(User.verification_status == status_value.value)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(User.created_at.desc())
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.post("/satellite/analyze", response_model=List[AnalysisResponse])
async def trigger_satellite_analysis(
    request: AnalysisRequest,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger satellite analysis for specified parcels.
    Platform Admins can run deforestation analysis.
    """
    # Get parcels
    if request.parcel_ids and len(request.parcel_ids) > 0:
        parcels_result = await db.execute(
            select(FarmParcel).where(FarmParcel.id.in_(request.parcel_ids))
        )
        parcels = parcels_result.scalars().all()
    else:
        # If no parcel IDs specified, analyze all parcels
        parcels_result = await db.execute(select(FarmParcel))
        parcels = parcels_result.scalars().all()
    
    if not parcels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No parcels found"
        )
    
    results = []
    
    for parcel in parcels:
        # Run analysis
        analysis = await satellite_engine.analyze_parcel(
            parcel=parcel,
            acquisition_date=request.acquisition_date
        )
        
        db.add(analysis)
        
        # Update parcel with analysis results
        parcel.ndvi_baseline = analysis.get("ndvi_mean", 0)
        parcel.canopy_density = analysis.get("canopy_cover_percentage", 0)
        
        results.append(analysis)
    
    await db.commit()
    
    return results


@router.get("/farms/{farm_id}")
async def get_farm(
    farm_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a single farm by ID with full details."""
    from app.models.user import User as UserModel, CooperativeMember, Cooperative
    from app.models.farm import LandParcel
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    owner_result = await db.execute(select(UserModel).where(UserModel.id == farm.owner_id))
    owner = owner_result.scalar_one_or_none()

    parcels_result = await db.execute(select(LandParcel).where(LandParcel.farm_id == farm.id))
    parcels = parcels_result.scalars().all()

    membership_result = await db.execute(
        select(CooperativeMember, Cooperative)
        .join(Cooperative, CooperativeMember.cooperative_id == Cooperative.id)
        .where(CooperativeMember.user_id == farm.owner_id)
        .where(CooperativeMember.is_active == True)
        .limit(1)
    )
    mem_row = membership_result.first()

    return {
        "id": farm.id,
        "farm_name": farm.farm_name,
        "farm_code": farm.farm_code,
        "status": farm.status,
        "verification_status": farm.verification_status,
        "compliance_status": farm.compliance_status,
        "total_area_hectares": farm.total_area_hectares,
        "coffee_varieties": farm.coffee_varieties,
        "years_farming": farm.years_farming,
        "average_annual_production_kg": farm.average_annual_production_kg,
        "centroid_lat": farm.centroid_lat,
        "centroid_lon": farm.centroid_lon,
        "created_at": farm.created_at,
        "owner": {
            "id": owner.id,
            "name": f"{owner.first_name} {owner.last_name}",
            "phone": getattr(owner, 'phone', None),
            "email": getattr(owner, 'email', None),
            "national_id": getattr(owner, 'national_id', None),
            "gender": getattr(owner, 'gender', None),
            "county": getattr(owner, 'county', None),
            "subcounty": getattr(owner, 'subcounty', None),
        } if owner else None,
        "membership": {
            "membership_number": mem_row[0].membership_number if mem_row else None,
            "cooperative_name": mem_row[1].name if mem_row else None,
            "cooperative_code": mem_row[1].code if mem_row else None,
        } if mem_row else None,
        "parcels": [
            {
                "id": p.id,
                "parcel_number": p.parcel_number,
                "parcel_name": p.parcel_name,
                "area_hectares": p.area_hectares,
                "land_use_type": p.land_use_type.value if p.land_use_type else None,
                "boundary_geojson": p.boundary_geojson,
                "verification_status": getattr(p, 'verification_status', None),
            }
            for p in parcels
        ],
    }


@router.patch("/farms/{farm_id}/approve")
async def approve_farm(
    farm_id: str,
    reason: str = "",
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending farm (Kipawa/admin level)."""
    from app.models.notification import Notification
    result = await db.execute(select(Farm).where(Farm.id == farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    farm.verification_status = "verified"
    farm.compliance_status = "Compliant"
    farm.certified_date = datetime.utcnow()
    farm.admin_verified_by_id = current_user.id
    farm.admin_verified_at = datetime.utcnow()
    farm.admin_notes = reason or None
    # Notify farmer
    notif = Notification(
        recipient_id=farm.owner_id,
        title="Farm Approved by Kipawa",
        message=f"Your farm '{farm.farm_name}' has been approved by Kipawa admin. {reason or ''}".strip(),
        type="success",
        reference_id=farm_id,
        reference_type="farm"
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farm approved", "verification_status": farm.verification_status}


@router.patch("/farms/{farm_id}/reject")
async def reject_farm(
    farm_id: str,
    reason: str = "",
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a farm submission (Kipawa/admin level)."""
    from app.models.notification import Notification
    result = await db.execute(select(Farm).where(Farm.id == farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    farm.verification_status = "rejected"
    farm.admin_verified_by_id = current_user.id
    farm.admin_verified_at = datetime.utcnow()
    farm.admin_notes = reason or "Rejected by admin"
    farm.notes = f"Rejected by admin: {reason}" if reason else "Rejected by admin"
    notif = Notification(
        recipient_id=farm.owner_id,
        title="Farm Rejected by Kipawa",
        message=f"Your farm '{farm.farm_name}' was rejected by Kipawa admin. Reason: {reason or 'No reason provided'}",
        type="error",
        reference_id=farm_id,
        reference_type="farm"
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farm rejected", "verification_status": farm.verification_status}


@router.get("/deliveries")
async def get_all_deliveries(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all deliveries for admin."""
    query = select(Delivery).order_by(Delivery.created_at.desc())
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    deliveries = result.scalars().all()
    return {"deliveries": deliveries, "total": total, "page": page, "page_size": page_size}


@router.get("/farms/risk-report")
async def get_risk_report(
    risk_level: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get deforestation risk report for all farms.
    Supports filtering by risk level and score range.
    """
    query = select(Farm)
    
    if risk_level:
        # Filter by specific risk level if provided
        pass  # Risk is stored as score, need to map to levels
    
    query = query.order_by(Farm.deforestation_risk_score.desc())
    
    result = await db.execute(query)
    farms = result.scalars().all()
    
    # Filter by score range if provided
    if min_score is not None:
        farms = [f for f in farms if f.deforestation_risk_score >= min_score]
    if max_score is not None:
        farms = [f for f in farms if f.deforestation_risk_score <= max_score]
    
    # Build report
    report = {
        "total_farms": len(farms),
        "high_risk_count": len([f for f in farms if f.deforestation_risk_score >= 70]),
        "medium_risk_count": len([f for f in farms if 30 <= f.deforestation_risk_score < 70]),
        "low_risk_count": len([f for f in farms if f.deforestation_risk_score < 30]),
        "farms": [
            {
                "id": f.id,
                "farm_name": f.farm_name,
                "risk_score": f.deforestation_risk_score,
                "compliance_status": f.compliance_status,
                "last_analysis": f.last_satellite_analysis.isoformat() if f.last_satellite_analysis else None
            }
            for f in farms
        ],
        "generated_at": datetime.utcnow().isoformat()
    }
    
    return report


@router.get("/compliance/overview")
async def get_compliance_overview(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system-wide compliance metrics.
    """
    # Get counts
    farms_result = await db.execute(select(func.count()).select_from(Farm))
    total_farms = farms_result.scalar() or 0
    
    batches_result = await db.execute(select(func.count()).select_from(Batch))
    total_batches = batches_result.scalar() or 0
    
    # Get compliance breakdown
    compliant_result = await db.execute(
        select(func.count()).select_from(Farm).where(Farm.compliance_status == "Compliant")
    )
    compliant_count = compliant_result.scalar() or 0
    
    under_review_result = await db.execute(
        select(func.count()).select_from(Farm).where(Farm.compliance_status == "Under Review")
    )
    under_review_count = under_review_result.scalar() or 0
    
    non_compliant_result = await db.execute(
        select(func.count()).select_from(Farm).where(Farm.compliance_status == "Non-Compliant")
    )
    non_compliant_count = non_compliant_result.scalar() or 0
    
    return {
        "total_farms": total_farms,
        "total_batches": total_batches,
        "compliance_breakdown": {
            "compliant": compliant_count,
            "under_review": under_review_count,
            "non_compliant": non_compliant_count
        },
        "compliance_rate": round((compliant_count / total_farms * 100), 2) if total_farms > 0 else 0,
        "generated_at": datetime.utcnow().isoformat()
    }


# ============== EUDR Tier 4: Regulatory Compliance APIs ==============

@router.post("/eudr/dds", response_model=DDSResponse)
async def generate_dds(
    dds_data: DDSRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Due Diligence Statement for EUDR compliance.
    Fetches linked farms to include geospatial and compliance data.
    """
    from app.models.compliance import DueDiligenceStatement
    
    # Fetch linked farms to include in DDS
    farms_data = []
    if dds_data.farm_ids:
        result = await db.execute(
            select(Farm).options(selectinload(Farm.parcels)).where(Farm.id.in_(dds_data.farm_ids))
        )
        farms = result.scalars().all()
        
        for farm in farms:
            centroid_lat = farm.centroid_lat
            centroid_lon = farm.centroid_lon
            if (centroid_lat is None or centroid_lon is None) and farm.parcels:
                first_parcel = farm.parcels[0]
                if first_parcel.boundary_geojson:
                    coords = first_parcel.boundary_geojson.get('coordinates', [[]])[0]
                    if coords and len(coords) > 0:
                        centroid_lat = sum(c[1] for c in coords) / len(coords)
                        centroid_lon = sum(c[0] for c in coords) / len(coords)
            
            farms_data.append({
                "id": farm.id,
                "farm_name": farm.farm_name or "Unnamed Farm",
                "country": "Kenya",
                "region": farm.cooperative_id or "Unknown Region",
                "centroid_lat": centroid_lat,
                "centroid_lon": centroid_lon,
                "area_hectares": farm.total_area_hectares,
                "coffee_area_hectares": farm.coffee_area_hectares,
                "verification_status": farm.verification_status,
                "compliance_status": farm.compliance_status,
                "deforestation_risk_score": farm.deforestation_risk_score
            })
    
    # Create DDS data structure
    dds_service_data = DDSData(
        operator_name=dds_data.operator_name,
        operator_id=dds_data.operator_id,
        contact_name=dds_data.contact_name,
        contact_email=dds_data.contact_email,
        contact_address=dds_data.contact_address,
        commodity_type=dds_data.commodity_type,
        hs_code=dds_data.hs_code,
        country_of_origin=dds_data.country_of_origin,
        quantity=dds_data.quantity,
        unit=dds_data.unit,
        supplier_name=dds_data.supplier_name,
        supplier_country=dds_data.supplier_country,
        first_placement_country=dds_data.first_placement_country,
        first_placement_date=dds_data.first_placement_date,
        farm_ids=dds_data.farm_ids
    )
    
    # Generate DDS dict
    dds_dict = eudr_service.generate_due_diligence_statement(dds_service_data, farms=farms_data)
    
    # Create ORM record
    dds = DueDiligenceStatement(
        dds_number=dds_dict['dds_number'],
        version=dds_dict['version'],
        operator_name=dds_dict['operator_name'],
        operator_id=dds_dict.get('operator_id'),
        contact_name=dds_dict.get('contact_name'),
        contact_email=dds_dict.get('contact_email'),
        contact_address=dds_dict.get('contact_address'),
        commodity_type=dds_dict['commodity_type'],
        hs_code=dds_dict.get('hs_code'),
        country_of_origin=dds_dict['country_of_origin'],
        quantity=dds_dict['quantity'],
        unit=dds_dict['unit'],
        supplier_name=dds_dict.get('supplier_name'),
        supplier_country=dds_dict.get('supplier_country'),
        first_placement_country=dds_dict.get('first_placement_country'),
        first_placement_date=dds_dict.get('first_placement_date'),
        risk_level=dds_dict['risk_level'],
        submission_status='draft',
        dds_hash=dds_dict.get('dds_hash'),
        signature=dds_dict.get('signature'),
        risk_assessment=dds_dict.get('risk_assessment'),
        mitigation_measures=dds_dict.get('mitigation_measures'),
        evidence_references=dds_dict.get('evidence_references'),
        farm_coordinates=dds_dict.get('farm_coordinates'),
        polygon_references=None,  # Could be populated later
        satellite_analysis_ids=None
    )
    
    db.add(dds)
    await db.commit()
    await db.refresh(dds)
    
    return dds


@router.get("/eudr/dds")
async def list_dds(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all Due Diligence Statements."""
    from app.models.compliance import DueDiligenceStatement
    query = select(DueDiligenceStatement).order_by(DueDiligenceStatement.created_at.desc())
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    dds_list = result.scalars().all()
    return {"dds": dds_list, "total": total, "page": page, "page_size": page_size}


@router.get("/eudr/dds/{dds_id}")
async def get_dds(
    dds_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get Due Diligence Statement details.
    """
    from app.models.compliance import DueDiligenceStatement
    
    dds = await db.get(DueDiligenceStatement, dds_id)
    
    if not dds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DDS not found"
        )
    
    return dds


@router.post("/eudr/certificate", response_model=CertificateResponse)
async def generate_certificate(
    cert_data: CertificateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate EUDR compliance certificate.
    """
    # Create certificate data structure
    cert_service_data = CertificateData(
        certificate_type=cert_data.certificate_type,
        entity_type=cert_data.entity_type,
        entity_id=cert_data.entity_id,
        entity_name=cert_data.entity_name,
        scope_description=cert_data.scope_description,
        product_scope=cert_data.product_scope,
        validity_days=cert_data.validity_days
    )
    
    # Generate certificate
    certificate = eudr_service.generate_certificate(cert_service_data)
    
    db.add(certificate)
    await db.commit()
    await db.refresh(certificate)
    
    return certificate


@router.get("/eudr/certificate/{cert_id}/verify")
async def verify_certificate(
    cert_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify EUDR compliance certificate authenticity.
    """
    from app.models.compliance import Certificate
    
    certificate = await db.get(Certificate, cert_id)
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    verification = eudr_service.verify_certificate(certificate)
    
    return verification


@router.get("/eudr/export/xml/{dds_id}")
async def export_dds_xml(
    dds_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Export Due Diligence Statement as EUDR-compliant XML.
    """
    from app.models.compliance import DueDiligenceStatement
    
    dds = await db.get(DueDiligenceStatement, dds_id)
    
    if not dds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DDS not found"
        )
    
    xml_content = eudr_service.generate_dds_xml(dds)
    
    return {
        "content": xml_content,
        "content_type": "application/xml",
        "filename": f"{dds.dds_number}.xml"
    }


@router.post("/farms/{farm_id}/compliance-check")
async def run_compliance_check(
    farm_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Run full compliance check for a farm.
    Aggregates satellite analysis, document verification, and traceability data.
    """
    farm = await db.get(Farm, farm_id)
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found"
        )
    
    # Gather compliance data
    # 1. Check deforestation status
    deforestation_ok = farm.deforestation_risk_score < 50
    
    # 2. Check documents
    docs_result = await db.execute(
        select(func.count()).select_from(LandDocument)
        .where(LandDocument.farm_id == farm_id, LandDocument.verification_status == "verified")
    )
    docs_count = docs_result.scalar() or 0
    
    # 3. Check traceability
    deliveries_result = await db.execute(
        select(func.count()).select_from(Delivery).where(Delivery.farm_id == farm_id)
    )
    deliveries_count = deliveries_result.scalar() or 0
    
    # Build checklist
    checklist = {
        "deforestation_free": 1 if deforestation_ok else 0,
        "legal_ownership": 1 if docs_count > 0 else 0,
        "traceability_verified": 1 if deliveries_count > 0 else 0,
        "documents_complete": 1 if docs_count >= 2 else 0,  # Require at least 2 documents
        "satellite_analysis_complete": 1 if farm.last_satellite_analysis else 0
    }
    
    # Calculate compliance score
    score_result = eudr_service.calculate_compliance_score(checklist)
    
    # Update farm status
    farm.compliance_status = "Compliant" if score_result["compliance_percentage"] >= 80 else "Under Review"
    
    await db.commit()
    
    return {
        "checklist": checklist,
        "score": score_result,
        "status": "Compliant" if score_result["compliance_percentage"] >= 80 else "Under Review"
    }


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get high-level platform statistics for Cooperatives, Farms, Farmers, and Compliance.
    """
    # Count total cooperatives
    total_cooperatives_result = await db.execute(select(func.count()).select_from(Cooperative))
    total_cooperatives = total_cooperatives_result.scalar() or 0
    
    # Count total farms and breakdown by verification_status
    total_farms_result = await db.execute(select(func.count()).select_from(Farm))
    total_farms = total_farms_result.scalar() or 0
    verified_farms = (await db.execute(select(func.count()).select_from(Farm).where(Farm.verification_status == 'verified'))).scalar() or 0
    pending_farms  = (await db.execute(select(func.count()).select_from(Farm).where(Farm.verification_status == 'pending'))).scalar() or 0
    draft_farms    = (await db.execute(select(func.count()).select_from(Farm).where(Farm.verification_status == 'draft'))).scalar() or 0
    
    # Count total farmers (users with 'farmer' role)
    total_farmers_result = await db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.FARMER.value)
    )
    total_farmers = total_farmers_result.scalar() or 0
    
    # Count total parcels
    total_parcels_result = await db.execute(select(func.count()).select_from(FarmParcel))
    total_parcels = total_parcels_result.scalar() or 0
    
    # Count total deliveries
    total_deliveries_result = await db.execute(select(func.count()).select_from(Delivery))
    total_deliveries = total_deliveries_result.scalar() or 0
    
    # Calculate compliance rate based on EUDRCompliance status
    compliant_result = await db.execute(
        select(func.count()).select_from(EUDRCompliance).where(
            EUDRCompliance.status == ComplianceStatus.COMPLIANT.value
        )
    )
    total_compliance_records = await db.execute(
        select(func.count()).select_from(EUDRCompliance)
    )
    
    compliant_count = compliant_result.scalar() or 0
    total_compliance = total_compliance_records.scalar() or 0
    compliance_rate = round((compliant_count / total_compliance * 100), 1) if total_compliance > 0 else 0
    
    return {
        "total_cooperatives": total_cooperatives,
        "total_farms": total_farms,
        "verified_farms": verified_farms,
        "pending_farms": pending_farms,
        "draft_farms": draft_farms,
        "total_farmers": total_farmers,
        "total_parcels": total_parcels,
        "total_deliveries": total_deliveries,
        "compliance_rate": compliance_rate
    }


# ============== Cooperative Management Endpoints ==============

@router.get("/cooperatives", response_model=List[CooperativeWithMembers])
async def get_all_cooperatives(
    verified_only: bool = False,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all cooperatives with member counts.
    Platform Admins and Auditors can access.
    """
    query = select(Cooperative)
    
    if verified_only:
        query = query.where(Cooperative.verification_status == "verified")
    
    # Get total count
    count_query = select(func.count()).select_from(Cooperative)
    if verified_only:
        count_query = count_query.where(Cooperative.verification_status == "verified")
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination and ordering
    query = query.order_by(Cooperative.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    cooperatives = result.scalars().all()
    
    # Build response with member counts and admin names
    response = []
    for coop in cooperatives:
        try:
            # Get member count
            members_count_result = await db.execute(
                select(func.count(CooperativeMember.id)).where(
                    CooperativeMember.cooperative_id == coop.id
                )
            )
            member_count = members_count_result.scalar() or 0
            
            # Get admin name if exists
            admin_name = None
            primary_officer_id = getattr(coop, 'primary_officer_id', None)
            if primary_officer_id:
                try:
                    admin = await db.get(User, primary_officer_id)
                    if admin:
                        admin_name = f"{admin.first_name} {admin.last_name}".strip()
                except Exception as e:
                    print(f"Warning: Could not fetch admin for cooperative {coop.id}: {e}")
            
            # Construct response with all required fields from schema
            coop_response = CooperativeWithMembers(
                id=coop.id,
                name=coop.name,
                code=getattr(coop, 'code', None),
                registration_number=getattr(coop, 'registration_number', None),
                tax_id=getattr(coop, 'tax_id', None),
                email=getattr(coop, 'email', None),
                phone=getattr(coop, 'phone', None),
                address=getattr(coop, 'address', None),
                country=getattr(coop, 'country', 'Kenya'),
                county=getattr(coop, 'county', None),
                district=getattr(coop, 'district', None),
                subcounty=getattr(coop, 'subcounty', None),
                ward=getattr(coop, 'ward', None),
                cooperative_type=getattr(coop, 'cooperative_type', None),
                latitude=getattr(coop, 'latitude', None),
                longitude=getattr(coop, 'longitude', None),
                establishment_date=getattr(coop, 'establishment_date', None),
                member_count=member_count,
                farm_count=0,  # Can be calculated if needed
                delivery_count=0,  # Can be calculated if needed
                is_active=getattr(coop, 'is_active', True),
                verification_status=getattr(coop, 'verification_status', 'pending'),
                members=[],  # Empty list for now, can be populated if needed
                created_at=getattr(coop, 'created_at', None),
                updated_at=getattr(coop, 'updated_at', None),
                primary_officer_id=getattr(coop, 'primary_officer_id', None),
                admin_name=admin_name,
                verification_date=getattr(coop, 'verification_date', None)
            )
            response.append(coop_response)
        except Exception as e:
            print(f"Error processing cooperative {coop.id}: {e}")
            # Skip this cooperative if there's an error
            continue
    
    return response


@router.post("/cooperatives", response_model=CooperativeResponse, status_code=status.HTTP_201_CREATED)
async def create_cooperative(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
    name: Optional[str] = Form(default=None),
    registration_number: Optional[str] = Form(default=None),
    cooperative_type: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    phone: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    county: Optional[str] = Form(default=None),
    district: Optional[str] = Form(default=None),
    subcounty: Optional[str] = Form(default=None),
    ward: Optional[str] = Form(default=None),
    tax_id: Optional[str] = Form(default=None),
    latitude: Optional[str] = Form(default=None),
    longitude: Optional[str] = Form(default=None),
    establishment_date: Optional[str] = Form(default=None),
    contact_person: Optional[str] = Form(default=None),
    contact_person_phone: Optional[str] = Form(default=None),
    contact_person_email: Optional[str] = Form(default=None),
    legal_status: Optional[str] = Form(default=None),
    governing_document: Optional[str] = Form(default=None),
    admin_email: Optional[str] = Form(default=None),
    admin_first_name: Optional[str] = Form(default=None),
    admin_last_name: Optional[str] = Form(default=None),
    admin_phone: Optional[str] = Form(default=None),
    documents: Optional[UploadFile] = File(default=None),
    document_ids: Optional[str] = Form(default=None)
):
    try:
        return await create_cooperative_impl(
            current_user, db, name, registration_number, cooperative_type, email, phone,
            address, county, district, subcounty, ward, tax_id, latitude, longitude,
            establishment_date, contact_person, contact_person_phone, contact_person_email,
            legal_status, governing_document, admin_email, admin_first_name, admin_last_name,
            admin_phone, documents, document_ids
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error in create_cooperative: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


async def create_cooperative_impl(
    current_user: User,
    db: AsyncSession,
    name: Optional[str],
    registration_number: Optional[str],
    cooperative_type: Optional[str],
    email: Optional[str],
    phone: Optional[str],
    address: Optional[str],
    county: Optional[str],
    district: Optional[str],
    subcounty: Optional[str],
    ward: Optional[str],
    tax_id: Optional[str],
    latitude: Optional[str],
    longitude: Optional[str],
    establishment_date: Optional[str],
    contact_person: Optional[str],
    contact_person_phone: Optional[str],
    contact_person_email: Optional[str],
    legal_status: Optional[str],
    governing_document: Optional[str],
    admin_email: Optional[str],
    admin_first_name: Optional[str],
    admin_last_name: Optional[str],
    admin_phone: Optional[str],
    documents: Optional[UploadFile],
    document_ids: Optional[str]
):
    print(f"[DEBUG] create_cooperative: name={name}, admin_email={admin_email}, document_ids={document_ids}")
    
    # Parse document_ids if provided
    doc_id_list = []
    if document_ids:
        import json
        print(f"[DEBUG] Parsing document_ids: {document_ids}")
        try:
            doc_id_list = json.loads(document_ids)
            print(f"[DEBUG] JSON parsed successfully: {doc_id_list}")
            if not isinstance(doc_id_list, list):
                doc_id_list = [doc_id_list]
        except Exception as e:
            # Fall back to comma-separated parsing
            print(f"[DEBUG] JSON parsing failed: {e}, trying comma-separated")
            doc_id_list = [id.strip() for id in document_ids.split(',') if id.strip()]
            print(f"[DEBUG] Comma-separated parsed: {doc_id_list}")
    
    # Ensure doc_id_list is always a list
    if not isinstance(doc_id_list, list):
        doc_id_list = []
    print(f"[DEBUG] Final doc_id_list: {doc_id_list}, type: {type(doc_id_list)}")
    
    # Build cooperative data dict
    coop_data_dict = {
        "name": name or "",
        "registration_number": registration_number,
        "cooperative_type": cooperative_type,
        "email": email,
        "phone": phone,
        "address": address,
        "county": county,
        "district": district,
        "subcounty": subcounty,
        "ward": ward,
        "tax_id": tax_id,
        "latitude": latitude,
        "longitude": longitude,
        "establishment_date": establishment_date,
        "contact_person": contact_person,
        "contact_person_phone": contact_person_phone,
        "contact_person_email": contact_person_email,
        "legal_status": legal_status,
        "governing_document": governing_document,
        "admin_email": admin_email,
        "admin_first_name": admin_first_name,
        "admin_last_name": admin_last_name,
        "admin_phone": admin_phone,
        "required_documents": doc_id_list
    }
    
    # Validate required fields
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not admin_email:
        raise HTTPException(status_code=400, detail="Admin email is required")
    
    # Check if registration number is unique if provided
    if registration_number:
        existing = await db.execute(
            select(Cooperative).where(Cooperative.registration_number == registration_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration number already exists"
            )
    
    admin_user = None
    
    # Create admin user if provided
    if admin_email:
        # Check if email already exists
        existing_user = await db.execute(
            select(User).where(User.email == admin_email)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin email already registered"
            )
        
        # Create the admin user
        from app.core.auth import get_password_hash
        
        admin_user = User(
            email=admin_email,
            password_hash=get_password_hash("TempPass123!"),
            first_name=admin_first_name or "Coop",
            last_name=admin_last_name or "Admin",
            phone=admin_phone,
            role=UserRole.COOPERATIVE_OFFICER,
            status=UserStatus.PENDING_VERIFICATION,
            password_reset_token=str(uuid.uuid4()),
            password_reset_expires=datetime.utcnow() + timedelta(hours=24)
        )
        db.add(admin_user)
        await db.flush()
    
    # Generate unique cooperative code in format PTC/YYYY/###
    from datetime import datetime as dt
    current_year = dt.now().year
    
    # Get the count of cooperatives created this year
    count_result = await db.execute(
        select(func.count(Cooperative.id)).where(
            Cooperative.code.like(f'PTC/{current_year}/%')
        )
    )
    coop_count = (count_result.scalar() or 0) + 1
    code = f"PTC/{current_year}/{coop_count:03d}"
    
    # Double-check this code doesn't exist (shouldn't happen but be safe)
    existing_code = await db.execute(
        select(Cooperative).where(Cooperative.code == code)
    )
    if existing_code.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique cooperative code"
        )
    
    # Create cooperative
    cooperative = Cooperative(
        name=name,
        code=code,
        registration_number=registration_number,
        email=email,
        phone=phone,
        address=address,
        county=county,
        district=district,
        subcounty=subcounty,
        ward=ward,
        tax_id=tax_id,
        latitude=latitude or None,
        longitude=longitude or None,
        contact_person=contact_person or None,
        contact_person_phone=contact_person_phone or None,
        contact_person_email=contact_person_email or None,
        legal_status=legal_status or None,
        governing_document=governing_document or None,
        cooperative_type=cooperative_type or None,
        primary_officer_id=admin_user.id if admin_user else None,
        verification_status="pending",
        member_count=0,
        is_active=True,
        required_documents=doc_id_list
    )
    
    db.add(cooperative)
    await db.commit()
    await db.refresh(cooperative)
    
    print(f"[DEBUG] Cooperative created successfully: ID={cooperative.id}, required_documents={cooperative.required_documents}, type={type(cooperative.required_documents)}")

    # Send welcome emails (fire-and-forget, don't block on failure)
    try:
        from app.core.email import send_cooperative_admin_welcome_email, send_cooperative_contact_welcome_email
        frontend_base = settings.app.frontend_base_url.rstrip('/')
        if admin_user and admin_email:
            reset_link = f"{frontend_base}?token={admin_user.password_reset_token}"
            await send_cooperative_admin_welcome_email(
                email=admin_email,
                first_name=admin_first_name or "Admin",
                cooperative_name=name or "Cooperative",
                setup_link=reset_link
            )
        if contact_person_email:
            await send_cooperative_contact_welcome_email(
                email=contact_person_email,
                contact_person=contact_person or "Contact Person",
                cooperative_name=name or "Cooperative",
                setup_link=f"{frontend_base}"
            )
    except Exception as email_err:
        print(f"[WARN] Email send failed (non-fatal): {email_err}")

    try:
        return cooperative
    except Exception as e:
        print(f"[ERROR] Failed to serialize cooperative response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create cooperative: {str(e)}"
        )


@router.get("/cooperatives/{coop_id}", response_model=CooperativeWithMembers)
async def get_cooperative(
    coop_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific cooperative with member details.
    """
    result = await db.execute(select(Cooperative).where(Cooperative.id == coop_id))
    cooperative = result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Get member count
    members_count_result = await db.execute(
        select(func.count()).select_from(CooperativeMember).where(
            CooperativeMember.cooperative_id == cooperative.id
        )
    )
    member_count = members_count_result.scalar() or 0
    
    # Get admin name
    admin_name = None
    if cooperative.primary_officer_id:
        admin_result = await db.execute(select(User).where(User.id == cooperative.primary_officer_id))
        admin = admin_result.scalar_one_or_none()
        if admin:
            admin_name = f"{admin.first_name} {admin.last_name}"
    
    return CooperativeWithMembers(
        id=cooperative.id,
        name=cooperative.name,
        registration_number=cooperative.registration_number,
        address=cooperative.address,
        phone=cooperative.phone,
        email=cooperative.email,
        country=cooperative.country,
        county=cooperative.county,
        primary_officer_id=cooperative.primary_officer_id,
        verification_status=cooperative.verification_status,
        verification_date=None,
        created_at=cooperative.created_at,
        updated_at=cooperative.updated_at,
        member_count=member_count,
        admin_name=admin_name
    )


@router.put("/cooperatives/{coop_id}", response_model=CooperativeResponse)
async def update_cooperative(
    coop_id: str,
    coop_data: CooperativeUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a cooperative.
    Platform Admins only.
    """
    result = await db.execute(select(Cooperative).where(Cooperative.id == coop_id))
    cooperative = result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Update fields
    update_data = coop_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cooperative, field, value)
    
    await db.commit()
    await db.refresh(cooperative)
    
    return cooperative


@router.post("/cooperatives/{coop_id}/assign-admin", response_model=UserResponse)
async def assign_cooperative_admin(
    coop_id: str,
    user_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Assign an existing user as cooperative admin.
    Platform Admins only.
    """
    coop_result = await db.execute(select(Cooperative).where(Cooperative.id == coop_id))
    cooperative = coop_result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user's role to COOPERATIVE_OFFICER
    user.role = UserRole.COOPERATIVE_OFFICER
    user.verification_status = VerificationStatus.VERIFIED
    
    # Assign as cooperative admin
    cooperative.primary_officer_id = user.id
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/cooperatives/{coop_id}/verify", response_model=CooperativeResponse)
async def verify_cooperative(
    coop_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a cooperative.
    Platform Admins only.
    """
    result = await db.execute(select(Cooperative).where(Cooperative.id == coop_id))
    cooperative = result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    cooperative.verification_status = True
    cooperative.verification_date = datetime.utcnow()
    
    await db.commit()
    await db.refresh(cooperative)
    
    return cooperative


# ============== Farmer Verification Management ==============

@router.get("/farmers/pending", response_model=List[UserResponse])
async def get_pending_farmers(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all farmers pending verification.
    Platform Admins and Coop Admins can access.
    """
    query = select(User).where(
        User.role == UserRole.FARMER,
        User.verification_status == VerificationStatus.PENDING
    )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(User.created_at.desc())
    
    result = await db.execute(query)
    farmers = result.scalars().all()
    
    return farmers


@router.put("/farmers/{user_id}/verify", response_model=UserResponse)
async def verify_farmer(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a farmer (admin level).
    """
    user = await db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.role != UserRole.FARMER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only verify farmers"
        )
    
    user.verification_status = VerificationStatus.VERIFIED
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.put("/farmers/{user_id}/reject", response_model=UserResponse)
async def reject_farmer(
    user_id: int,
    reason: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Reject a farmer's verification.
    """
    user = await db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.role != UserRole.FARMER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only reject farmers"
        )
    
    user.verification_status = VerificationStatus.REJECTED
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/farmers/{farmer_id}/approve")
async def admin_approve_farmer(
    farmer_id: str,
    body: dict = {},
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin (Kipawa) approves a farmer — sets final verification_status=verified."""
    from datetime import datetime
    from app.models.notification import Notification
    farmer = await db.get(User, farmer_id)
    if not farmer or farmer.role.value != 'farmer':
        raise HTTPException(status_code=404, detail="Farmer not found")
    farmer.verification_status = VerificationStatus.VERIFIED
    farmer.admin_verified_by_name = current_user.first_name + ' ' + current_user.last_name
    farmer.admin_verified_at = datetime.utcnow()
    farmer.admin_notes = body.get('notes', '') if isinstance(body, dict) else ''
    farmer.status = UserStatus.ACTIVE
    notif = Notification(
        id=str(__import__('uuid').uuid4()),
        recipient_id=farmer.id,
        title='Account Fully Verified',
        message=f'Your account has been fully verified and approved by Kipawa admin.',
        type='success',
        reference_type='farmer',
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farmer fully approved", "verification_status": "verified"}


@router.patch("/farmers/{farmer_id}/reject")
async def admin_reject_farmer(
    farmer_id: str,
    body: dict = {},
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin (Kipawa) rejects a farmer."""
    from datetime import datetime
    from app.models.notification import Notification
    farmer = await db.get(User, farmer_id)
    if not farmer or farmer.role.value != 'farmer':
        raise HTTPException(status_code=404, detail="Farmer not found")
    reason = body.get('notes', '') if isinstance(body, dict) else ''
    farmer.verification_status = VerificationStatus.REJECTED
    farmer.admin_verified_by_name = current_user.first_name + ' ' + current_user.last_name
    farmer.admin_verified_at = datetime.utcnow()
    farmer.admin_notes = reason
    notif = Notification(
        id=str(__import__('uuid').uuid4()),
        recipient_id=farmer.id,
        title='Account Verification Rejected',
        message=f'Your account verification was rejected by Kipawa admin{(": " + reason) if reason else "."}',
        type='error',
        reference_type='farmer',
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farmer rejected by admin", "verification_status": "rejected"}


# ============== Verification Endpoints ==============

@router.get("/verification/pending")
async def get_pending_verifications(
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get pending farm verifications — only farmers (not admin/coop accounts).
    Returns farms in pending state with their owner info.
    """
    # Return only farms owned by farmer-role users that are pending verification
    result = await db.execute(
        select(Farm).join(User, Farm.owner_id == User.id)
        .where(
            Farm.verification_status.in_(["pending", "coop_approved"]),
            Farm.deleted_at == None,
            User.role == UserRole.FARMER.value
        )
        .order_by(Farm.created_at.desc()).limit(limit)
    )
    farms = result.scalars().all()

    # Fetch owners
    output = []
    for f in farms:
        owner_result = await db.execute(select(User).where(User.id == f.owner_id))
        owner = owner_result.scalar_one_or_none()
        coop_name = None
        if f.cooperative_id:
            coop_result = await db.execute(select(Cooperative).where(Cooperative.id == f.cooperative_id))
            coop = coop_result.scalar_one_or_none()
            if coop: coop_name = coop.name

        # Who approved at coop level
        coop_approver_name = None
        if f.coop_verified_by_id:
            ca_result = await db.execute(select(User).where(User.id == f.coop_verified_by_id))
            ca = ca_result.scalar_one_or_none()
            if ca: coop_approver_name = f"{ca.first_name} {ca.last_name}"

        output.append({
            "id": f.id,
            "farm_name": f.farm_name,
            "farmer_name": f"{owner.first_name} {owner.last_name}" if owner else "Unknown",
            "farmer_email": owner.email if owner else None,
            "farmer_phone": owner.phone if owner else None,
            "cooperative_name": coop_name,
            "verification_status": f.verification_status,
            "coop_status": f.coop_status,
            "coop_approver": coop_approver_name,
            "coop_notes": f.coop_notes,
            "total_area_hectares": f.total_area_hectares,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return output


@router.post("/verification/{user_id}/approve")
async def approve_verification(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a user's verification."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.verification_status = VerificationStatus.VERIFIED
    user.status = UserStatus.ACTIVE
    await db.commit()
    await db.refresh(user)
    return {"message": "User verified successfully", "user_id": user_id}


@router.post("/verification/{user_id}/reject")
async def reject_verification(
    user_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a user's verification."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.verification_status = VerificationStatus.REJECTED
    await db.commit()
    await db.refresh(user)
    return {"message": "User verification rejected", "user_id": user_id}


# ============== Payment Chart Endpoints ==============

@router.get("/payments/chart")
async def get_payments_chart(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get payment chart data.
    Platform Admins can access.
    """
    # Return empty chart data structure
    return {
        "labels": [],
        "datasets": []
    }


# ============== User Management Endpoints ==============

@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user account.
    Platform Admins only.
    """
    user = await db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "User deleted successfully"}


@router.post("/users/{user_id}/suspend", response_model=UserResponse)
async def suspend_user(
    user_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Suspend a user account.
    Platform Admins only.
    """
    user = await db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-suspension
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend your own account"
        )
    
    user.is_locked = True
    user.status = UserStatus.SUSPENDED
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/users/{user_id}/unsuspend", response_model=UserResponse)
async def unsuspend_user(
    user_id: int,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Unsuspend a user account.
    Platform Admins only.
    """
    user = await db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_locked = False
    user.status = UserStatus.ACTIVE
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.get("/users/export")
async def export_users(
    role_filter: Optional[str] = None,
    verification_filter: Optional[str] = None,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Export users data as CSV.
    Platform Admins only.
    """
    query = select(User)
    
    if role_filter:
        try:
            role_value = UserRole(role_filter.strip().lower())
        except ValueError:
            role_value = UserRole[role_filter.strip().upper()]
        query = query.where(User.role == role_value.value)
    
    if verification_filter:
        try:
            status_value = VerificationStatus(verification_filter.strip().lower())
        except ValueError:
            status_value = VerificationStatus[verification_filter.strip().upper()]
        query = query.where(User.verification_status == status_value.value)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Build CSV data
    csv_data = []
    for user in users:
        csv_data.append({
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value if user.role else "",
            "verification_status": user.verification_status.value if user.verification_status else "",
            "status": user.status.value if user.status else "",
            "created_at": user.created_at.isoformat() if user.created_at else ""
        })
    
    return {
        "data": csv_data,
        "total": len(csv_data)
    }


@router.get("/farmers/verified")
async def get_verified_farmers(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all verified farmers.
    Platform Admins and Coop Admins can access.
    """
    query = select(User).where(
        User.role == UserRole.FARMER,
        User.verification_status == VerificationStatus.VERIFIED
    )
    
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(User.created_at.desc())
    
    result = await db.execute(query)
    farmers = result.scalars().all()
    
    return {
        "farmers": farmers,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/farmers/rejected")
async def get_rejected_farmers(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all rejected farmers.
    Platform Admins and Coop Admins can access.
    """
    query = select(User).where(
        User.role == UserRole.FARMER,
        User.verification_status == VerificationStatus.REJECTED
    )
    
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(User.updated_at.desc())
    
    result = await db.execute(query)
    farmers = result.scalars().all()
    
    return {
        "farmers": farmers,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.delete("/cooperatives/{coop_id}", response_model=MessageResponse)
async def delete_cooperative(
    coop_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a cooperative.
    Platform Admins only.
    """
    result = await db.execute(select(Cooperative).where(Cooperative.id == coop_id))
    cooperative = result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Check if cooperative has members
    members_result = await db.execute(
        select(func.count()).select_from(CooperativeMember).where(
            CooperativeMember.cooperative_id == coop_id
        )
    )
    member_count = members_result.scalar() or 0
    
    if member_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete cooperative with active members"
        )
    
    await db.delete(cooperative)
    await db.commit()
    
    return {"message": "Cooperative deleted successfully"}


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed user information.
    Platform Admins only.
    """
    user = await db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get related farms
    farms_result = await db.execute(
        select(Farm).where(Farm.owner_id == user_id)
    )
    farms = farms_result.scalars().all()
    
    # Get cooperative memberships
    memberships_result = await db.execute(
        select(CooperativeMember).where(CooperativeMember.user_id == str(user_id))
    )
    memberships = memberships_result.scalars().all()
    
    return {
        "user": user,
        "farms": farms,
        "memberships": memberships
    }


@router.put("/farmers/{user_id}/status")
async def update_farmer_status(
    user_id: int,
    status: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update farmer account status.
    Platform Admins can activate, suspend, or deactivate farmers.
    """
    user = await db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.role != UserRole.FARMER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update status for farmers"
        )
    
    # Validate status
    valid_statuses = ["active", "inactive", "suspended", "pending_verification"]
    if status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status must be one of: {', '.join(valid_statuses)}"
        )
    
    user.status = UserStatus(status.lower())
    user.is_locked = (status.lower() == "suspended")
    
    await db.commit()
    await db.refresh(user)
    
    return user


# ============== Compliance Chart Endpoint ==============

@router.get("/compliance/overview/chart")
async def get_compliance_chart(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get compliance chart data.
    """
    farms_result = await db.execute(select(func.count()).select_from(Farm))
    total_farms = farms_result.scalar() or 0
    
    compliant_result = await db.execute(
        select(func.count()).select_from(Farm).where(Farm.compliance_status == "Compliant")
    )
    compliant_count = compliant_result.scalar() or 0
    
    under_review_result = await db.execute(
        select(func.count()).select_from(Farm).where(Farm.compliance_status == "Under Review")
    )
    under_review_count = under_review_result.scalar() or 0
    
    non_compliant_result = await db.execute(
        select(func.count()).select_from(Farm).where(Farm.compliance_status == "Non-Compliant")
    )
    non_compliant_count = non_compliant_result.scalar() or 0
    
    return {
        "labels": ["Compliant", "Under Review", "Non-Compliant"],
        "datasets": [
            {
                "data": [compliant_count, under_review_count, non_compliant_count]
            }
        ]
    }


# ============== System Config Endpoints ==============

@router.get("/config/required-documents")
async def get_required_documents(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get required documents from DB."""
    from app.models.system import RequiredDocument
    result = await db.execute(
        select(RequiredDocument)
        .where(RequiredDocument.is_active == True, RequiredDocument.is_deleted == 0)
        .order_by(RequiredDocument.sort_order, RequiredDocument.created_at)
    )
    docs = result.scalars().all()
    return [d.to_dict() for d in docs]


@router.post("/config/required-documents")
async def create_required_document(
    doc_data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new required document."""
    from app.models.system import RequiredDocument
    doc = RequiredDocument(
        name=doc_data.get("name"),
        display_name=doc_data.get("display_name"),
        description=doc_data.get("description"),
        document_type=doc_data.get("document_type"),
        is_required=doc_data.get("is_required", True),
        sort_order=doc_data.get("sort_order", 0),
        is_active=True
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc.to_dict()


@router.put("/config/required-documents/{doc_id}")
async def update_required_document(
    doc_id: str,
    doc_data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing required document."""
    from app.models.system import RequiredDocument
    result = await db.execute(select(RequiredDocument).where(RequiredDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for field in ["name", "display_name", "description", "document_type", "is_required", "sort_order"]:
        if field in doc_data:
            setattr(doc, field, doc_data[field])
    await db.commit()
    await db.refresh(doc)
    return doc.to_dict()


@router.delete("/config/required-documents/{doc_id}")
async def delete_required_document(
    doc_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete a required document."""
    from app.models.system import RequiredDocument
    result = await db.execute(select(RequiredDocument).where(RequiredDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_active = False
    doc.is_deleted = 1
    await db.commit()
    return {"message": "Document deleted"}


@router.get("/config/session-timeout")
async def get_session_timeout(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get session timeout from DB config."""
    from app.models.system import SystemConfig
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "session_timeout")
    )
    cfg = result.scalar_one_or_none()
    if cfg and cfg.config_value:
        return cfg.config_value
    return {"session_timeout_minutes": 60, "max_login_attempts": 5, "lockout_duration_minutes": 15}


@router.put("/config/session-timeout")
async def update_session_timeout(
    data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Save session timeout to DB config."""
    from app.models.system import SystemConfig
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "session_timeout")
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.config_value = data
    else:
        cfg = SystemConfig(config_key="session_timeout", config_value=data, is_public=False)
        db.add(cfg)
    await db.commit()
    return {"message": "Session timeout updated", **data}


@router.get("/config/settings")
async def get_system_settings(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Return current system settings from config + any DB overrides, masking secrets."""
    from app.core.config import settings
    from app.models.system import SystemConfig

    # Load any DB overrides stored under config keys
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key.like("cfg_%")))
    db_configs = {r.config_key: r.config_value for r in result.scalars().all()}

    def db_or(key, default):
        return db_configs.get(key, default)

    def mask(v):
        return "***" if v else ""

    return {
        "satellite": {
            "provider": db_or("cfg_satellite_provider", settings.satellite.provider),
            "api_key": db_or("cfg_satellite_api_key", mask(settings.satellite.api_key)),
            "base_url": db_or("cfg_satellite_base_url", settings.satellite.base_url),
            "simulation_mode": db_or("cfg_satellite_simulation_mode", settings.satellite.simulation_mode),
        },
        "email": {
            "resend_api_key": db_or("cfg_email_resend_api_key", mask(settings.email.resend_api_key)),
            "from_email": db_or("cfg_email_from_email", settings.email.from_email),
            "from_name": db_or("cfg_email_from_name", settings.email.from_name),
        },
        "storage": {
            "s3_bucket": db_or("cfg_s3_bucket", settings.storage.s3_bucket),
            "s3_endpoint": db_or("cfg_s3_endpoint", settings.storage.s3_endpoint),
            "s3_access_key": db_or("cfg_s3_access_key", settings.storage.s3_access_key),
            "s3_secret_key": db_or("cfg_s3_secret_key", mask(settings.storage.s3_secret_key)),
            "s3_region": db_or("cfg_s3_region", settings.storage.s3_region),
        },
        "payments": {
            "enabled": db_or("cfg_payments_enabled", settings.payments.enabled),
            "mpesa_consumer_key": db_or("cfg_mpesa_consumer_key", settings.payments.mpesa_consumer_key),
            "mpesa_consumer_secret": db_or("cfg_mpesa_consumer_secret", mask(settings.payments.mpesa_consumer_secret)),
            "mpesa_shortcode": db_or("cfg_mpesa_shortcode", settings.payments.mpesa_shortcode),
        },
        "app": {
            "name": db_or("cfg_app_name", settings.app.name),
            "debug": db_or("cfg_app_debug", settings.app.debug),
            "access_token_expire_minutes": db_or("cfg_token_expire", settings.app.access_token_expire_minutes),
            "frontend_base_url": db_or("cfg_frontend_url", settings.app.frontend_base_url),
        },
    }


@router.put("/config/settings")
async def update_system_settings(
    data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update system settings — stored in SystemConfig DB table (overrides config.yaml)."""
    from app.models.system import SystemConfig
    section = data.get("section")
    updates = data.get("values", {})
    if not section or not updates:
        raise HTTPException(status_code=400, detail="section and values required")

    prefix_map = {
        "satellite": "cfg_satellite_",
        "email": "cfg_email_",
        "storage": "cfg_s3_",
        "payments": "cfg_payments_",
        "app": "cfg_app_",
    }
    prefix = prefix_map.get(section, f"cfg_{section}_")

    for field, value in updates.items():
        if value == "***":
            continue  # skip masked secrets — user didn't change them
        key = f"{prefix}{field}"
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        cfg = result.scalar_one_or_none()
        if cfg:
            cfg.config_value = value
        else:
            db.add(SystemConfig(config_key=key, config_value=value, is_public=False))

    await db.commit()
    return {"message": f"{section} settings updated"}


@router.get("/config/env-credentials")
async def get_env_credentials(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get env credentials from DB config."""
    from app.models.system import SystemConfig
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "env_credentials")
    )
    cfg = result.scalar_one_or_none()
    credentials = cfg.config_value if (cfg and cfg.config_value) else {}
    return {"credentials": credentials}


@router.put("/config/env-credentials")
async def upsert_env_credential(
    data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add or update a credential key in DB config."""
    from app.models.system import SystemConfig
    key = data.get("key")
    value = data.get("value")
    description = data.get("description", "")
    is_public = data.get("is_public", False)
    if not key:
        raise HTTPException(status_code=400, detail="Key is required")
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "env_credentials")
    )
    cfg = result.scalar_one_or_none()
    credentials = cfg.config_value if (cfg and cfg.config_value) else {}
    credentials[key] = {"value": value, "description": description, "is_public": is_public}
    if cfg:
        cfg.config_value = credentials
    else:
        cfg = SystemConfig(config_key="env_credentials", config_value=credentials, is_public=False)
        db.add(cfg)
    await db.commit()
    return {"message": "Credential saved", "credentials": credentials}


@router.delete("/config/env-credentials/{key}")
async def delete_env_credential(
    key: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Remove a credential key from DB config."""
    from app.models.system import SystemConfig
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "env_credentials")
    )
    cfg = result.scalar_one_or_none()
    if not cfg or not cfg.config_value or key not in cfg.config_value:
        raise HTTPException(status_code=404, detail="Credential not found")
    del cfg.config_value[key]
    # Force SQLAlchemy to detect the JSON mutation
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(cfg, "config_value")
    await db.commit()
    return {"message": "Credential deleted"}
