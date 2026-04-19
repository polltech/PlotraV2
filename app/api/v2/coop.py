"""
Plotra Platform - Cooperative API Endpoints (Tier 2)
Member verification, delivery recording, and batch management
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user, require_coop_admin
from app.models.user import User, VerificationStatus, CooperativeMember, Cooperative, UserRole
from app.models.farm import Farm
from app.models.traceability import Delivery, Batch, QualityGrade, DeliveryStatus
from app.api.schemas import (
    UserResponse, DeliveryCreate, DeliveryResponse,
    BatchCreate, BatchResponse, MessageResponse
)

from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(tags=["Tier 2: Cooperative APIs"])


@router.get("/cooperatives/validate-code")
async def validate_cooperative_code(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate a cooperative code and return the cooperative ID.
    Used during farmer registration.
    """
    # Find cooperative by code
    result = await db.execute(
        select(Cooperative).where(Cooperative.code == code.upper())
    )
    cooperative = result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid cooperative code"
        )
    
    return {
        "valid": True,
        "cooperative_id": cooperative.id,
        "cooperative_name": cooperative.name
    }


@router.get("/members", response_model=List[UserResponse])
async def get_coop_members(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all farmer members of the cooperative.
    """
    # Get cooperative membership for current user
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.primary_admin_id == current_user.id)
    )
    cooperative = coop_result.scalar_one_or_none()
    
    if not cooperative:
        # Try to get through membership
        member_result = await db.execute(
            select(CooperativeMember).where(CooperativeMember.user_id == current_user.id)
        )
        membership = member_result.scalar_one_or_none()
        
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to any cooperative"
            )
        
        cooperative = await db.get(Cooperative, membership.cooperative_id)
    
    # Get members
    members_result = await db.execute(
        select(CooperativeMember).where(CooperativeMember.cooperative_id == cooperative.id)
    )
    members = members_result.scalars().all()
    
    # Fetch user details
    user_ids = [m.user_id for m in members]
    users_result = await db.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users = {u.id: u for u in users_result.scalars().all()}
    
    return [users[m.user_id] for m in members if m.user_id in users]


class MemberAddRequest(BaseModel):
    """Request to add a member to cooperative"""
    user_id: int
    membership_number: Optional[str] = None
    cooperative_role: str = "member"


@router.post("/members", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def add_coop_member(
    member_data: MemberAddRequest,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Add an existing user as a member of the cooperative.
    Coop Admins can add farmers to their cooperative.
    """
    # Get cooperative
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.primary_admin_id == current_user.id)
    )
    cooperative = coop_result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned as a cooperative admin"
        )
    
    # Check if user exists
    user = await db.get(User, member_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if already a member
    existing_result = await db.execute(
        select(CooperativeMember).where(
            CooperativeMember.user_id == member_data.user_id,
            CooperativeMember.cooperative_id == cooperative.id
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this cooperative"
        )
    
    # Create membership
    membership = CooperativeMember(
        user_id=member_data.user_id,
        cooperative_id=cooperative.id,
        membership_number=member_data.membership_number,
        cooperative_role=member_data.cooperative_role
    )
    
    db.add(membership)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.put("/members/{user_id}/verify", response_model=UserResponse)
async def verify_farmer_member(
    user_id: int,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a farmer member's KYC and farm data.
    Coop Admins can verify member submissions.
    """
    # Get user
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
    
    # Update verification status
    user.verification_status = VerificationStatus.VERIFIED
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/deliveries", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
async def record_delivery(
    delivery_data: DeliveryCreate,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Record a coffee delivery from a farmer.
    Creates weighing records and initial quality assessment.
    """
    # Generate delivery number
    delivery_number = f"DEL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    # Calculate net weight
    net_weight = delivery_data.gross_weight_kg - delivery_data.tare_weight_kg
    
    # Create delivery
    delivery = Delivery(
        delivery_number=delivery_number,
        farm_id=delivery_data.farm_id,
        gross_weight_kg=delivery_data.gross_weight_kg,
        tare_weight_kg=delivery_data.tare_weight_kg,
        net_weight_kg=net_weight,
        quality_grade=delivery_data.quality_grade,
        moisture_content=delivery_data.moisture_content,
        cherry_type=delivery_data.cherry_type,
        picking_date=delivery_data.picking_date,
        status=DeliveryStatus.PENDING,
        received_by_id=current_user.id
    )
    
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)
    
    return delivery


@router.get("/deliveries", response_model=List[DeliveryResponse])
async def get_deliveries(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get coffee deliveries for the cooperative.
    Supports date range and status filtering.
    """
    query = select(Delivery)
    
    if start_date:
        query = query.where(Delivery.created_at >= start_date)
    if end_date:
        query = query.where(Delivery.created_at <= end_date)
    if status_filter:
        query = query.where(Delivery.status == DeliveryStatus(status_filter))
    
    query = query.order_by(Delivery.created_at.desc())
    
    result = await db.execute(query)
    deliveries = result.scalars().all()
    
    return deliveries


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    batch_data: BatchCreate,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a coffee batch from multiple deliveries.
    Batches are used for traceability and export certification.
    """
    # Get cooperative
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.primary_admin_id == current_user.id)
    )
    cooperative = coop_result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned as a cooperative admin"
        )
    
    # Get deliveries
    if batch_data.delivery_ids:
        deliveries_result = await db.execute(
            select(Delivery).where(Delivery.id.in_(batch_data.delivery_ids))
        )
        deliveries = deliveries_result.scalars().all()
        
        total_weight = sum(d.net_weight_kg for d in deliveries)
    else:
        deliveries = []
        total_weight = 0
    
    # Create batch
    batch = Batch(
        cooperative_id=cooperative.id,
        batch_number=batch_data.batch_number,
        crop_year=batch_data.crop_year,
        harvest_start_date=batch_data.harvest_start_date,
        harvest_end_date=batch_data.harvest_end_date,
        processing_method=batch_data.processing_method,
        total_weight_kg=total_weight,
        compliance_status="Under Review"
    )
    
    db.add(batch)
    await db.flush()
    
    # Update delivery batch references
    for delivery in deliveries:
        delivery.batch_id = batch.id
    
    await db.commit()
    await db.refresh(batch)
    
    return batch


