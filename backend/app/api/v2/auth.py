"""
Plotra Platform - Authentication API Endpoints
"""
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.auth import (
    authenticate_user, create_access_token, get_current_user,
    get_password_hash, require_admin
)
from app.models.user import User, UserRole, VerificationStatus
from app.api.schemas import (
    Token, LoginRequest, UserCreate, UserResponse, MessageResponse
)

router = APIRouter(tags=["Authentication"])
logger = logging.getLogger(__name__)


# ── OTP helpers ──────────────────────────────────────────────────────────────

async def _normalize(phone: str) -> str:
    from app.core.auth import _normalize_phone
    if not phone.startswith('+'):
        phone = _normalize_phone(phone) or phone
    return phone


@router.post("/send-otp")
async def send_otp(
    phone: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Generate and send a 6-digit OTP to the given phone number."""
    from sqlalchemy import select, update as sa_update
    from app.models.otp import OTPVerification

    phone = await _normalize(phone)

    # Invalidate any existing unused OTPs for this phone
    await db.execute(
        sa_update(OTPVerification)
        .where(OTPVerification.phone == phone, OTPVerification.is_used == False)
        .values(is_used=True)
    )

    otp = OTPVerification.generate(phone)
    db.add(otp)
    await db.commit()

    # ── SMS delivery ─────────────────────────────────────────────────────────
    # Replace this block with your SMS provider (Africa's Talking, Twilio, etc.)
    logger.info(f"[OTP] {phone} → {otp.code}  (expires in 10 min)")
    # ─────────────────────────────────────────────────────────────────────────

    return {"message": "OTP sent", "expires_in": 600, "dev_code": otp.code}


@router.post("/verify-otp")
async def verify_otp(
    phone: str = Form(...),
    code: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Verify OTP code for a phone number."""
    from sqlalchemy import select
    from app.models.otp import OTPVerification
    from datetime import datetime

    phone = await _normalize(phone)

    result = await db.execute(
        select(OTPVerification)
        .where(OTPVerification.phone == phone, OTPVerification.is_used == False)
        .order_by(OTPVerification.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()

    if not otp:
        raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")

    if datetime.utcnow() > otp.expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if otp.attempts >= 5:
        raise HTTPException(status_code=400, detail="Too many attempts. Please request a new OTP.")

    if otp.code != code:
        otp.attempts += 1
        await db.commit()
        remaining = 5 - otp.attempts
        raise HTTPException(status_code=400, detail=f"Invalid code. {remaining} attempt(s) remaining.")

    otp.is_used = True
    await db.commit()

    # If the user has a pending password reset token, return it so the frontend
    # can proceed to the reset step without a separate round-trip.
    reset_token = None
    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()
    if user and user.password_reset_token:
        reset_token = user.password_reset_token

    return {"verified": True, "reset_token": reset_token}


@router.post("/forgot-password-otp")
async def forgot_password_otp(
    phone: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Check user exists by phone and send OTP for password reset."""
    from sqlalchemy import select, update as sa_update
    from app.models.otp import OTPVerification

    normalized = await _normalize(phone)

    # Check user exists
    result = await db.execute(
        select(User).where(User.phone == normalized)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that phone number.")

    # Invalidate old OTPs
    await db.execute(
        sa_update(OTPVerification)
        .where(OTPVerification.phone == normalized, OTPVerification.is_used == False)
        .values(is_used=True)
    )

    # Generate and store a password reset token so verify-otp can return it
    import uuid as _uuid
    reset_token = str(_uuid.uuid4())
    user.password_reset_token = reset_token

    otp = OTPVerification.generate(normalized)
    db.add(otp)
    await db.commit()

    logger.info(f"[RESET OTP] {normalized} → {otp.code}")
    return {"message": "OTP sent to your phone", "expires_in": 600, "dev_code": otp.code}


@router.get("/check-field")
async def check_field(
    field: str,
    value: str = "",
    first_name: str = "",
    last_name: str = "",
    db: AsyncSession = Depends(get_db)
):
    """Check whether a field value is already taken. Returns {available: bool}."""
    from sqlalchemy import select, func
    from app.models.user import User

    if field == "email":
        if not value:
            return {"available": True}
        r = await db.execute(select(func.count()).select_from(User).where(User.email == value.strip().lower()))
        return {"available": r.scalar() == 0}

    if field == "phone":
        if not value:
            return {"available": True}
        phone = await _normalize(value.strip())
        r = await db.execute(select(func.count()).select_from(User).where(User.phone == phone))
        return {"available": r.scalar() == 0}

    if field == "national_id":
        if not value:
            return {"available": True}
        r = await db.execute(select(func.count()).select_from(User).where(User.national_id == value.strip()))
        return {"available": r.scalar() == 0}

    if field == "name":
        if not first_name or not last_name:
            return {"available": True}
        r = await db.execute(
            select(func.count()).select_from(User)
            .where(func.lower(User.first_name) == first_name.strip().lower())
            .where(func.lower(User.last_name) == last_name.strip().lower())
        )
        return {"available": r.scalar() == 0}

    return {"available": True}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 compatible token login.
    Supports both JSON and form-encoded requests.
    """
    user = await authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    access_token_expires = timedelta(minutes=settings.app.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "phone": user.phone, "role": user.role.value, "page_permissions": getattr(user, 'page_permissions', None), "cooperative_id": getattr(user, 'cooperative_id', None)},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.app.access_token_expire_minutes * 60
    }


@router.post("/token-form", response_model=Token)
async def login_form(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Form-encoded login endpoint for browser compatibility.
    """
    try:
        user = await authenticate_user(db, username, password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect phone/email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )

        access_token_expires = timedelta(minutes=settings.app.access_token_expire_minutes)
        role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "phone": user.phone, "role": role_value},
            expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.app.access_token_expire_minutes * 60
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Login error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Login error: {str(e)}"}
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    New users are created with PENDING verification status.
    """
    from sqlalchemy import select
    import traceback
    
    try:
        # Check if email already exists (if email provided)
        if user_data.email:
            result = await db.execute(
                select(User).where(User.email == user_data.email)
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Check if phone already exists (if phone provided)
        if user_data.phone_number:
            result = await db.execute(
                select(User).where(User.phone == user_data.phone_number)
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number already registered"
                )
        
        # Determine country
        country_value = user_data.country or "Kenya"
        if user_data.phone_number and not user_data.country:
            phone = user_data.phone_number
            if phone.startswith('+254'):
                country_value = "Kenya"
            elif phone.startswith('+255'):
                country_value = "Tanzania"
            elif phone.startswith('+256'):
                country_value = "Uganda"
            else:
                country_value = "Kenya"
        
        # Create user
        user = User(
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone_number,
            role=user_data.role,
            country=country_value,
            county=user_data.county,
            district=user_data.subcounty  # Map subcounty to district
        )
        
        # Store id_number in national_id if provided
        if user_data.id_number:
            user.national_id = user_data.id_number
        
        # Store additional optional fields in kyc_data JSON
        kyc_data = {}
        if user_data.gender:
            kyc_data['gender'] = user_data.gender
        if user_data.id_type:
            kyc_data['id_type'] = user_data.id_type
        if user_data.id_number:
            kyc_data['id_number'] = user_data.id_number
        if user_data.cooperative_code:
            kyc_data['cooperative_code'] = user_data.cooperative_code
        if user_data.payout_method:
            kyc_data['payout_method'] = user_data.payout_method
        if user_data.payout_recipient_id:
            kyc_data['payout_recipient_id'] = user_data.payout_recipient_id
        if user_data.payout_bank_name:
            kyc_data['payout_bank_name'] = user_data.payout_bank_name
        if user_data.payout_account_number:
            kyc_data['payout_account_number'] = user_data.payout_account_number
        
        if kyc_data:
            user.kyc_data = kyc_data
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Link user to cooperative if cooperative_code is provided
        if user_data.cooperative_code:
            from app.models.user import Cooperative, CooperativeMember
            # Find cooperative by code
            coop_query = select(Cooperative).where(Cooperative.code == user_data.cooperative_code)
            coop_result = await db.execute(coop_query)
            cooperative = coop_result.scalar_one_or_none()
            
            if cooperative:
                from sqlalchemy import func
                from datetime import datetime as _dt

                # Get cooperative's own sequential number (its position among all coops)
                coop_seq_result = await db.execute(
                    select(func.count()).select_from(Cooperative)
                    .where(Cooperative.created_at <= cooperative.created_at)
                )
                coop_seq = coop_seq_result.scalar() or 1

                # Get farmer's sequence number within this cooperative
                member_count_result = await db.execute(
                    select(func.count()).select_from(CooperativeMember)
                    .where(CooperativeMember.cooperative_id == cooperative.id)
                )
                farmer_seq = (member_count_result.scalar() or 0) + 1

                year = _dt.utcnow().year
                membership_number = f"PCF:{coop_seq:03d}/{year}/{farmer_seq:03d}"

                # Create cooperative membership
                membership = CooperativeMember(
                    user_id=user.id,
                    cooperative_id=cooperative.id,
                    is_active=True,
                    cooperative_role="member",
                    membership_number=membership_number
                )
                db.add(membership)
                await db.commit()
        
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"REGISTER ERROR: {str(e)}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred. Please try again later. ({str(e)})"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's profile.
    """
    return current_user


@router.get("/me/membership")
async def get_my_membership(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the current farmer's primary cooperative membership number."""
    from sqlalchemy import select, func
    from app.models.user import CooperativeMember, Cooperative
    result = await db.execute(
        select(CooperativeMember, Cooperative)
        .join(Cooperative, CooperativeMember.cooperative_id == Cooperative.id)
        .where(CooperativeMember.user_id == current_user.id)
        .where(CooperativeMember.is_active == True)
        .order_by(CooperativeMember.created_at)
        .limit(1)
    )
    row = result.first()
    if not row:
        return {"membership_number": None, "cooperative_name": None, "cooperative_code": None}
    membership, cooperative = row

    # Generate membership number if it was never assigned (legacy accounts)
    if not membership.membership_number:
        from sqlalchemy import func
        from datetime import datetime as _dt
        from app.models.user import CooperativeMember as CM
        coop_seq_result = await db.execute(
            select(func.count()).select_from(Cooperative).where(
                Cooperative.created_at <= cooperative.created_at
            )
        )
        coop_seq = coop_seq_result.scalar() or 1
        member_count_result = await db.execute(
            select(func.count()).select_from(CM).where(CM.cooperative_id == cooperative.id)
        )
        farmer_seq = (member_count_result.scalar() or 0)
        year = _dt.utcnow().year
        membership.membership_number = f"PCF:{coop_seq:03d}/{year}/{farmer_seq:03d}"
        await db.commit()

    return {
        "membership_number": membership.membership_number,
        "cooperative_name": cooperative.name,
        "cooperative_code": cooperative.code,
    }


@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    profile_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile.
    """
    from sqlalchemy import select, update
    from app.models.user import User
    
    # Build update fields (only non-None values)
    update_fields = {}
    allowed_fields = [
        'phone', 'id_number', 'date_of_birth', 'gender',
        'county', 'subcounty', 'ward', 'address', 'first_name', 'last_name',
        'profile_photo_url'
    ]
    
    for field in allowed_fields:
        if field in profile_data and profile_data[field] is not None:
            update_fields[field] = profile_data[field]
    
    # Handle kyc_data fields
    kyc_fields = ['id_type', 'gender', 'cooperative_code', 'payout_method', 
                  'payout_recipient_id', 'payout_bank_name', 'payout_account_number']
    
    # Build kyc_data if any kyc fields are provided
    kyc_updates = {}
    for field in kyc_fields:
        if field in profile_data and profile_data[field] is not None:
            kyc_updates[field] = profile_data[field]
    
    # Merge with existing kyc_data
    if kyc_updates:
        existing_kyc = current_user.kyc_data or {}
        existing_kyc.update(kyc_updates)
        update_fields['kyc_data'] = existing_kyc
    
    # Also store gender directly on user
    if 'gender' in profile_data and profile_data['gender'] is not None:
        update_fields['gender'] = profile_data['gender']
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    # Update user
    stmt = (
        update(User)
        .where(User.id == current_user.id)
        .values(**update_fields)
    )
    await db.execute(stmt)
    await db.commit()
    
    # Fetch updated user
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(..., min_length=8),
    confirm_password: str = Form(..., min_length=8),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change user password.
    """
    from app.core.auth import verify_password
    
    # Verify current password
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Confirm new password matches
    if new_password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(new_password)
    await db.commit()
    
    return {"message": "Password changed successfully"}


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """
    Logout endpoint.
    Note: JWT tokens are stateless, so this is mainly for client-side cleanup.
    """
    return {"message": "Successfully logged out"}


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    identifier: str = Form(..., alias="email"),
    db: AsyncSession = Depends(get_db)
):
    """
    Request a password reset. Accepts email or phone number.
    """
    from sqlalchemy import select, or_
    from datetime import datetime, timedelta
    import uuid
    from app.core.email import send_email
    from app.core.auth import _normalize_phone

    # Normalize phone if local format
    if '@' not in identifier and not identifier.startswith('+'):
        identifier = _normalize_phone(identifier) or identifier

    # Find user by email or phone
    if '@' in identifier:
        result = await db.execute(select(User).where(User.email == identifier))
    else:
        result = await db.execute(select(User).where(User.phone == identifier))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this phone/email"
        )
    
    # Generate reset token
    reset_token = str(uuid.uuid4())
    reset_expires = datetime.utcnow() + timedelta(hours=settings.auth.password_reset_token_expiry_hours)

    # Update user with reset token and expiry
    user.password_reset_token = reset_token
    user.password_reset_expires = reset_expires
    await db.commit()

    # Send reset email
    reset_link = f"{settings.app.frontend_base_url}/reset-password?token={reset_token}"
    subject = "Plotra Platform - Password Reset Request"
    text_content = f"""
    We received a request to reset your password for the Plotra Platform.
    
    To reset your password, please click the link below:
    
    {reset_link}
    
    This link will expire in 24 hours for security reasons.
    
    If you did not request a password reset, please ignore this email or contact our support team at support@plotra.africa.
    """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Password Reset Request</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                padding: 20px;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                padding: 20px 0;
                border-bottom: 1px solid #eeeeee;
            }}
            .content {{
                padding: 20px 0;
                line-height: 1.6;
            }}
            .button {{
                display: inline-block;
                background-color: #6f4e37;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                padding: 20px 0;
                border-top: 1px solid #eeeeee;
                color: #666666;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="color: #6f4e37;">Plotra Platform</h1>
                <p>Password Reset Request</p>
            </div>
            
            <div class="content">
                <p>We received a request to reset your password for the Plotra Platform.</p>
                
                <p>To reset your password, please click the button below:</p>
                
                <p style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </p>
                
                <p>This link will expire in 24 hours for security reasons.</p>
                
                <p>If you did not request a password reset, please ignore this email or contact our support team at <a href="mailto:support@plotra.africa">support@plotra.africa</a>.</p>
            </div>
            
            <div class="footer">
                <p>&copy; 2026 Plotra Platform. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send to email if available, otherwise we can only return the token for SMS (future)
    recipient_email = user.email
    if recipient_email:
        await send_email(recipient_email, subject, html_content, text_content)
        return {"message": "Password reset link sent to your email"}
    else:
        # No email on account — return token directly (SMS integration pending)
        return {"message": f"Reset token: {reset_token}. Use it at /reset-password."}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    token: str = Form(...),
    new_password: str = Form(..., min_length=8),
    confirm_password: str = Form(..., min_length=8),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using a valid reset token.
    """
    from sqlalchemy import select
    from datetime import datetime
    from app.core.auth import get_password_hash
    
    # Verify passwords match
    if new_password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    # Find user with valid reset token
    result = await db.execute(
        select(User).where(User.password_reset_token == token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    # Check if token has expired
    if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired"
        )
    
    # Update password and clear reset token
    user.password_hash = get_password_hash(new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    
    # Activate the user if they were pending verification
    from app.models.user import UserStatus
    if user.status == UserStatus.PENDING_VERIFICATION:
        user.status = UserStatus.ACTIVE
    
    await db.commit()
    
    return {"message": "Password reset successfully. Your account is now active."}


@router.get("/verify-token")
async def verify_token(
    current_user: User = Depends(get_current_user)
):
    """
    Verify if the current token is valid.
    """
    return {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.value
    }
