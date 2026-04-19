"""
Plotra Platform - Sustainability & Incentive API Endpoints
Layers 3-7: Practice Logs, Incentives, Payments, Carbon
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user, require_farmer, require_coop_admin, require_platform_admin
from app.models.user import User, UserRole
from app.models.farm import Farm, FarmParcel, LandParcel
from app.models.traceability import Delivery
from app.models.sustainability import (
    PracticeLog,
    TransitionEvent,
    BiomassLedger,
    IncentiveRule,
    IncentiveClaim,
    PaymentEscrow,
    DigitalSignature,
    ImpactClaim,
    DigitalProductPassport,
    CarbonProject,
    CarbonToken,
    PracticeState,
    TransitionEventType,
    IncentiveType,
    PayoutStatus,
    ImpactClaimType,
    CarbonProjectStatus,
)
from app.api.schemas import MessageResponse

router = APIRouter(tags=["Sustainability & Incentives"])


# ==================== LAYER 1 & 3: PRACTICE LOGS ====================

@router.post("/practice-log", status_code=status.HTTP_201_CREATED)
async def create_practice_log(
    parcel_id: int,
    practice_type: str,
    practice_date: datetime,
    description: Optional[str] = None,
    inputs_used: Optional[dict] = None,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    method: Optional[str] = None,
    labor_hours: Optional[float] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Record an agricultural practice (pruning, harvesting, intercropping).
    Layer 1: Practice logs for satellite cross-reference.
    """
    # Verify parcel belongs to user's farm
    parcel = await db.get(FarmParcel, parcel_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    farm = await db.get(Farm, parcel.farm_id)
    if farm.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    practice_log = PracticeLog(
        parcel_id=parcel_id,
        practice_type=practice_type,
        practice_date=practice_date,
        description=description,
        inputs_used=inputs_used,
        quantity=quantity,
        unit=unit,
        method=method,
        labor_hours=labor_hours,
        latitude=latitude,
        longitude=longitude
    )
    
    db.add(practice_log)
    await db.commit()
    await db.refresh(practice_log)
    
    return {"id": practice_log.id, "status": "created"}


@router.get("/practice-logs")
async def get_practice_logs(
    parcel_id: Optional[int] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get practice logs for user's parcels."""
    query = select(PracticeLog).join(FarmParcel).join(Farm).where(Farm.owner_id == current_user.id)
    
    if parcel_id:
        query = query.where(PracticeLog.parcel_id == parcel_id)
    
    result = await db.execute(query.order_by(PracticeLog.practice_date.desc()))
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "parcel_id": log.parcel_id,
            "practice_type": log.practice_type,
            "practice_date": log.practice_date.isoformat(),
            "description": log.description
        }
        for log in logs
    ]


# ==================== LAYER 3: TRANSITION EVENTS ====================

@router.post("/transition-event", status_code=status.HTTP_201_CREATED)
async def create_transition_event(
    parcel_id: int,
    event_type: str,
    from_state: str,
    to_state: str,
    description: Optional[str] = None,
    biomass_change_tons: Optional[float] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Record a sustainability practice transition.
    Layer 3: Monocrop → Mixed → Agroforestry.
    """
    parcel = await db.get(FarmParcel, parcel_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    farm = await db.get(Farm, parcel.farm_id)
    if farm.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    transition = TransitionEvent(
        parcel_id=parcel_id,
        event_type=TransitionEventType(event_type),
        from_state=PracticeState(from_state),
        to_state=PracticeState(to_state),
        description=description,
        biomass_change_tons=biomass_change_tons
    )
    
    # Update parcel entry state
    parcel.entry_state = to_state
    
    db.add(transition)
    await db.commit()
    await db.refresh(transition)
    
    return {"id": transition.id, "status": "created", "new_state": to_state}


# ==================== LAYER 4: INCENTIVE RULES ====================

@router.get("/incentive-rules")
async def get_incentive_rules(
    cooperative_id: Optional[int] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get active incentive rules."""
    query = select(IncentiveRule).where(IncentiveRule.is_active == True)
    
    if cooperative_id:
        query = query.where(
            (IncentiveRule.applies_to_cooperative_id == cooperative_id) |
            (IncentiveRule.applies_to_cooperative_id == None)
        )
    
    result = await db.execute(query)
    rules = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "rule_code": r.rule_code,
            "rule_name": r.rule_name,
            "incentive_type": r.incentive_type,
            "percentage_rate": r.percentage_rate,
            "conditions": r.conditions
        }
        for r in rules
    ]