@router.get("/batches", response_model=List[BatchResponse])
async def get_batches(
    crop_year: Optional[int] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get batches for the cooperative.
    """
    # Get cooperative
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.primary_admin_id == current_user.id)
    )
    cooperative = coop_result.scalar_one_or_none()
    
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned as a cooperative admin"
        )
    
    query = select(Batch).where(Batch.cooperative_id == cooperative.id)
    
    if crop_year:
        query = query.where(Batch.crop_year == crop_year)
    
    query = query.order_by(Batch.created_at.desc())
    
    result = await db.execute(query)
    batches = result.scalars().all()
    
    return batches


@router.get("/batches/{batch_id}/traceability")
async def get_batch_traceability(
    batch_id: int,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full traceability data for a batch.
    Returns detailed information about farm origins, deliveries, and compliance.
    """
    batch = await db.get(Batch, batch_id)
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Get deliveries
    deliveries_result = await db.execute(
        select(Delivery).where(Delivery.batch_id == batch_id)
    )
    deliveries = deliveries_result.scalars().all()
    
    # Get farm details
    farm_ids = list(set(d.farm_id for d in deliveries))
    farms_result = await db.execute(
        select(Farm).where(Farm.id.in_(farm_ids))
    )
    farms = {f.id: f for f in farms_result.scalars().all()}
    
    # Build traceability data
    traceability = {
        "batch": {
            "batch_number": batch.batch_number,
            "crop_year": batch.crop_year,
            "total_weight_kg": batch.total_weight_kg,
            "quality_grade": batch.quality_grade,
            "compliance_status": batch.compliance_status
        },
        "deliveries": [
            {
                "delivery_number": d.delivery_number,
                "net_weight_kg": d.net_weight_kg,
                "quality_grade": d.quality_grade,
                "farm": farms.get(d.farm_id).farm_name if farms.get(d.farm_id) else None
            }
            for d in deliveries
        ],
        "total_deliveries": len(deliveries),
        "generated_at": datetime.utcnow().isoformat()
    }
    
    return traceability


@router.get("/stats")
async def get_coop_stats(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cooperative's operational statistics.
    """
    # Get total deliveries
    deliveries_count = await db.execute(select(func.count()).select_from(Delivery))
    total_deliveries = deliveries_count.scalar() or 0
    
    # Get member count
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.primary_admin_id == current_user.id)
    )
    cooperative = coop_result.scalar_one_or_none()
    
    member_count = 0
    if cooperative:
        members_count_result = await db.execute(
            select(func.count()).select_from(CooperativeMember).where(CooperativeMember.cooperative_id == cooperative.id)
        )
        member_count = members_count_result.scalar() or 0
        
    return {
        "daily_deliveries": total_deliveries, # Simplified
        "member_count": member_count,
        "quality_index": "AA / AB",
        "batch_status": "03 Ready"
    }
