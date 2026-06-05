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
from app.core.auth import get_current_user, require_coop_admin, require_coop_staff, require_plotra_admin, get_password_hash
from app.models.user import User, VerificationStatus, CooperativeMember, Cooperative, UserRole
from app.models.farm import Farm
from app.models.traceability import (
    Delivery, Batch, QualityGrade, DeliveryStatus, BatchStatus,
    ProcessingLog, ProcessingStepType, Consignment, ConsignmentStatus,
    AuditEvent, AuditEventType,
)
from app.api.schemas import (
    UserResponse, DeliveryCreate, DeliveryResponse,
    BatchCreate, BatchResponse, MessageResponse,
    CooperativeCreate, CooperativeResponse, CooperativeAdminCreate,
    CooperativeUserAddRequest, CooperativeUserResponse, CooperativeUserRoleEnum,
    CreateCoopStaffRequest, CoopStaffResponse,
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
    q: str = "",
    code: str = "",
    db: AsyncSession = Depends(get_db)
):
    """
    Search cooperatives by name OR code (partial match).
    Used during farmer registration to find cooperatives.
    Accepts ?q=<term> (name or code) or legacy ?code=<term>.
    """
    from sqlalchemy import or_
    term = (q or code).strip()
    if not term:
        return {"cooperatives": []}

    result = await db.execute(
        select(Cooperative).where(
            or_(
                Cooperative.code.ilike(f"%{term}%"),
                Cooperative.name.ilike(f"%{term}%"),
            )
        ).limit(10)
    )
    cooperatives = result.scalars().all()

    return {
        "cooperatives": [
            {
                "id": coop.id,
                "code": coop.code,
                "name": coop.name,
                "county": getattr(coop, 'county', None),
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


@router.get("/farmers")
async def get_coop_all_farmers(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all farmers (any coop_status) that are members of this cooperative."""
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if not coop_id:
        return []

    farmer_ids = await _get_farmer_ids_for_coop(coop_id, db)
    if not farmer_ids:
        return []

    result = await db.execute(
        select(User).where(
            User.id.in_(farmer_ids),
            User.role == UserRole.FARMER
        ).order_by(User.created_at.desc())
    )
    farmers = result.scalars().all()

    output = []
    for f in farmers:
        farm_count_res = await db.execute(
            select(func.count(Farm.id)).where(
                Farm.owner_id == f.id, Farm.deleted_at == None
            )
        )
        farm_count = farm_count_res.scalar() or 0
        member_no = await _get_or_generate_member_no(f.id, coop_id, db)
        output.append({
            "id": f.id,
            "first_name": f.first_name,
            "last_name": f.last_name,
            "email": f.email,
            "phone": f.phone,
            "national_id": getattr(f, 'national_id', None),
            "county": f.county,
            "gender": getattr(f, 'gender', None),
            "verification_status": f.verification_status.value if hasattr(f.verification_status, 'value') else str(f.verification_status),
            "coop_status": f.coop_status,
            "update_requested": bool(getattr(f, 'update_requested', False)),
            "update_request_notes": getattr(f, 'update_request_notes', None),
            "update_requested_by_name": getattr(f, 'update_requested_by_name', None),
            "farm_count": farm_count,
            "coop_member_no": member_no,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return output


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
        (User.coop_status == None) | (User.coop_status == 'pending') | (User.coop_status == 'update_requested')
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
            "update_requested": bool(getattr(f, 'update_requested', False)),
            "update_request_notes": getattr(f, 'update_request_notes', None),
            "update_requested_by_name": getattr(f, 'update_requested_by_name', None),
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
    farmer.update_requested = False
    # Generate cooperative member number if not already assigned
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if coop_id:
        await _get_or_generate_member_no(farmer_id, coop_id, db)
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
    farmer.update_requested = False
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


@router.patch("/farmers/{farmer_id}/request-update")
async def coop_request_farmer_update(
    farmer_id: str,
    body: dict = {},
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Request farmer to update/correct their profile before cooperative approves."""
    from datetime import datetime
    from app.models.notification import Notification
    farmer = await db.get(User, farmer_id)
    if not farmer or farmer.role.value != 'farmer':
        raise HTTPException(status_code=404, detail="Farmer not found")
    issue = body.get('issue', '').strip() if isinstance(body, dict) else ''
    if not issue:
        raise HTTPException(status_code=400, detail="Issue description is required")
    farmer.update_requested = True
    farmer.update_requested_by_name = current_user.first_name + ' ' + current_user.last_name
    farmer.update_request_notes = issue
    farmer.update_requested_at = datetime.utcnow()
    farmer.coop_status = 'update_requested'
    notif = Notification(
        id=str(__import__('uuid').uuid4()),
        recipient_id=farmer.id,
        title='Action Required: Update Your Profile',
        message=f'Your cooperative officer has requested you to update your profile before approval.\n\nIssue: {issue}',
        type='warning',
        reference_type='farmer',
    )
    db.add(notif)
    await db.commit()
    return {"message": "Update request sent to farmer"}


@router.patch("/farms/{farm_id}/request-update")
async def coop_request_farm_update(
    farm_id: str,
    body: dict = {},
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Request farmer to update/correct their farm before cooperative approves."""
    from datetime import datetime
    from app.models.notification import Notification
    result = await db.execute(select(Farm).where(Farm.id == farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    issue = body.get('issue', '').strip() if isinstance(body, dict) else ''
    if not issue:
        raise HTTPException(status_code=400, detail="Issue description is required")
    farm.update_requested = True
    farm.update_requested_by_name = current_user.first_name + ' ' + current_user.last_name
    farm.update_request_notes = issue
    farm.update_requested_at = datetime.utcnow()
    farm.coop_status = 'update_requested'
    notif = Notification(
        id=str(__import__('uuid').uuid4()),
        recipient_id=farm.owner_id,
        title=f'Action Required: Update Your Farm — {farm.farm_name}',
        message=f'Your cooperative officer has requested changes to your farm before approval.\n\nIssue: {issue}',
        type='warning',
        reference_id=farm_id,
        reference_type='farm',
    )
    db.add(notif)
    await db.commit()
    return {"message": "Update request sent to farmer"}


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
    farm.update_requested = False
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
    farm.update_requested = False
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


async def _get_coop_id_for_officer(current_user: User, db: AsyncSession) -> Optional[str]:
    """Resolve the cooperative ID for the current officer/agent via user field, primary_officer, or membership."""
    coop_id = getattr(current_user, 'cooperative_id', None)
    if not coop_id:
        # Fallback 1: cooperative where this user is the primary officer
        coop_result = await db.execute(
            select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
        )
        coop = coop_result.scalar_one_or_none()
        coop_id = str(coop.id) if coop else None
    if not coop_id:
        # Fallback 2: CooperativeMember entry (handles delivery agents + web-created staff)
        mem_result = await db.execute(
            select(CooperativeMember.cooperative_id)
            .where(CooperativeMember.user_id == current_user.id, CooperativeMember.is_active == True)
            .limit(1)
        )
        coop_id = mem_result.scalar_one_or_none()
    return coop_id


async def _get_farmer_ids_for_coop(coop_id: str, db: AsyncSession):
    """Return list of farmer user IDs that are members of this cooperative."""
    result = await db.execute(
        select(CooperativeMember.user_id).where(
            CooperativeMember.cooperative_id == coop_id,
            CooperativeMember.is_active == True
        )
    )
    return result.scalars().all()


async def _get_or_generate_member_no(user_id: str, coop_id: str, db: AsyncSession) -> str | None:
    """Return or lazily generate a PCFNO member number for a farmer in a cooperative."""
    from datetime import datetime as _dt
    res = await db.execute(
        select(CooperativeMember).where(
            CooperativeMember.user_id == user_id,
            CooperativeMember.cooperative_id == coop_id,
            CooperativeMember.is_active == True,
        )
    )
    member = res.scalar_one_or_none()
    if not member:
        return None
    if not member.membership_number or not member.membership_number.startswith("PCFNO/"):
        count_res = await db.execute(
            select(func.count(CooperativeMember.id)).where(
                CooperativeMember.cooperative_id == coop_id,
                CooperativeMember.membership_number.like("PCFNO/%"),
            )
        )
        seq = (count_res.scalar() or 0) + 1
        year = member.join_date.year if member.join_date else _dt.utcnow().year
        member.membership_number = f"PCFNO/{seq:03d}/{year}"
        await db.commit()
    return member.membership_number


@router.get("/farms")
async def get_coop_farms(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all farms whose owners are members of this cooperative."""
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if not coop_id:
        return {"farms": [], "total": 0}

    farmer_ids = await _get_farmer_ids_for_coop(coop_id, db)
    if not farmer_ids:
        return {"farms": [], "total": 0}

    query = select(Farm).where(
        Farm.owner_id.in_(farmer_ids),
        Farm.deleted_at == None
    )
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
            "farm_code": getattr(f, 'farm_code', None),
            "owner_id": str(f.owner_id),
            "farmer_name": f"{owner.first_name} {owner.last_name}" if owner else "Unknown",
            "farmer_phone": owner.phone if owner else None,
            "total_area_hectares": f.total_area_hectares,
            "total_area_ha": f.total_area_hectares,
            "verification_status": f.verification_status,
            "coop_status": f.coop_status,
            "coop_notes": f.coop_notes,
            "compliance_status": getattr(f, 'compliance_status', 'Under Review') or 'Under Review',
            "deforestation_risk_score": getattr(f, 'deforestation_risk_score', 0.0),
            "update_requested": bool(getattr(f, 'update_requested', False)),
            "update_request_notes": getattr(f, 'update_request_notes', None),
            "update_requested_by_name": getattr(f, 'update_requested_by_name', None),
            "centroid_lat": getattr(f, 'centroid_lat', None),
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return {"farms": output, "total": len(output)}


@router.get("/farms/pending")
async def get_pending_farms(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get farms pending coop verification for this cooperative."""
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if not coop_id:
        return []

    farmer_ids = await _get_farmer_ids_for_coop(coop_id, db)
    if not farmer_ids:
        return []

    result = await db.execute(
        select(Farm).where(
            Farm.owner_id.in_(farmer_ids),
            Farm.verification_status.in_(["pending", "coop_approved", "draft"]),
            Farm.deleted_at == None
        ).order_by(Farm.created_at.desc())
    )
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
    current_user: User = Depends(require_coop_staff),
    db: AsyncSession = Depends(get_db)
):
    """Record a coffee delivery — farm must belong to a farmer in this cooperative."""
    coop_id = await _get_coop_id_for_officer(current_user, db)
    now = datetime.utcnow()

    coop_farm_ids: list = []
    if coop_id:
        farmer_ids = await _get_farmer_ids_for_coop(coop_id, db)
        # Verify the farm belongs to a member of this cooperative
        farm_res = await db.execute(select(Farm).where(Farm.id == delivery_data.farm_id))
        farm = farm_res.scalar_one_or_none()
        if farm and farmer_ids and str(farm.owner_id) not in [str(fid) for fid in farmer_ids]:
            raise HTTPException(status_code=403, detail="Farm does not belong to a farmer in your cooperative")
        if farmer_ids:
            cf_res = await db.execute(select(Farm.id).where(Farm.owner_id.in_(farmer_ids)))
            coop_farm_ids = cf_res.scalars().all()

    # Sequential delivery number scoped to this cooperative
    if coop_farm_ids:
        count_res = await db.execute(
            select(func.count(Delivery.id)).where(Delivery.farm_id.in_(coop_farm_ids))
        )
    else:
        count_res = await db.execute(select(func.count(Delivery.id)))
    seq = (count_res.scalar() or 0) + 1
    delivery_number = f"PCFDELIVERY/{seq:03d}/{now.year}"
    net_weight = delivery_data.gross_weight_kg - delivery_data.tare_weight_kg

    delivery = Delivery(
        delivery_number=delivery_number,
        farm_id=delivery_data.farm_id,
        gross_weight_kg=delivery_data.gross_weight_kg,
        tare_weight_kg=delivery_data.tare_weight_kg,
        net_weight_kg=net_weight,
        crop_mix=delivery_data.crop_mix,
        notes=delivery_data.notes,
        status=DeliveryStatus.RECEIVED,
        received_by_id=current_user.id,
        agent_id=current_user.id,
    )
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)

    # Notify the farmer that a delivery has been recorded for their farm
    try:
        from app.models.notification import Notification
        notif_farm_res = await db.execute(select(Farm).where(Farm.id == delivery_data.farm_id))
        notif_farm = notif_farm_res.scalar_one_or_none()
        if notif_farm and notif_farm.owner_id:
            officer_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or "Cooperative Officer"
            grade = delivery_data.quality_grade or "PB"
            db.add(Notification(
                recipient_id=str(notif_farm.owner_id),
                title="New Delivery Recorded",
                message=(
                    f"A delivery of {net_weight:.1f} kg ({grade} grade) has been recorded "
                    f"for your farm by {officer_name}. Reference: {delivery_number}."
                ),
                type="success",
                reference_id=str(delivery.id),
                reference_type="delivery",
            ))
            await db.commit()
    except Exception:
        pass  # never fail the delivery if notification creation errors

    return delivery


@router.post("/staff", response_model=CoopStaffResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery_agent(
    staff_data: CreateCoopStaffRequest,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new Delivery Agent account linked to this cooperative.
    Only cooperative officers can create staff accounts.
    """
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if not coop_id:
        raise HTTPException(status_code=403, detail="No cooperative linked to your account")

    # Prevent duplicate phone
    dup_phone = await db.execute(select(User).where(User.phone == staff_data.phone))
    if dup_phone.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A user with this phone number already exists")

    if staff_data.email:
        dup_email = await db.execute(select(User).where(User.email == staff_data.email))
        if dup_email.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="A user with this email already exists")

    agent = User(
        first_name=staff_data.first_name,
        last_name=staff_data.last_name,
        phone=staff_data.phone,
        email=staff_data.email,
        password_hash=get_password_hash(staff_data.password),
        national_id=staff_data.national_id,
        role=UserRole.DELIVERY_AGENT,
        cooperative_id=coop_id,   # so /auth/me returns cooperative_id and coop APIs resolve correctly
        is_active=True,
    )
    db.add(agent)
    await db.flush()

    membership = CooperativeMember(
        user_id=agent.id,
        cooperative_id=coop_id,
        cooperative_role=CooperativeUserRoleEnum.DELIVERY_AGENT.value,
        membership_type="staff",
        is_active=True,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(agent)

    return CoopStaffResponse(
        id=str(agent.id),
        first_name=agent.first_name,
        last_name=agent.last_name,
        phone=agent.phone,
        email=agent.email,
        role=agent.role.value if hasattr(agent.role, "value") else str(agent.role),
        job_title=staff_data.job_title or "Delivery Agent",
        is_active=bool(agent.is_active),
        created_at=agent.created_at,
    )


@router.get("/staff", response_model=List[CoopStaffResponse])
async def get_coop_staff(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all delivery agents belonging to this cooperative."""
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if not coop_id:
        raise HTTPException(status_code=403, detail="No cooperative linked to your account")

    result = await db.execute(
        select(User, CooperativeMember)
        .join(CooperativeMember, CooperativeMember.user_id == User.id)
        .where(
            CooperativeMember.cooperative_id == coop_id,
            CooperativeMember.cooperative_role == CooperativeUserRoleEnum.DELIVERY_AGENT.value,
            CooperativeMember.is_active == True,
        )
    )
    rows = result.all()
    return [
        CoopStaffResponse(
            id=str(u.id),
            first_name=u.first_name,
            last_name=u.last_name,
            phone=u.phone,
            email=u.email,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            job_title="Delivery Agent",
            is_active=bool(m.is_active),
            created_at=u.created_at,
        )
        for u, m in rows
    ]


@router.get("/deliveries", response_model=List[DeliveryResponse])
async def get_deliveries(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get deliveries for farms belonging to farmers in this cooperative."""
    coop_id = await _get_coop_id_for_officer(current_user, db)

    query = select(Delivery)

    if coop_id:
        farmer_ids = await _get_farmer_ids_for_coop(coop_id, db)
        if farmer_ids:
            farm_res = await db.execute(
                select(Farm.id).where(Farm.owner_id.in_(farmer_ids))
            )
            farm_ids = farm_res.scalars().all()
            if farm_ids:
                query = query.where(Delivery.farm_id.in_(farm_ids))
            else:
                return []

    if start_date:
        query = query.where(Delivery.created_at >= start_date)
    if end_date:
        query = query.where(Delivery.created_at <= end_date)
    if status_filter:
        query = query.where(Delivery.status == status_filter.lower())

    result = await db.execute(query.order_by(Delivery.created_at.desc()))
    return result.scalars().all()


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    batch_data: BatchCreate,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a coffee batch from ready-for-batching deliveries — URS §4.2"""
    from datetime import datetime as _dt, date as _date
    from app.models.farms import Farm

    # Resolve cooperative
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
    )
    cooperative = coop_result.scalar_one_or_none()
    if not cooperative:
        raise HTTPException(status_code=403, detail="You are not assigned as a cooperative admin")

    # Load selected deliveries
    deliveries: list = []
    if batch_data.delivery_ids:
        d_res = await db.execute(select(Delivery).where(Delivery.id.in_(batch_data.delivery_ids)))
        deliveries = d_res.scalars().all()

    # Auto-compute totals
    total_weight    = sum(d.net_weight_kg or 0 for d in deliveries)
    eudr_kg         = sum((d.net_weight_kg or 0) for d in deliveries if d.eudr_eligible is not False)
    parcel_ids      = {d.parcel_id for d in deliveries if d.parcel_id}
    farm_ids        = {d.farm_id   for d in deliveries if d.farm_id}

    # Count unique farmers from farms
    farmer_ids: set = set()
    if farm_ids:
        f_res = await db.execute(select(Farm).where(Farm.id.in_(farm_ids)))
        for f in f_res.scalars().all():
            if f.farmer_id:
                farmer_ids.add(f.farmer_id)

    crop_year = (batch_data.harvest_start_date.year
                 if batch_data.harvest_start_date else _date.today().year)

    batch = Batch(
        cooperative_id=cooperative.id,
        batch_number=batch_data.batch_number,
        crop_year=crop_year,
        harvest_start_date=batch_data.harvest_start_date,
        harvest_end_date=batch_data.harvest_end_date,
        total_weight_kg=total_weight,
        eudr_eligible_kg=eudr_kg,
        total_farmers=len(farmer_ids) or len(farm_ids),
        total_parcels=len(parcel_ids),
        notes=batch_data.notes,
        created_by_id=current_user.id,
        compliance_status="Under Review",
        status=BatchStatus.DRAFT.value,
    )
    db.add(batch)
    await db.flush()

    # Link deliveries → batch
    for d in deliveries:
        d.batch_id = batch.id

    # Release immediately if requested
    if batch_data.release_immediately:
        batch.status = BatchStatus.RELEASED.value
        batch.released_at = _dt.utcnow()

    _audit(db, AuditEventType.BATCH_CREATED, "batch", batch.id, current_user.id,
           nxt=batch.status)

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
    coop = None
    if not coop_id:
        coop_result = await db.execute(
            select(Cooperative).where(Cooperative.primary_officer_id == current_user.id)
        )
        coop = coop_result.scalar_one_or_none()
        coop_id = str(coop.id) if coop else None
    if not coop_id:
        raise HTTPException(status_code=404, detail="No cooperative linked to your account")
    if not coop:
        coop = await db.get(Cooperative, coop_id)
    return {"cooperative_id": coop_id, "cooperative_name": coop.name if coop else None}


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


# ════════════════════════════════════════════════════════════════════════════
#  URS — Delivery detail + status update + processing log
# ════════════════════════════════════════════════════════════════════════════

def _audit(db, event_type, entity_type, entity_id, actor_id, prev=None, nxt=None, notes=None):
    """Helper: queue an AuditEvent (caller must commit)."""
    db.add(AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_id=str(actor_id),
        previous_state=str(prev) if prev is not None else None,
        new_state=str(nxt) if nxt is not None else None,
        notes=notes,
    ))


@router.get("/deliveries/{delivery_id}")
async def get_delivery_detail(
    delivery_id: str,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Full delivery detail including processing log."""
    delivery = await db.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    logs_res = await db.execute(
        select(ProcessingLog)
        .where(ProcessingLog.delivery_id == delivery_id)
        .order_by(ProcessingLog.step_date)
    )
    logs = logs_res.scalars().all()

    # Resolve logged-by names for processing logs
    log_user_ids = list({lg.logged_by_id for lg in logs if lg.logged_by_id})
    log_users: dict = {}
    if log_user_ids:
        lu_res = await db.execute(select(User).where(User.id.in_(log_user_ids)))
        for u in lu_res.scalars().all():
            log_users[u.id] = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email

    # Build farm/farmer info
    farm = await db.get(Farm, delivery.farm_id) if delivery.farm_id else None
    farmer = None
    if farm:
        farmer_res = await db.execute(select(User).where(User.id == farm.owner_id))
        farmer = farmer_res.scalar_one_or_none()

    return {
        "id": delivery.id,
        "delivery_number": delivery.delivery_number,
        "status": getattr(delivery.status, 'value', str(delivery.status)) if delivery.status else "pending",
        "farm_id": delivery.farm_id,
        "farm_name": farm.farm_name if farm else None,
        "farmer_name": f"{farmer.first_name} {farmer.last_name}" if farmer else None,
        "farmer_phone": farmer.phone if farmer else None,
        "parcel_id": delivery.parcel_id,
        "gross_weight_kg": delivery.gross_weight_kg,
        "tare_weight_kg": delivery.tare_weight_kg,
        "net_weight_kg": delivery.net_weight_kg,
        "quality_grade": delivery.quality_grade.value if delivery.quality_grade else None,
        "moisture_content": delivery.moisture_content,
        "cherry_type": delivery.cherry_type,
        "eudr_eligible": delivery.eudr_eligible,
        "crop_mix": delivery.crop_mix,
        "notes": delivery.notes,
        "batch_id": delivery.batch_id,
        "reception_date": delivery.reception_date.isoformat() if delivery.reception_date else None,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
        "processing_log": [
            {
                "id": lg.id,
                "log_number": lg.log_number,
                "step_type": lg.step_type.value,
                "step_date": lg.step_date.isoformat() if lg.step_date else None,
                "weight_out_kg": lg.weight_out_kg,
                "grade": lg.grade,
                "notes": lg.notes,
                "logged_by_id": lg.logged_by_id,
                "logged_by_name": log_users.get(lg.logged_by_id, ''),
                "created_at": lg.created_at.isoformat() if lg.created_at else None,
            }
            for lg in logs
        ],
    }


@router.patch("/deliveries/{delivery_id}/status")
async def update_delivery_status(
    delivery_id: str,
    body: dict,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a delivery's status. body: {status, notes?}"""
    delivery = await db.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    try:
        new_status = DeliveryStatus(body.get("status", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid values: {[s.value for s in DeliveryStatus]}")

    prev_status = delivery.status
    delivery.status = new_status.value  # use plain string to avoid asyncpg sending uppercase name
    _audit(db, AuditEventType.DELIVERY_STATUS_CHANGED, "delivery", delivery_id,
           current_user.id, prev=prev_status.value if hasattr(prev_status, 'value') else str(prev_status),
           nxt=new_status.value, notes=body.get("notes"))
    await db.commit()
    return {"delivery_id": delivery_id, "status": new_status.value}


@router.post("/deliveries/{delivery_id}/processing")
async def add_processing_step(
    delivery_id: str,
    body: dict,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Log a processing step for a delivery.
    Automatically advances delivery status:
      any step → in_processing; Packing → ready_for_batching.
    """
    delivery = await db.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    try:
        step_type = ProcessingStepType(body.get("step_type", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid step_type. Valid: {[s.value for s in ProcessingStepType]}")

    from datetime import datetime as _dt
    step_date_raw = body.get("step_date")
    step_date = _dt.fromisoformat(step_date_raw) if step_date_raw else _dt.utcnow()
    now = _dt.utcnow()

    # Sequential log number scoped to all processing logs
    pl_count_res = await db.execute(select(func.count(ProcessingLog.id)))
    pl_seq = (pl_count_res.scalar() or 0) + 1
    log_number = f"PDELPL/{pl_seq:03d}/{now.year}/{now.strftime('%H%M')}"

    log = ProcessingLog(
        log_number=log_number,
        delivery_id=delivery_id,
        step_type=step_type,
        step_date=step_date,
        weight_out_kg=body.get("weight_out_kg"),
        grade=body.get("grade") if step_type == ProcessingStepType.GRADING else None,
        notes=body.get("notes"),
        logged_by_id=current_user.id,
    )
    db.add(log)

    # Auto-advance delivery status
    # Use .value (plain string) not the enum object — SQLAlchemy 1.4/asyncpg sends
    # .name (uppercase) for enum objects in UPDATE statements, causing a DB type error.
    prev_status = delivery.status
    prev_val = prev_status.value if hasattr(prev_status, 'value') else str(prev_status)
    if step_type == ProcessingStepType.PACKING:
        delivery.status = DeliveryStatus.READY_FOR_BATCHING.value
    elif str(delivery.status) in (
        DeliveryStatus.PENDING.value, DeliveryStatus.RECEIVED.value,
        DeliveryStatus.WEIGHED.value, DeliveryStatus.QUALITY_CHECKED.value,
        DeliveryStatus.IN_PROCESSING.value,
    ):
        delivery.status = DeliveryStatus.IN_PROCESSING.value

    _audit(db, AuditEventType.PROCESSING_STEP_ADDED, "delivery", delivery_id,
           current_user.id, prev=prev_val,
           nxt=str(delivery.status), notes=f"Step: {step_type.value}")
    await db.commit()
    await db.refresh(log)
    logged_by_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
    return {
        "id": log.id,
        "log_number": log.log_number,
        "delivery_id": delivery_id,
        "step_type": log.step_type.value,
        "step_date": log.step_date.isoformat(),
        "weight_out_kg": log.weight_out_kg,
        "grade": log.grade,
        "notes": log.notes,
        "logged_by_id": log.logged_by_id,
        "logged_by_name": logged_by_name,
        "delivery_status": getattr(delivery.status, 'value', str(delivery.status)),
    }


@router.get("/deliveries/{delivery_id}/processing")
async def get_processing_log(
    delivery_id: str,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get the full processing log for a delivery."""
    res = await db.execute(
        select(ProcessingLog)
        .where(ProcessingLog.delivery_id == delivery_id)
        .order_by(ProcessingLog.step_date)
    )
    logs = res.scalars().all()

    user_ids = list({lg.logged_by_id for lg in logs if lg.logged_by_id})
    users: dict = {}
    if user_ids:
        u_res = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in u_res.scalars().all():
            users[u.id] = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email

    return [
        {
            "id": lg.id, "log_number": lg.log_number,
            "step_type": lg.step_type.value,
            "step_date": lg.step_date.isoformat() if lg.step_date else None,
            "weight_out_kg": lg.weight_out_kg, "grade": lg.grade,
            "notes": lg.notes,
            "logged_by_id": lg.logged_by_id,
            "logged_by_name": users.get(lg.logged_by_id, ''),
            "created_at": lg.created_at.isoformat() if lg.created_at else None,
        }
        for lg in logs
    ]


# ════════════════════════════════════════════════════════════════════════════
#  URS — Batch detail + release
# ════════════════════════════════════════════════════════════════════════════

@router.get("/batches/{batch_id}")
async def get_batch_detail(
    batch_id: str,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Full batch detail with delivery list and EUDR eligibility."""
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    deliveries_res = await db.execute(
        select(Delivery).where(Delivery.batch_id == batch_id)
    )
    deliveries = deliveries_res.scalars().all()

    eudr_kg = sum(
        (d.net_weight_kg or 0) for d in deliveries
        if d.eudr_eligible is not False
    )
    unique_farms = list({d.farm_id for d in deliveries if d.farm_id})

    return {
        "id": batch.id,
        "batch_number": batch.batch_number,
        "lot_number": batch.lot_number,
        "crop_year": batch.crop_year,
        "harvest_start_date": batch.harvest_start_date.isoformat() if batch.harvest_start_date else None,
        "harvest_end_date": batch.harvest_end_date.isoformat() if batch.harvest_end_date else None,
        "processing_method": batch.processing_method.value if batch.processing_method else None,
        "quality_grade": batch.quality_grade.value if batch.quality_grade else None,
        "total_weight_kg": batch.total_weight_kg,
        "eudr_eligible_kg": eudr_kg,
        "total_farmers": len(unique_farms),
        "total_parcels": batch.total_parcels,
        "status": getattr(batch.status, 'value', str(batch.status)) if batch.status else "draft",
        "compliance_status": batch.compliance_status,
        "notes": batch.notes,
        "released_at": batch.released_at.isoformat() if batch.released_at else None,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "deliveries": [
            {
                "id": d.id, "delivery_number": d.delivery_number,
                "net_weight_kg": d.net_weight_kg,
                "status": getattr(d.status, 'value', str(d.status)) if d.status else None,
                "eudr_eligible": d.eudr_eligible,
                "quality_grade": d.quality_grade.value if d.quality_grade else None,
            }
            for d in deliveries
        ],
    }


@router.post("/batches/{batch_id}/release")
async def release_batch(
    batch_id: str,
    body: dict = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Release a batch to Plotra Admin for satellite screening — URS UC-07.
    Pre-release validation: all deliveries must be in batched/ready_for_batching status.
    """
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status != BatchStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Batch is already in status '{getattr(batch.status, 'value', batch.status)}' — only Draft batches can be released")

    deliveries_res = await db.execute(select(Delivery).where(Delivery.batch_id == batch_id))
    deliveries = deliveries_res.scalars().all()

    if not deliveries:
        raise HTTPException(status_code=400, detail="Batch has no deliveries — add deliveries before releasing")

    # Validation: flag any deliveries that aren't ready
    blocked = [
        d.delivery_number for d in deliveries
        if d.status not in (DeliveryStatus.READY_FOR_BATCHING, DeliveryStatus.BATCHED, DeliveryStatus.PROCESSED)
    ]
    if blocked:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot release: {len(blocked)} deliver(ies) are not in Ready/Batched status: {blocked[:5]}"
        )

    from datetime import datetime as _dt
    prev_status = batch.status
    prev_status_val = prev_status.value if hasattr(prev_status, 'value') else str(prev_status or '')
    batch.status = BatchStatus.RELEASED.value
    batch.released_at = _dt.utcnow()
    batch.eudr_eligible_kg = sum((d.net_weight_kg or 0) for d in deliveries if d.eudr_eligible is not False)
    batch.total_farmers = len({d.farm_id for d in deliveries if d.farm_id})

    # Mark all deliveries as batched
    for d in deliveries:
        prev_d = d.status.value if hasattr(d.status, 'value') else str(d.status or '')
        d.status = DeliveryStatus.BATCHED.value
        _audit(db, AuditEventType.DELIVERY_STATUS_CHANGED, "delivery", d.id,
               current_user.id, prev=prev_d, nxt=DeliveryStatus.BATCHED.value)

    _audit(db, AuditEventType.BATCH_RELEASED, "batch", batch_id,
           current_user.id, prev=prev_status_val, nxt=BatchStatus.RELEASED.value,
           notes=(body or {}).get("notes"))
    await db.commit()
    return {
        "batch_id": batch_id, "status": "released",
        "released_at": batch.released_at.isoformat(),
        "eudr_eligible_kg": batch.eudr_eligible_kg,
        "total_farmers": batch.total_farmers,
    }


@router.patch("/batches/{batch_id}/status")
async def update_batch_status(
    batch_id: str,
    body: dict,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin/system endpoint to advance batch status (used by Plotra Admin after satellite review)."""
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    try:
        new_status = BatchStatus(body.get("status", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {[s.value for s in BatchStatus]}")
    prev = batch.status
    prev_val = prev.value if hasattr(prev, 'value') else str(prev or '')
    batch.status = new_status.value
    _audit(db, AuditEventType.BATCH_VERIFIED if new_status == BatchStatus.VERIFIED else AuditEventType.BATCH_RELEASED,
           "batch", batch_id, current_user.id, prev=prev_val, nxt=new_status.value)
    await db.commit()
    return {"batch_id": batch_id, "status": new_status.value}


# ════════════════════════════════════════════════════════════════════════════
#  URS — Consignment management
# ════════════════════════════════════════════════════════════════════════════

@router.get("/consignments")
async def list_consignments(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all consignments for the cooperative."""
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if not coop_id:
        return []
    res = await db.execute(
        select(Consignment)
        .where(Consignment.cooperative_id == coop_id)
        .order_by(Consignment.created_at.desc())
    )
    consignments = res.scalars().all()
    return [
        {
            "id": c.id, "consignment_reference": c.consignment_reference,
            "batch_ids": c.batch_ids, "destination_country": c.destination_country,
            "importer_name": c.importer_name,
            "expected_shipment_date": c.expected_shipment_date.isoformat() if c.expected_shipment_date else None,
            "total_weight_kg": c.total_weight_kg,
            "consignment_status": c.consignment_status.value if c.consignment_status else None,
            "dds_reference": c.dds_reference, "notes": c.notes,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in consignments
    ]


@router.post("/consignments", status_code=201)
async def create_consignment(
    body: dict,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a consignment from one or more verified batches — URS UC-06."""
    coop_id = await _get_coop_id_for_officer(current_user, db)
    if not coop_id:
        raise HTTPException(status_code=403, detail="No cooperative found for this officer")

    batch_ids = body.get("batch_ids", [])
    if not batch_ids:
        raise HTTPException(status_code=400, detail="At least one batch_id is required")

    # Validate all batches exist and belong to this coop
    total_weight = 0.0
    for bid in batch_ids:
        b = await db.get(Batch, str(bid))
        if not b:
            raise HTTPException(status_code=404, detail=f"Batch {bid} not found")
        if str(b.cooperative_id) != str(coop_id):
            raise HTTPException(status_code=403, detail=f"Batch {bid} does not belong to your cooperative")
        total_weight += b.total_weight_kg or 0

    ref = body.get("consignment_reference", "").strip()
    if not ref:
        from datetime import datetime as _dt
        ref = f"CSG-{_dt.utcnow().strftime('%Y%m%d')}-{__import__('uuid').uuid4().hex[:6].upper()}"

    consignment = Consignment(
        cooperative_id=coop_id,
        consignment_reference=ref,
        batch_ids=batch_ids,
        destination_country=body.get("destination_country", "").upper(),
        importer_name=body.get("importer_name", ""),
        expected_shipment_date=__import__('datetime').datetime.fromisoformat(body["expected_shipment_date"]) if body.get("expected_shipment_date") else None,
        total_weight_kg=total_weight,
        notes=body.get("notes"),
        created_by_id=current_user.id,
    )
    db.add(consignment)
    _audit(db, AuditEventType.CONSIGNMENT_CREATED, "consignment", ref,
           current_user.id, nxt="pending_dds")
    await db.commit()
    await db.refresh(consignment)
    return {
        "id": consignment.id, "consignment_reference": consignment.consignment_reference,
        "batch_ids": consignment.batch_ids, "destination_country": consignment.destination_country,
        "importer_name": consignment.importer_name, "total_weight_kg": consignment.total_weight_kg,
        "consignment_status": consignment.consignment_status.value,
        "created_at": consignment.created_at.isoformat() if consignment.created_at else None,
    }


@router.patch("/consignments/{consignment_id}/status")
async def update_consignment_status(
    consignment_id: str,
    body: dict,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update consignment status (e.g. dds_ready, dds_submitted)."""
    c = await db.get(Consignment, consignment_id)
    if not c:
        raise HTTPException(status_code=404, detail="Consignment not found")
    try:
        new_status = ConsignmentStatus(body.get("status", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {[s.value for s in ConsignmentStatus]}")
    prev = c.consignment_status
    c.consignment_status = new_status
    if body.get("dds_reference"):
        c.dds_reference = body["dds_reference"]
    _audit(db, AuditEventType.CONSIGNMENT_DDS_SUBMITTED if new_status == ConsignmentStatus.DDS_SUBMITTED else AuditEventType.CONSIGNMENT_CREATED,
           "consignment", consignment_id, current_user.id,
           prev=prev.value if prev else None, nxt=new_status.value)
    await db.commit()
    return {"consignment_id": consignment_id, "status": new_status.value, "dds_reference": c.dds_reference}


@router.post("/members/{user_id}/reject")
async def reject_farmer(
    user_id: str,
    body: dict = None,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject a farmer's cooperative membership application."""
    farmer = await db.get(User, user_id)
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    farmer.coop_status = "coop_rejected"
    farmer.coop_notes = (body or {}).get("reason", "Rejected by cooperative officer")
    farmer.coop_verified_by_name = f"{current_user.first_name} {current_user.last_name}"
    await db.commit()
    return {"user_id": user_id, "coop_status": "coop_rejected"}


@router.get("/consignments/{consignment_id}")
async def get_consignment_detail(
    consignment_id: str,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db),
):
    """Full consignment detail with linked batches."""
    c = await db.get(Consignment, consignment_id)
    if not c:
        raise HTTPException(status_code=404, detail="Consignment not found")

    batches = []
    for bid in (c.batch_ids or []):
        b = await db.get(Batch, str(bid))
        if b:
            batches.append({
                "id": b.id, "batch_number": b.batch_number,
                "total_weight_kg": b.total_weight_kg,
                "eudr_eligible_kg": b.eudr_eligible_kg,
                "status": getattr(b.status, 'value', str(b.status)) if b.status else None,
                "crop_year": b.crop_year,
            })

    return {
        "id": c.id, "consignment_reference": c.consignment_reference,
        "batch_ids": c.batch_ids, "destination_country": c.destination_country,
        "importer_name": c.importer_name,
        "expected_shipment_date": c.expected_shipment_date.isoformat() if c.expected_shipment_date else None,
        "total_weight_kg": c.total_weight_kg,
        "consignment_status": c.consignment_status.value if c.consignment_status else None,
        "dds_reference": c.dds_reference, "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "batches": batches,
    }
