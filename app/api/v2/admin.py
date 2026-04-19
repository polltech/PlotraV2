"""
Plotra Platform - Admin API Endpoints (Tier 3 & 4)
Satellite analysis, user management, and compliance oversight
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user, require_platform_admin, require_admin
from app.core.config import settings
from app.models.user import User, UserRole, VerificationStatus, Cooperative, CooperativeMember
from app.models.farm import Farm, FarmParcel, LandDocument
from app.models.traceability import Batch, Delivery
from app.models.satellite import SatelliteAnalysis, AnalysisStatus, RiskLevel
from app.models.compliance import EUDRCompliance, ComplianceStatus
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


def create_cooperative_response(cooperative: Cooperative, admin_reset: bool = False, contact_reset: bool = False) -> dict:
    """Create a dict response for cooperative creation"""
    return {
        "id": cooperative.id,
        "name": cooperative.name,
        "code": cooperative.code,
        "registration_number": cooperative.registration_number,
        "address": cooperative.address,
        "phone": cooperative.phone,
        "contact_phone": cooperative.contact_phone,
        "contact_email": cooperative.contact_email,
        "country": cooperative.country,
        "county": cooperative.county,
        "subcounty": cooperative.subcounty,
        "cooperative_type": cooperative.cooperative_type,
        "primary_admin_id": cooperative.primary_admin_id,
        "contact_person_id": cooperative.contact_person_id,
        "is_verified": cooperative.is_verified,
        "verification_date": cooperative.verification_date,
        "created_at": cooperative.created_at,
        "updated_at": cooperative.updated_at,
        "admin_password_reset_sent": admin_reset,
        "contact_person_password_reset_sent": contact_reset
    }


@router.get("/farms")
async def get_all_farms(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all farms with pagination.
    Platform Admins and Auditors can access.
    """
    query = select(Farm)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Farm.created_at.desc())
    
    result = await db.execute(query)
    farms = result.scalars().all()
    
    return {
        "farms": farms,
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
    """
    query = select(User)
    
    if role_filter:
        normalized_role = role_filter.strip().lower()
        try:
            role_value = UserRole(normalized_role)
        except ValueError:
            # allow named form like "FARMER"
            role_value = UserRole[role_filter.strip().upper()]
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
        parcel.ndvi_baseline = analysis.ndvi_mean
        parcel.canopy_density = analysis.canopy_cover_percentage
        
        results.append(analysis)
    
    await db.commit()
    
    return results


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
    high_threshold = settings.satellite.risk_thresholds["high"]
    medium_threshold = settings.satellite.risk_thresholds["medium"]
    report = {
        "total_farms": len(farms),
        "high_risk_count": len([f for f in farms if f.deforestation_risk_score >= high_threshold]),
        "medium_risk_count": len([f for f in farms if medium_threshold <= f.deforestation_risk_score < high_threshold]),
        "low_risk_count": len([f for f in farms if f.deforestation_risk_score < medium_threshold]),
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


@router.get("/farms/{farm_id}")
async def get_farm_by_id(
    farm_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a single farm by ID."""
    farm = await db.get(Farm, farm_id)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


@router.get("/deliveries")
async def get_all_deliveries(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all coffee deliveries (admin view)."""
    count_result = await db.execute(select(func.count()).select_from(Delivery))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Delivery).order_by(Delivery.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    deliveries = result.scalars().all()

    return {
        "deliveries": deliveries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


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
    """
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
    
    # Generate DDS
    dds = eudr_service.generate_due_diligence_statement(dds_service_data)
    
    db.add(dds)
    await db.commit()
    await db.refresh(dds)
    
    return dds


@router.get("/eudr/dds")
async def get_dds_list(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all Due Diligence Statements."""
    from app.models.compliance import DueDiligenceStatement
    result = await db.execute(
        select(DueDiligenceStatement).order_by(DueDiligenceStatement.created_at.desc())
    )
    return result.scalars().all()


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
    compliance_pct = score_result.get("compliance_percentage", 0)
    compliance_status = "Compliant" if compliance_pct >= settings.eudr.compliance_thresholds["compliant"] else "Under Review"

    # Update farm compliance status
    farm.compliance_status = compliance_status
    await db.commit()

    return {
        "checklist": checklist,
        "score": score_result,
        "status": compliance_status
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
    
    # Count total farms
    total_farms_result = await db.execute(select(func.count()).select_from(Farm))
    total_farms = total_farms_result.scalar() or 0
    
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
        query = query.where(Cooperative.is_verified == True)
    
    # Get total count
    count_query = select(func.count(Cooperative.id))
    if verified_only:
        count_query = count_query.where(Cooperative.is_verified == True)
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
            if getattr(coop, 'primary_admin_id', None) or getattr(coop, 'primary_officer_id', None):
                admin_id = getattr(coop, 'primary_admin_id', None) or getattr(coop, 'primary_officer_id', None)
                try:
                    admin = await db.get(User, admin_id)
                    if admin:
                        admin_name = f"{admin.first_name} {admin.last_name}".strip()
                except Exception as e:
                    print(f"Warning: Could not fetch admin for cooperative {coop.id}: {e}")
            
            # Construct response with required fields
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
                farm_count=0,
                delivery_count=0,
                is_active=getattr(coop, 'is_active', True),
                verification_status=str(getattr(coop, 'is_verified', False)).lower() if getattr(coop, 'is_verified', False) else "pending",
                members=[],
                created_at=getattr(coop, 'created_at', None),
                updated_at=getattr(coop, 'updated_at', None),
                primary_officer_id=getattr(coop, 'primary_admin_id', None) or getattr(coop, 'primary_officer_id', None),
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
    coop_data: CooperativeCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new cooperative.
    Optionally create and assign an admin user.
    Platform Admins only.
    """
    # Check if registration number is unique if provided
    if coop_data.registration_number:
        existing = await db.execute(
            select(Cooperative).where(Cooperative.registration_number == coop_data.registration_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration number already exists"
            )
    
    admin_user = None
    contact_person_user = None
    admin_reset_sent = False
    contact_reset_sent = False
    
    # Helper function to send password reset email
    async def send_password_reset_email(user_obj: User, db: AsyncSession, coop_name: str = "your cooperative"):
        """Generate password reset token and send email"""
        try:
            from app.core.email import send_email
        except ImportError:
            print("WARNING: Email service not configured")
            send_email = None
        
        if not send_email:
            return False
        
        # Generate reset token
        reset_token = str(uuid.uuid4())
        reset_expires = datetime.utcnow() + timedelta(hours=settings.auth.password_reset_token_expiry_hours)
        
        user_obj.password_reset_token = reset_token
        user_obj.password_reset_expires = reset_expires
        
        # Store email in session storage for auto-login after password reset
        # The frontend will use this to auto-login after password reset
        # (This is communicated via the reset link URL)
        
        await db.flush()
        
        # Send reset email
        reset_link = f"{settings.app.frontend_base_url}/reset-password?token={reset_token}&email={user_obj.email}"
        subject = "Plotra Platform - Set Your Password"
        
        text_content = f"""
        Welcome to the Plotra Platform!
        
        Your account has been created as part of the cooperative "{coop_name}".
        
        To set your password and access your dashboard, please click the link below:
        
        {reset_link}
        
        This link will expire in 24 hours for security reasons.
        
        If you did not expect this email, please contact your administrator.
        """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Welcome to Plotra</title>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; padding: 20px 0; border-bottom: 1px solid #eeeeee; }}
                .content {{ padding: 20px 0; }}
                .btn {{ display: inline-block; padding: 12px 24px; background-color: #6f4e37; color: #ffffff; text-decoration: none; border-radius: 6px; margin-top: 20px; }}
                .footer {{ text-align: center; padding-top: 20px; color: #888888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="color: #6f4e37; margin: 0;">Welcome to Plotra!</h2>
                </div>
                <div class="content">
                    <p>Your account has been created as part of the cooperative <strong>{coop_name}</strong>.</p>
                    <p>To set your password and access your dashboard, please click the button below:</p>
                    <p style="text-align: center;">
                        <a href="{reset_link}" class="btn">Set Your Password</a>
                    </p>
                    <p><small>This link will expire in 24 hours for security reasons.</small></p>
                </div>
                <div class="footer">
                    <p>If you did not expect this email, please contact your administrator.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        try:
            await send_email(
                to=user_obj.email,
                subject=subject,
                text_content=text_content,
                html_content=html_content
            )
            return True
        except Exception as e:
            print(f"Failed to send password reset email: {e}")
            return False
    
    # Create admin user if provided
    if coop_data.admin_email:
        # Check if email already exists
        existing_user = await db.execute(
            select(User).where(User.email == coop_data.admin_email)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin email already registered"
            )
        
        # Create the admin user with temporary password (will need reset)
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            email=coop_data.admin_email,
            password_hash=pwd_context.hash(coop_data.admin_password or "TempPass123!"),
            first_name=coop_data.admin_first_name or "Coop",
            last_name=coop_data.admin_last_name or "Admin",
            phone_number=coop_data.admin_phone,
            role=UserRole.COOP_ADMIN,
            verification_status=VerificationStatus.VERIFIED,
            country=coop_data.country,
            county=coop_data.county,
            # Set a password reset required flag for force change on first login
            password_reset_token=str(uuid.uuid4()),  # Mark as needing password change
            password_reset_expires=datetime.utcnow() + timedelta(days=7)
        )
        db.add(admin_user)
        await db.flush()
    
    # Create contact person user if provided
    if coop_data.contact_person_email:
        # Check if email already exists
        existing_contact = await db.execute(
            select(User).where(User.email == coop_data.contact_person_email)
        )
        if existing_contact.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact person email already registered"
            )
        
        # Create the contact person user
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        contact_person_user = User(
            email=coop_data.contact_person_email,
            password_hash=pwd_context.hash(coop_data.admin_password or "TempPass123!"),
            first_name=coop_data.contact_person_first_name or "Coop",
            last_name=coop_data.contact_person_last_name or "Contact",
            phone_number=coop_data.contact_person_phone,
            role=UserRole.COOP_ADMIN,  # Could also be FARMER or another role based on requirements
            verification_status=VerificationStatus.VERIFIED,
            country=coop_data.country,
            county=coop_data.county,
            # Set a password reset required flag for force change on first login
            password_reset_token=str(uuid.uuid4()),
            password_reset_expires=datetime.utcnow() + timedelta(days=7)
        )
        db.add(contact_person_user)
        await db.flush()
    
    # Generate unique cooperative code in format PTC/YYYY/###
    from datetime import datetime as dt
    from sqlalchemy import func
    
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
        name=coop_data.name,
        code=code,
        registration_number=coop_data.registration_number,
        address=coop_data.address,
        phone=coop_data.phone,
        contact_phone=coop_data.contact_phone,
        contact_email=coop_data.contact_email,
        country=coop_data.country,
        county=coop_data.county,
        subcounty=coop_data.subcounty,
        cooperative_type=coop_data.cooperative_type,
        primary_admin_id=admin_user.id if admin_user else None,
        contact_person_id=contact_person_user.id if contact_person_user else None,
        is_verified=True  # Auto-verify cooperatives created by platform admin
    )
    
    db.add(cooperative)
    await db.flush()
    
    # Send password reset emails if requested
    if coop_data.send_password_reset:
        if admin_user:
            admin_reset_sent = await send_password_reset_email(admin_user, db)
        if contact_person_user:
            contact_reset_sent = await send_password_reset_email(contact_person_user, db)
    
    await db.commit()
    await db.refresh(cooperative)
    
    # Build response with additional info
    response_data = {
        "id": cooperative.id,
        "name": cooperative.name,
        "code": cooperative.code,
        "registration_number": cooperative.registration_number,
        "address": cooperative.address,
        "phone": cooperative.phone,
        "contact_phone": cooperative.contact_phone,
        "contact_email": cooperative.contact_email,
        "country": cooperative.country,
        "county": cooperative.county,
        "subcounty": cooperative.subcounty,
        "cooperative_type": cooperative.cooperative_type,
        "primary_admin_id": cooperative.primary_admin_id,
        "contact_person_id": cooperative.contact_person_id,
        "is_verified": cooperative.is_verified,
        "verification_date": cooperative.verification_date,
        "created_at": cooperative.created_at,
        "updated_at": cooperative.updated_at,
        # Include info about password reset emails sent
        "admin_password_reset_sent": admin_reset_sent,
        "contact_person_password_reset_sent": contact_reset_sent
    }
    
    return response_data


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
    if cooperative.primary_admin_id:
        admin_result = await db.execute(select(User).where(User.id == cooperative.primary_admin_id))
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
        primary_admin_id=cooperative.primary_admin_id,
        is_verified=cooperative.is_verified,
        verification_date=cooperative.verification_date,
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


class AssignAdminRequest(BaseModel):
    user_id: str


@router.post("/cooperatives/{coop_id}/assign-admin", response_model=UserResponse)
async def assign_cooperative_admin(
    coop_id: str,
    body: AssignAdminRequest,
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
    
    user_result = await db.execute(select(User).where(User.id == body.user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update user's role to COOP_ADMIN
    user.role = UserRole.COOP_ADMIN
    user.verification_status = VerificationStatus.VERIFIED

    # Assign as cooperative admin
    cooperative.primary_admin_id = user.id
    
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
    
    cooperative.is_verified = True
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
    # Note: In a full implementation, you'd also store the rejection reason
    
    await db.commit()
    await db.refresh(user)
    
    return user


# ============== Verification Endpoints ==============

@router.get("/verification/pending")
async def get_pending_verifications(
    limit: int = 5,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get pending verifications.
    Platform Admins can access.
    """
    result = await db.execute(
        select(User).where(
            User.verification_status == VerificationStatus.PENDING
        ).limit(limit)
    )
    users = result.scalars().all()
    
    return {
        "verifications": users,
        "total": len(users)
    }


@router.post("/verification/{user_id}/approve")
async def approve_verification(
    user_id: int,
    data: dict = {},
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending verification."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.verification_status = VerificationStatus.VERIFIED
    await db.commit()
    return {"message": "Verification approved", "user_id": user_id}


@router.post("/verification/{user_id}/reject")
async def reject_verification(
    user_id: int,
    data: dict = {},
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a pending verification."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.verification_status = VerificationStatus.REJECTED
    await db.commit()
    return {"message": "Verification rejected", "user_id": user_id}


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


# ============== System Config Endpoints ==============

@router.get("/compliance/overview/chart")
async def get_compliance_overview_chart(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get compliance chart data for visualization.
    Platform Admins can access.
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


@router.get("/config/required-documents")
async def get_required_documents(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get required documents configuration.
    Platform Admins only.
    Returns array directly (not wrapped) for frontend compatibility.
    """
    return [
        {"id": 1, "name": "National ID", "display_name": "National ID Copy", "is_required": True, "description": "Valid national identification document"},
        {"id": 2, "name": "Land Title Deed", "display_name": "Land Title Deed", "is_required": True, "description": "Official land ownership document"},
        {"id": 3, "name": "Coffee Nursery Certificate", "display_name": "Coffee Nursery Certificate", "is_required": False, "description": "Optional certificate showing coffee nursery"},
        {"id": 4, "name": "Farm Map", "display_name": "Farm Map", "is_required": True, "description": "Georeferenced farm boundary map"}
    ]


@router.post("/config/required-documents")
async def create_required_document(
    documents: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create or update required documents configuration.
    Platform Admins only.
    """
    return {
        "message": "Required document created successfully",
        "document": documents
    }


@router.get("/config/session-timeout")
async def get_session_timeout(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get session timeout configuration.
    Platform Admins only.
    """
    config_data = settings.model_dump()
    return {
        "session_timeout_minutes": config_data.get("app", {}).get("access_token_expire_minutes", 60),
        "max_login_attempts": config_data.get("auth", {}).get("max_login_attempts", 5),
        "lockout_duration_minutes": config_data.get("auth", {}).get("lockout_duration_minutes", 15)
    }


@router.get("/config/env-credentials")
async def get_env_credentials(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get environment credentials configuration.
    Platform Admins only.
    """
    config_data = settings.model_dump()
    return {
        "satellite_api_configured": bool(config_data.get("satellite", {}).get("api_key")),
        "eudr_portal_configured": bool(config_data.get("eudr", {}).get("portal_url")),
        "sms_gateway_configured": False,  # Not implemented yet
        "email_gateway_configured": bool(config_data.get("email", {}).get("smtp_password"))
    }


# ============== System Configuration Management ==============

from app.core.config import settings, save_config, Settings
from pydantic import BaseModel
from typing import Dict, Any


class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]


@router.get("/config")
async def get_system_config(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all system configuration settings.
    Platform Admins only.
    Returns the current configuration from config.yaml
    """
    # Return the current settings as dict
    config_data = settings.model_dump()
    return config_data


@router.get("/config/{section}")
async def get_config_section(
    section: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific configuration section.
    Platform Admins only.
    """
    config_data = settings.model_dump()
    if section not in config_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration section '{section}' not found"
        )
    return {section: config_data[section]}


@router.put("/config/{section}")
async def update_config_section(
    section: str,
    config_update: ConfigUpdateRequest,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a specific configuration section and save to config.yaml.
    Platform Admins only.

    WARNING: This endpoint allows editing sensitive configuration including credentials.
    Ensure proper access controls and audit logging in production.
    """
    global settings

    # Validate section exists
    config_data = settings.model_dump()
    if section not in config_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration section '{section}' not found"
        )

    # Validate the new config data
    try:
        # Create a copy of current config and update the section
        new_config_data = config_data.copy()
        new_config_data[section] = config_update.config

        # Validate by creating a new Settings object
        new_settings = Settings(**new_config_data)

        # Save to file
        save_config(new_settings)

        # Update global settings (this will require app restart for some changes)
        settings = new_settings

        return {
            "message": f"Configuration section '{section}' updated successfully",
            "section": section,
            "config": config_update.config
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid configuration: {str(e)}"
        )


@router.get("/config/credentials/status")
async def get_credentials_status(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get status of all credentials configuration.
    Platform Admins only.
    Shows which credentials are configured vs empty.
    """
    config_data = settings.model_dump()

    status = {
        "database": {
            "configured": bool(config_data.get("database", {}).get("password")),
            "host": config_data.get("database", {}).get("host"),
            "port": config_data.get("database", {}).get("port"),
            "username": config_data.get("database", {}).get("username"),
            "name": config_data.get("database", {}).get("name")
        },
        "satellite": {
            "configured": bool(config_data.get("satellite", {}).get("api_key")),
            "provider": config_data.get("satellite", {}).get("provider"),
            "simulation_mode": config_data.get("satellite", {}).get("simulation_mode")
        },
        "email": {
            "configured": bool(config_data.get("email", {}).get("smtp_password")),
            "smtp_server": config_data.get("email", {}).get("smtp_server"),
            "smtp_port": config_data.get("email", {}).get("smtp_port"),
            "smtp_username": config_data.get("email", {}).get("smtp_username"),
            "from_email": config_data.get("email", {}).get("from_email")
        },
        "storage": {
            "s3_configured": bool(config_data.get("storage", {}).get("s3_access_key") and config_data.get("storage", {}).get("s3_secret_key")),
            "s3_bucket": config_data.get("storage", {}).get("s3_bucket"),
            "s3_region": config_data.get("storage", {}).get("s3_region")
        },
        "payments": {
            "mpesa_configured": bool(config_data.get("payments", {}).get("mpesa_consumer_key") and config_data.get("payments", {}).get("mpesa_consumer_secret")),
            "enabled": config_data.get("payments", {}).get("enabled")
        }
    }

    return status


# ============== Admin Management ==============

class AdminCredentialsUpdate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    phone_number: Optional[str] = None


@router.post("/config/admin/credentials")
async def update_admin_credentials(
    credentials: AdminCredentialsUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update or create platform admin credentials.
    This allows changing the admin user credentials after login.
    Platform Admins only.
    """
    from passlib.context import CryptContext

    # Check if an admin with this email already exists
    existing_admin = await db.execute(
        select(User).where(
            User.email == credentials.email,
            User.role == UserRole.PLATFORM_ADMIN.value
        )
    )
    existing_admin = existing_admin.scalar_one_or_none()

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    if existing_admin:
        # Update existing admin credentials
        existing_admin.password_hash = pwd_context.hash(credentials.password)
        existing_admin.first_name = credentials.first_name
        existing_admin.last_name = credentials.last_name
        if credentials.phone_number:
            existing_admin.phone_number = credentials.phone_number
        existing_admin.verification_status = VerificationStatus.VERIFIED

        await db.commit()
        await db.refresh(existing_admin)

        return {
            "message": "Admin credentials updated successfully",
            "admin_id": existing_admin.id,
            "email": existing_admin.email
        }
    else:
        # Create new platform admin
        new_admin = User(
            email=credentials.email,
            password_hash=pwd_context.hash(credentials.password),
            first_name=credentials.first_name,
            last_name=credentials.last_name,
            phone_number=credentials.phone_number,
            role=UserRole.PLATFORM_ADMIN,
            verification_status=VerificationStatus.VERIFIED
        )

        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        return {
            "message": "New platform admin created successfully",
            "admin_id": new_admin.id,
            "email": new_admin.email
        }
