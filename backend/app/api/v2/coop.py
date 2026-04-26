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
from app.core.auth import get_current_user, require_coop_admin, require_plotra_admin
from app.models.user import User, VerificationStatus, CooperativeMember, Cooperative, UserRole
from app.models.farm import Farm
from app.models.traceability import Delivery, Batch, QualityGrade, DeliveryStatus
from app.api.schemas import (
    UserResponse, DeliveryCreate, DeliveryResponse,
    BatchCreate, BatchResponse, MessageResponse,
    CooperativeCreate, CooperativeResponse, CooperativeAdminCreate,
    CooperativeUserAddRequest, CooperativeUserResponse, CooperativeUserRoleEnum
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


@router.get("/cooperatives/search")
async def search_cooperatives(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Search cooperatives by code (partial match).
    Used during farmer registration to find cooperatives.
    """
    # Search for cooperatives where code contains the search term (case-insensitive)
    result = await db.execute(
        select(Cooperative).where(
            Cooperative.code.ilike(f"%{code}%")
        ).limit(10)
    )
    cooperatives = result.scalars().all()
    
    return {
        "cooperatives": [
            {
                "id": coop.id,
                "code": coop.code,
                "name": coop.name,
                "county": coop.county
            }
            for coop in cooperatives
        ]
    }


@router.post("/cooperatives", response_model=CooperativeResponse, status_code=status.HTTP_201_CREATED)
async def create_cooperative(
    coop_data: CooperativeCreate,
    admin_data: CooperativeAdminCreate,
    current_user: User = Depends(require_plotra_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new cooperative with a cooperative admin user.
    Plotra admins can create cooperatives and their initial admin.
    """
    # Check if cooperative with registration number already exists
    if coop_data.registration_number:
        existing_result = await db.execute(
            select(Cooperative).where(Cooperative.registration_number == coop_data.registration_number)
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cooperative with this registration number already exists"
            )
    
    # Generate unique cooperative code in format PTC/YEAR/001
    from datetime import datetime
    current_year = datetime.utcnow().year
    
    # Find the highest existing sequential number for the current year
    year_prefix = f"PTC/{current_year}/"
    existing_codes_query = await db.execute(
        select(Cooperative.code).where(Cooperative.code.like(f"{year_prefix}%"))
    )
    existing_codes = existing_codes_query.scalars().all()
    
    # Extract sequential numbers and find the highest
    max_seq = 0
    for existing_code in existing_codes:
        try:
            seq_part = existing_code.split("/")[-1]
            seq_num = int(seq_part)
            if seq_num > max_seq:
                max_seq = seq_num
        except (ValueError, IndexError):
            continue
    
    # Generate next sequential number
    next_seq = max_seq + 1
    code = f"{year_prefix}{next_seq:03d}"
            
    # Create cooperative
    cooperative = Cooperative(
        name=coop_data.name,
        code=code,
        registration_number=coop_data.registration_number,
        tax_id=coop_data.tax_id,
        email=coop_data.email,
        phone=coop_data.phone,
        address=coop_data.address,
        country=coop_data.country,
        county=coop_data.county,
        district=coop_data.district,
        subcounty=coop_data.subcounty,
        ward=coop_data.ward,
        cooperative_type=coop_data.cooperative_type,
        establishment_date=coop_data.establishment_date,
        member_count=0,  # Auto-calculated from linked farmers
        contact_person=coop_data.contact_person,
        contact_person_phone=coop_data.contact_person_phone,
        contact_person_email=coop_data.contact_person_email,
        legal_status=coop_data.legal_status,
        governing_document=coop_data.governing_document
    )
    
    db.add(cooperative)
    await db.commit()
    await db.refresh(cooperative)
    
    # Create cooperative admin user
    from app.core.auth import get_password_hash
    
    admin_user = User(
        email=admin_data.email,
        password_hash=get_password_hash(admin_data.password),
        first_name=admin_data.first_name,
        last_name=admin_data.last_name,
        phone=admin_data.phone_number,
        role=UserRole.COOPERATIVE_OFFICER,
        country=coop_data.country,
        county=coop_data.county,
        district=coop_data.district,
        subcounty=coop_data.subcounty,
        ward=coop_data.ward,
        status="active"
    )
    
    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)
    
    # Make admin user the primary officer of the cooperative
    cooperative.primary_officer_id = admin_user.id
    await db.commit()
    await db.refresh(cooperative)
    
    # Add admin user as a cooperative member with admin role
    admin_membership = CooperativeMember(
        user_id=admin_user.id,
        cooperative_id=cooperative.id,
        cooperative_role="admin",
        is_active=True
    )
    
    db.add(admin_membership)
    await db.commit()
    
    # Calculate member_count dynamically from linked farmers
    member_count_result = await db.execute(
        select(func.count(CooperativeMember.id)).where(
            CooperativeMember.cooperative_id == cooperative.id,
            CooperativeMember.is_active == True
        )
    )
    cooperative.member_count = member_count_result.scalar() or 0
    await db.commit()
    
    return cooperative


@router.get("/cooperatives/{coop_id}", response_model=CooperativeResponse)
async def get_cooperative_details(
    coop_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific cooperative.
    """
    cooperative = await db.get(Cooperative, coop_id)
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Check access permissions
    if not current_user.can_access_cooperative(coop_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this cooperative"
        )
    
    # Calculate member_count dynamically from linked farmers
    member_count_result = await db.execute(
        select(func.count(CooperativeMember.id)).where(
            CooperativeMember.cooperative_id == coop_id,
            CooperativeMember.is_active == True
        )
    )
    cooperative.member_count = member_count_result.scalar() or 0
    await db.commit()
    
    return cooperative


@router.put("/cooperatives/{coop_id}", response_model=CooperativeResponse)
async def update_cooperative(
    coop_id: str,
    coop_data: CooperativeCreate,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update cooperative information.
    Cooperative admins can update their cooperative's details.
    """
    cooperative = await db.get(Cooperative, coop_id)
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Check access permissions
    if not current_user.can_access_cooperative(coop_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this cooperative"
        )
    
    # Update cooperative details
    for key, value in coop_data.dict(exclude_unset=True).items():
        setattr(cooperative, key, value)
    
    await db.commit()
    await db.refresh(cooperative)
    
    # Calculate member_count dynamically from linked farmers
    member_count_result = await db.execute(
        select(func.count(CooperativeMember.id)).where(
            CooperativeMember.cooperative_id == coop_id,
            CooperativeMember.is_active == True
        )
    )
    cooperative.member_count = member_count_result.scalar() or 0
    await db.commit()
    
    return cooperative


@router.post("/cooperatives/{coop_id}/users", response_model=CooperativeUserResponse, status_code=status.HTTP_201_CREATED)
async def add_cooperative_user(
    coop_id: str,
    user_data: CooperativeUserAddRequest,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a user to a cooperative with specific role.
    Cooperative admins can add users with various roles.
    """
    cooperative = await db.get(Cooperative, coop_id)
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Check if current user has permission to manage users in this cooperative
    if not current_user.can_access_cooperative(coop_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage users in this cooperative"
        )
    
    # Check if user exists
    user = await db.get(User, user_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is already a member
    existing_result = await db.execute(
        select(CooperativeMember).where(
            CooperativeMember.user_id == user_data.user_id,
            CooperativeMember.cooperative_id == coop_id
        )
    )
    existing_membership = existing_result.scalar_one_or_none()
    
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this cooperative"
        )
    
    # Create membership
    membership = CooperativeMember(
        user_id=user_data.user_id,
        cooperative_id=coop_id,
        cooperative_role=user_data.cooperative_role,
        membership_number=user_data.membership_number,
        is_active=user_data.is_active
    )
    
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    
    # Return user with cooperative role information
    return CooperativeUserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone,
        role=user.role,
        cooperative_role=membership.cooperative_role,
        membership_number=membership.membership_number,
        is_active=membership.is_active,
        joined_at=membership.created_at
    )


@router.get("/cooperatives/{coop_id}/users", response_model=List[CooperativeUserResponse])
async def get_cooperative_users(
    coop_id: str,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all users in a cooperative with their roles.
    """
    cooperative = await db.get(Cooperative, coop_id)
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Check access permissions
    if not current_user.can_access_cooperative(coop_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this cooperative"
        )
    
    # Get all members with their roles
    members_result = await db.execute(
        select(CooperativeMember).where(CooperativeMember.cooperative_id == coop_id)
    )
    members = members_result.scalars().all()
    
    # Fetch user details
    user_ids = [m.user_id for m in members]
    users_result = await db.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users = {u.id: u for u in users_result.scalars().all()}
    
    # Prepare response
    cooperative_users = []
    for membership in members:
        user = users.get(membership.user_id)
        if user:
            cooperative_users.append(
                CooperativeUserResponse(
                    id=str(user.id),
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    phone_number=user.phone,
                    role=user.role,
                    cooperative_role=membership.cooperative_role,
                    membership_number=membership.membership_number,
                    is_active=membership.is_active,
                    joined_at=membership.created_at
                )
            )
    
    return cooperative_users


@router.put("/cooperatives/{coop_id}/users/{user_id}", response_model=CooperativeUserResponse)
async def update_cooperative_user_role(
    coop_id: str,
    user_id: int,
    role_data: dict,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a user's role in a cooperative.
    """
    cooperative = await db.get(Cooperative, coop_id)
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Check access permissions
    if not current_user.can_access_cooperative(coop_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage users in this cooperative"
        )
    
    # Find the membership
    membership_result = await db.execute(
        select(CooperativeMember).where(
            CooperativeMember.user_id == user_id,
            CooperativeMember.cooperative_id == coop_id
        )
    )
    membership = membership_result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this cooperative"
        )
    
    # Update role
    if "cooperative_role" in role_data:
        membership.cooperative_role = role_data["cooperative_role"]
    
    if "is_active" in role_data:
        membership.is_active = role_data["is_active"]
    
    if "membership_number" in role_data:
        membership.membership_number = role_data["membership_number"]
    
    await db.commit()
    await db.refresh(membership)
    
    # Get user details
    user = await db.get(User, user_id)
    
    return CooperativeUserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone,
        role=user.role,
        cooperative_role=membership.cooperative_role,
        membership_number=membership.membership_number,
        is_active=membership.is_active,
        joined_at=membership.created_at
    )


@router.delete("/cooperatives/{coop_id}/users/{user_id}", response_model=MessageResponse)
async def remove_cooperative_user(
    coop_id: str,
    user_id: int,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a user from a cooperative.
    """
    cooperative = await db.get(Cooperative, coop_id)
    if not cooperative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cooperative not found"
        )
    
    # Check access permissions
    if not current_user.can_access_cooperative(coop_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage users in this cooperative"
        )
    
    # Find the membership
    membership_result = await db.execute(
        select(CooperativeMember).where(
            CooperativeMember.user_id == user_id,
            CooperativeMember.cooperative_id == coop_id
        )
    )
    membership = membership_result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this cooperative"
        )
    
    # Cannot remove primary officer
    if cooperative.primary_officer_id == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the primary officer of the cooperative"
        )
    
    await db.delete(membership)
    await db.commit()
    
    return {"message": "User removed from cooperative successfully"}


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
        select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
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
        select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
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


@router.get("/farmers/pending")
async def get_coop_pending_farmers(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get farmers pending coop review (coop_status is null/empty)."""
    # Find cooperative via primary_officer_id or cooperative_id field
    coop_id = getattr(current_user, 'cooperative_id', None)
    if not coop_id:
        coop_result = await db.execute(
            select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
        )
        coop = coop_result.scalar_one_or_none()
        coop_id = str(coop.id) if coop else None

    query = select(User).where(
        User.role == UserRole.FARMER,
        (User.coop_status == None) | (User.coop_status == 'pending')
    )
    if coop_id:
        # Filter to farmers in this cooperative
        farmer_ids_result = await db.execute(
            select(CooperativeMember.user_id).where(
                CooperativeMember.cooperative_id == coop_id,
                CooperativeMember.cooperative_role == 'member'
            )
        )
        farmer_ids = [r for r in farmer_ids_result.scalars().all()]
        if farmer_ids:
            query = query.where(User.id.in_(farmer_ids))
        else:
            return []

    query = query.order_by(User.created_at.desc())
    result = await db.execute(query)
    farmers = result.scalars().all()
    return [
        {
            "id": f.id,
            "first_name": f.first_name,
            "last_name": f.last_name,
            "email": f.email,
            "phone": f.phone,
            "national_id": getattr(f, 'national_id', None),
            "county": f.county,
            "verification_status": f.verification_status.value if hasattr(f.verification_status, 'value') else str(f.verification_status),
            "coop_status": f.coop_status,
            "coop_verified_by_name": f.coop_verified_by_name,
            "coop_verified_at": f.coop_verified_at.isoformat() if f.coop_verified_at else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in farmers
    ]


@router.patch("/farmers/{farmer_id}/approve")
async def coop_approve_farmer(
    farmer_id: str,
    body: dict = {},
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Cooperative approves a farmer (member verification)."""
    from datetime import datetime
    from app.models.notification import Notification
    farmer = await db.get(User, farmer_id)
    if not farmer or farmer.role.value != 'farmer':
        raise HTTPException(status_code=404, detail="Farmer not found")
    farmer.coop_status = 'coop_approved'
    farmer.coop_verified_by_name = current_user.first_name + ' ' + current_user.last_name
    farmer.coop_verified_at = datetime.utcnow()
    farmer.coop_notes = body.get('reason', '') if isinstance(body, dict) else ''
    notif = Notification(
        id=str(__import__('uuid').uuid4()),
        recipient_id=farmer.id,
        title='Cooperative Verification Approved',
        message=f'Your account has been verified by the cooperative{(": " + farmer.coop_notes) if farmer.coop_notes else "."}',
        type='success',
        reference_type='farmer',
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farmer approved by cooperative", "coop_status": "coop_approved"}


@router.patch("/farmers/{farmer_id}/reject")
async def coop_reject_farmer(
    farmer_id: str,
    body: dict = {},
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Cooperative rejects a farmer (member verification)."""
    from datetime import datetime
    from app.models.notification import Notification
    farmer = await db.get(User, farmer_id)
    if not farmer or farmer.role.value != 'farmer':
        raise HTTPException(status_code=404, detail="Farmer not found")
    reason = body.get('reason', '') if isinstance(body, dict) else ''
    farmer.coop_status = 'coop_rejected'
    farmer.coop_verified_by_name = current_user.first_name + ' ' + current_user.last_name
    farmer.coop_verified_at = datetime.utcnow()
    farmer.coop_notes = reason
    notif = Notification(
        id=str(__import__('uuid').uuid4()),
        recipient_id=farmer.id,
        title='Cooperative Verification Rejected',
        message=f'Your account verification was rejected by the cooperative{(": " + reason) if reason else "."}',
        type='error',
        reference_type='farmer',
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farmer rejected by cooperative", "coop_status": "coop_rejected"}


@router.patch("/farms/{farm_id}/approve")
async def coop_approve_farm(
    farm_id: str,
    reason: str = "",
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Cooperative approves a farmer's farm — moves it to coop_approved stage."""
    from datetime import datetime
    from app.models.notification import Notification
    result = await db.execute(select(Farm).where(Farm.id == farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    farm.coop_status = "coop_approved"
    farm.verification_status = "coop_approved"
    farm.coop_verified_by_id = current_user.id
    farm.coop_verified_at = datetime.utcnow()
    farm.coop_notes = reason or None
    notif = Notification(
        recipient_id=farm.owner_id,
        title="Farm Approved by Cooperative",
        message=f"Your farm '{farm.farm_name}' has been approved by your cooperative. {reason or ''}".strip(),
        type="success",
        reference_id=farm_id,
        reference_type="farm"
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farm approved by cooperative", "verification_status": farm.verification_status}


@router.patch("/farms/{farm_id}/reject")
async def coop_reject_farm(
    farm_id: str,
    reason: str = "",
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Cooperative rejects a farmer's farm with reason."""
    from datetime import datetime
    from app.models.notification import Notification
    result = await db.execute(select(Farm).where(Farm.id == farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    farm.coop_status = "coop_rejected"
    farm.verification_status = "rejected"
    farm.coop_verified_by_id = current_user.id
    farm.coop_verified_at = datetime.utcnow()
    farm.coop_notes = reason or "Rejected by cooperative"
    farm.notes = f"Rejected by cooperative: {reason}" if reason else "Rejected by cooperative"
    notif = Notification(
        recipient_id=farm.owner_id,
        title="Farm Rejected by Cooperative",
        message=f"Your farm '{farm.farm_name}' was rejected by your cooperative. Reason: {reason or 'No reason provided'}",
        type="error",
        reference_id=farm_id,
        reference_type="farm"
    )
    db.add(notif)
    await db.commit()
    return {"message": "Farm rejected by cooperative", "verification_status": farm.verification_status}


@router.get("/farms")
async def get_coop_farms(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all farms for this cooperative with optional status filter."""
    coop_id = getattr(current_user, 'cooperative_id', None)
    if not coop_id:
        coop_result = await db.execute(
            select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
        )
        coop = coop_result.scalar_one_or_none()
        coop_id = str(coop.id) if coop else None

    query = select(Farm).join(User, Farm.owner_id == User.id).where(
        Farm.deleted_at == None,
        User.role == "farmer"
    )
    if coop_id:
        query = query.where(Farm.cooperative_id == coop_id)
    if status_filter:
        query = query.where(Farm.verification_status == status_filter)

    result = await db.execute(query.order_by(Farm.created_at.desc()))
    farms = result.scalars().all()

    output = []
    for f in farms:
        owner_res = await db.execute(select(User).where(User.id == f.owner_id))
        owner = owner_res.scalar_one_or_none()
        output.append({
            "id": f.id,
            "farm_name": f.farm_name,
            "farmer_name": f"{owner.first_name} {owner.last_name}" if owner else "Unknown",
            "farmer_phone": owner.phone if owner else None,
            "total_area_hectares": f.total_area_hectares,
            "verification_status": f.verification_status,
            "coop_status": f.coop_status,
            "coop_notes": f.coop_notes,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return {"farms": output, "total": len(output)}


@router.get("/farms/pending")
async def get_pending_farms(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get farms pending coop verification for this cooperative."""
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
    )
    coop = coop_result.scalar_one_or_none()
    coop_id = coop.id if coop else None

    query = select(Farm).join(User, Farm.owner_id == User.id).where(
        Farm.verification_status.in_(["pending", "coop_approved", "draft"]),
        Farm.deleted_at == None,
        User.role == "farmer"
    )
    if coop_id:
        query = query.where(Farm.cooperative_id == coop_id)

    result = await db.execute(query.order_by(Farm.created_at.desc()))
    farms = result.scalars().all()

    output = []
    for f in farms:
        owner_res = await db.execute(select(User).where(User.id == f.owner_id))
        owner = owner_res.scalar_one_or_none()
        output.append({
            "id": f.id,
            "farm_name": f.farm_name,
            "farmer_name": f"{owner.first_name} {owner.last_name}" if owner else "Unknown",
            "farmer_phone": owner.phone if owner else None,
            "total_area_hectares": f.total_area_hectares,
            "verification_status": f.verification_status,
            "coop_status": f.coop_status,
            "coop_notes": f.coop_notes,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return output


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
        select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
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
        select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
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


@router.get("/me")
async def get_my_cooperative(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Return the cooperative linked to the current officer."""
    coop_id = getattr(current_user, 'cooperative_id', None)
    if not coop_id:
        coop_result = await db.execute(
            select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
        )
        coop = coop_result.scalar_one_or_none()
        coop_id = str(coop.id) if coop else None
    if not coop_id:
        raise HTTPException(status_code=404, detail="No cooperative linked to your account")
    return {"cooperative_id": coop_id}


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
        select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
    )
    cooperative = coop_result.scalar_one_or_none()
    
    member_count = 0
    verified_farms = 0
    pending_verification = 0
    draft_farms = 0
    total_weight = 0.0
    compliant_farms = 0

    if cooperative:
        members_count_result = await db.execute(
            select(func.count()).select_from(CooperativeMember).where(CooperativeMember.cooperative_id == cooperative.id)
        )
        member_count = members_count_result.scalar() or 0

    # Farm counts by verification_status (platform-wide for coop context)
    verified_farms    = (await db.execute(select(func.count()).select_from(Farm).where(Farm.verification_status == 'verified'))).scalar() or 0
    pending_verification = (await db.execute(select(func.count()).select_from(Farm).where(Farm.verification_status == 'pending'))).scalar() or 0
    draft_farms       = (await db.execute(select(func.count()).select_from(Farm).where(Farm.verification_status == 'draft'))).scalar() or 0
    compliant_farms   = verified_farms  # verified = compliant for display purposes

    # Total weight delivered
    weight_result = await db.execute(select(func.coalesce(func.sum(Delivery.net_weight_kg), 0.0)))
    total_weight = float(weight_result.scalar() or 0.0)

    return {
        "daily_deliveries": total_deliveries,
        "total_deliveries": total_deliveries,
        "member_count": member_count,
        "total_members": member_count,
        "verified_farms": verified_farms,
        "compliant_farms": compliant_farms,
        "pending_verification": pending_verification,
        "draft_farms": draft_farms,
        "total_weight_kg": round(total_weight, 2),
        "quality_index": "AA / AB",
        "batch_status": "03 Ready"
    }