@router.post("/incentive-rules", status_code=status.HTTP_201_CREATED)
async def create_incentive_rule(
    rule_code: str,
    rule_name: str,
    incentive_type: str,
    calculation_type: str,
    conditions: dict,
    percentage_rate: Optional[float] = None,
    base_amount: Optional[float] = None,
    minimum_threshold: Optional[float] = None,
    maximum_amount: Optional[float] = None,
    applies_to_cooperative_id: Optional[int] = None,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create an incentive rule.
    Layer 4: JSON-based conditions for premium calculation.
    Example: IF "heritage_slope" > 0.05 AND "gender" == 'F' THEN +15% Premium
    """
    rule = IncentiveRule(
        rule_code=rule_code,
        rule_name=rule_name,
        incentive_type=IncentiveType(incentive_type),
        calculation_type=calculation_type,
        conditions=conditions,
        percentage_rate=percentage_rate,
        base_amount=base_amount,
        minimum_threshold=minimum_threshold,
        maximum_amount=maximum_amount,
        applies_to_cooperative_id=applies_to_cooperative_id,
        is_active=True
    )
    
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    return {"id": rule.id, "status": "created"}


# ==================== LAYER 4 & 5: INCENTIVE CLAIMS ====================

@router.get("/incentive-claims")
async def get_incentive_claims(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get incentive claims for current farmer."""
    query = select(IncentiveClaim).where(IncentiveClaim.farmer_id == current_user.id)
    
    if status_filter:
        query = query.where(IncentiveClaim.status == status_filter)
    
    result = await db.execute(query.order_by(IncentiveClaim.claim_date.desc()))
    claims = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "claim_date": c.claim_date.isoformat(),
            "total_amount": c.total_amount,
            "currency": c.currency,
            "status": c.status,
            "rule_name": c.rule.rule_name if c.rule else None
        }
        for c in claims
    ]


@router.post("/evaluate-incentives", status_code=status.HTTP_201_CREATED)
async def evaluate_incentives(
    farmer_id: int,
    parcel_id: Optional[int] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Evaluate incentive rules for a farmer.
    Layer 4: Calculate premiums based on conditions.
    """
    # Get active rules
    rules_result = await db.execute(
        select(IncentiveRule).where(IncentiveRule.is_active == True)
    )
    rules = rules_result.scalars().all()
    
    # Get farmer data (simplified - would need satellite data, gender, etc.)
    farmer = await db.get(User, farmer_id)
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    
    created_claims = []
    
    for rule in rules:
        # Evaluate conditions (simplified logic)
        conditions_met = {}
        bonus_amount = 0.0
        
        # Example: Gender incentive
        if "gender" in rule.conditions:
            expected_gender = rule.conditions["gender"]
            conditions_met["gender"] = farmer.gender == expected_gender
            if conditions_met["gender"] and rule.percentage_rate:
                bonus_amount = rule.percentage_rate  # Simplified
        
        if conditions_met and bonus_amount > 0:
            claim = IncentiveClaim(
                farmer_id=farmer_id,
                rule_id=rule.id,
                parcel_id=parcel_id,
                claim_number=f"CLM-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                base_amount=100.0,  # Would be calculated from actual deliveries
                bonus_amount=bonus_amount,
                total_amount=100.0 + bonus_amount,
                conditions_met=conditions_met,
                status="pending"
            )
            db.add(claim)
            created_claims.append(claim)
    
    await db.commit()
    
    return {
        "evaluated": len(rules),
        "claims_created": len(created_claims),
        "farmer_id": farmer_id
    }


# ==================== LAYER 5: PAYMENT ESCROW ====================

@router.get("/escrow")
async def get_escrow_payments(
    status_filter: Optional[str] = None,
    farmer_id: Optional[int] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get payment escrow records for current user."""
    query = select(PaymentEscrow).where(PaymentEscrow.payee_id == current_user.id)
    
    if status_filter:
        query = query.where(PaymentEscrow.status == status_filter)
    if farmer_id:
        query = query.where(PaymentEscrow.payee_id == farmer_id)
    
    result = await db.execute(query.order_by(PaymentEscrow.escrow_date.desc()))
    escrows = result.scalars().all()
    
    return [
        {
            "id": e.id,
            "reference_number": e.reference_number,
            "amount": e.amount,
            "currency": e.currency,
            "status": e.status,
            "escrow_date": e.escrow_date.isoformat(),
            "release_date": e.release_date.isoformat() if e.release_date else None
        }
        for e in escrows
    ]


@router.post("/create-escrow", status_code=status.HTTP_201_CREATED)
async def create_escrow(
    payee_id: int,
    amount: float,
    conditions: dict,
    delivery_id: Optional[int] = None,
    description: Optional[str] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a payment escrow record.
    Layer 5: Triggered by delivery_confirmed + verification_passed.
    """
    payee = await db.get(User, payee_id)
    if not payee:
        raise HTTPException(status_code=404, detail="Payee not found")
    
    escrow = PaymentEscrow(
        reference_number=f"ESC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        payer_id=current_user.id,
        payer_name=current_user.get_full_name(),
        payee_id=payee_id,
        payee_name=payee.get_full_name(),
        payout_recipient_id=payee.payout_recipient_id,
        payout_method=payee.payout_method,
        amount=amount,
        currency="KES",
        conditions=conditions,
        delivery_id=delivery_id,
        status=PayoutStatus.PENDING,
        description=description
    )
    
    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    
    return {"id": escrow.id, "reference_number": escrow.reference_number, "status": "created"}


@router.post("/release-escrow/{escrow_id}")
async def release_escrow(
    escrow_id: int,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Release payment from escrow.
    Layer 5: Conditions met, release to M-Pesa/Wallet.
    """
    escrow = await db.get(PaymentEscrow, escrow_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    
    if escrow.status != PayoutStatus.PENDING:
        raise HTTPException(status_code=400, detail="Escrow not in pending status")
    
    # Update status
    escrow.status = PayoutStatus.RELEASED
    escrow.release_date = datetime.utcnow()
    escrow.payment_reference = f"PAY-{uuid.uuid4().hex[:10].upper()}"
    
    await db.commit()
    
    return {"id": escrow.id, "status": "released", "payment_reference": escrow.payment_reference}


# ==================== LAYER 6: IMPACT CLAIMS ====================

@router.get("/impact-claims")
async def get_impact_claims(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get impact claims for a farm or cooperative."""
    query = select(ImpactClaim)
    
    if entity_type:
        query = query.where(ImpactClaim.entity_type == entity_type)
    if entity_id:
        query = query.where(ImpactClaim.entity_id == entity_id)
    
    result = await db.execute(query.order_by(ImpactClaim.issue_date.desc()))
    claims = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "claim_type": c.claim_type,
            "title": c.title,
            "claim_value": c.claim_value,
            "is_verified": c.is_verified,
            "issue_date": c.issue_date.isoformat()
        }
        for c in claims
    ]


# ==================== LAYER 6: DIGITAL PRODUCT PASSPORT ====================

@router.get("/product-passport/{farm_id}")
async def get_product_passport(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get Digital Product Passport for a farm.
    Layer 6: QR-linked journey showing Heritage → Compliance → Future.
    """
    passport_result = await db.execute(
        select(DigitalProductPassport).where(DigitalProductPassport.farm_id == farm_id)
    )
    passport = passport_result.scalar_one_or_none()
    
    if not passport:
        raise HTTPException(status_code=404, detail="Product passport not found")
    
    return {
        "passport_number": passport.passport_number,
        "product_name": passport.product_name,
        "country_of_origin": passport.country_of_origin,
        "harvest_date": passport.harvest_date.isoformat() if passport.harvest_date else None,
        "certifications": passport.certifications,
        "sustainability_score": passport.sustainability_score,
        "heritage_verified": passport.heritage_verified,
        "eudr_compliant": passport.eudr_compliant,
        "carbon_footprint_kg_co2": passport.carbon_footprint_kg_co2,
        "qr_code_data": passport.qr_code_data
    }


# ==================== LAYER 7: CARBON PROJECTS ====================

@router.get("/carbon-projects")
async def get_carbon_projects(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get carbon projects."""
    query = select(CarbonProject)
    
    if status_filter:
        query = query.where(CarbonProject.status == CarbonProjectStatus(status_filter))
    
    result = await db.execute(query.order_by(CarbonProject.created_at.desc()))
    projects = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "project_name": p.project_name,
            "project_code": p.project_code,
            "total_area_hectares": p.total_area_hectares,
            "current_carbon_tons": p.current_carbon_tons,
            "status": p.status,
            "carbon_standard": p.carbon_standard
        }
        for p in projects
    ]


@router.post("/carbon-projects", status_code=status.HTTP_201_CREATED)
async def create_carbon_project(
    project_name: str,
    project_code: str,
    total_area_hectares: float,
    description: Optional[str] = None,
    carbon_standard: Optional[str] = None,
    methodology: Optional[str] = None,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a carbon project.
    Layer 7: Aggregates micro-scale biomass into tradeable units.
    """
    project = CarbonProject(
        project_name=project_name,
        project_code=project_code,
        description=description,
        carbon_standard=carbon_standard,
        methodology=methodology,
        total_area_hectares=total_area_hectares,
        status=CarbonProjectStatus.DRAFT
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    return {"id": project.id, "project_code": project.project_code, "status": "draft"}


@router.get("/carbon-tokens")
async def get_carbon_tokens(
    farmer_id: Optional[int] = None,
    project_id: Optional[int] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get carbon tokens for farmer or project."""
    query = select(CarbonToken)
    
    if farmer_id:
        query = query.where(CarbonToken.farmer_id == farmer_id)
    if project_id:
        query = query.where(CarbonToken.project_id == project_id)
    
    result = await db.execute(query.order_by(CarbonToken.issue_date.desc()))
    tokens = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "token_id": t.token_id,
            "carbon_tons": t.carbon_tons,
            "carbon_tons_co2": t.carbon_tons_co2,
            "vintage_year": t.vintage_year,
            "status": t.status,
            "price_per_ton_usd": t.price_per_ton_usd
        }
        for t in tokens
    ]


# ==================== DASHBOARD AGGREGATION ====================

@router.get("/dashboard-summary")
async def get_dashboard_summary(
    cooperative_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated sustainability dashboard data.
    Returns: Total Trees, Carbon Stored, Soil Health, Incentives, Recent Practice Logs
    """
    
    from app.models.farm import Farm
    from app.models.user import CooperativeMember
    
    # Determine which farms to query based on user role
    farm_ids = None
    farmer_ids = None
    
    if cooperative_id:
        # Get all farmers in this cooperative
        members_result = await db.execute(
            select(CooperativeMember.user_id).where(CooperativeMember.cooperative_id == str(cooperative_id))
        )
        farmer_ids = [m.user_id for m in members_result.scalars().all()]
        if farmer_ids:
            farms_result = await db.execute(
                select(Farm.id).where(Farm.owner_id.in_(farmer_ids))
            )
            farm_ids = [f.id for f in farms_result.scalars().all()]
    elif current_user.role == UserRole.FARMER:
        # Get current user's farms
        farms_result = await db.execute(
            select(Farm.id).where(Farm.owner_id == current_user.id)
        )
        farm_ids = [f.id for f in farms_result.scalars().all()]
        farmer_ids = [current_user.id]
    
    # Query parcels
    if farm_ids:
        parcels_result = await db.execute(
            select(LandParcel).where(LandParcel.farm_id.in_(farm_ids))
        )
        parcels = parcels_result.scalars().all()
    else:
        parcels = []
    
    # 1. Total Trees - sum of shade_tree_count from all parcels
    total_trees = sum([p.shade_tree_count or 0 for p in parcels])
    
    # 2. Carbon Stored - sum of biomass from biomass ledgers
    parcel_ids = [p.id for p in parcels]
    if parcel_ids:
        ledger_result = await db.execute(
            select(func.sum(BiomassLedger.biomass_tons)).where(
                BiomassLedger.parcel_id.in_(parcel_ids)
            )
        )
        total_carbon = ledger_result.scalar() or 0.0
    else:
        total_carbon = 0.0
    
    # Convert to CO2 equivalent (multiply by 0.5 for carbon to CO2)
    carbon_stored_co2 = total_carbon * 0.5
    
    # 3. Soil Health - average from NDVI and canopy density
    ndvi_values = [p.ndvi_baseline for p in parcels if p.ndvi_baseline is not None]
    canopy_values = [p.canopy_density for p in parcels if p.canopy_density is not None]
    
    if ndvi_values or canopy_values:
        avg_ndvi = sum(ndvi_values) / len(ndvi_values) if ndvi_values else 0
        avg_canopy = sum(canopy_values) / len(canopy_values) if canopy_values else 0
        # Normalize to 0-10 scale (NDVI is typically 0-1, canopy is 0-100%)
        soil_health_score = round((avg_ndvi * 5 + (avg_canopy/100) * 5), 1)
    else:
        soil_health_score = 0.0
    
    # 4. Incentives - sum of approved/paid claims
    incentive_query = select(func.sum(IncentiveClaim.total_amount)).where(
        IncentiveClaim.status.in_(["approved", "paid"])
    )
    
    if farmer_ids:
        incentive_query = incentive_query.where(IncentiveClaim.farmer_id.in_(farmer_ids))
    elif current_user.role == UserRole.FARMER:
        incentive_query = incentive_query.where(IncentiveClaim.farmer_id == current_user.id)
    
    incentive_result = await db.execute(incentive_query)
    total_incentives = incentive_result.scalar() or 0.0
    
    # 5. Recent Practice Logs
    logs_query = select(PracticeLog)
    
    if farm_ids:
        logs_query = logs_query.where(PracticeLog.parcel_id.in_(parcel_ids)) if parcel_ids else logs_query
    elif current_user.role == UserRole.FARMER:
        # Need to join with parcels and farms
        logs_query = select(PracticeLog).join(LandParcel).join(Farm).where(Farm.owner_id == current_user.id)
    
    logs_result = await db.execute(logs_query.order_by(PracticeLog.practice_date.desc()).limit(10))
    practice_logs = logs_result.scalars().all()
    
    recent_logs = []
    for log in practice_logs:
        parcel = await db.get(LandParcel, log.parcel_id)
        parcel_name = parcel.parcel_name or str(parcel.parcel_number) if parcel else "Unknown"
        recent_logs.append({
            "id": log.id,
            "date": log.practice_date.isoformat() if log.practice_date else None,
            "parcel": parcel_name,
            "activity": log.practice_type,
            "description": log.description,
            "status": "verified" if log.is_organic else "pending"
        })
    
    return {
        "total_trees": total_trees,
        "carbon_stored_tons": round(total_carbon, 2),
        "carbon_stored_co2": round(carbon_stored_co2, 2),
        "soil_health_score": soil_health_score,
        "total_incentives_kes": round(total_incentives, 2),
        "recent_practice_logs": recent_logs,
        "parcel_count": len(parcels)
    }
