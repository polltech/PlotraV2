"""
Plotra Platform - Authentication Module
JWT-based authentication with role-based access control
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .config import settings
from .database import get_db
from app.models.user import User, UserRole
from app.models.verification import VerificationStatus


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v2/auth/token",
    scheme_name="JWT",
)

# Form-based OAuth2 for browser compatibility
oauth2_scheme_form = OAuth2PasswordBearer(
    tokenUrl="/api/v2/auth/token-form",
    scheme_name="JWT Form",
    auto_error=False,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data to encode
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.app.access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.app.secret_key,
        algorithm=settings.app.algorithm
    )
    
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.app.secret_key,
            algorithms=[settings.app.algorithm]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If user not found or inactive
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise credentials_exception
    
    # Fetch user from database
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Ensure the current user is active.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Active User object
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return current_user


def require_role(allowed_roles: list[UserRole]):
    """
    Dependency factory for role-based access control.
    
    Args:
        allowed_roles: List of roles allowed to access the endpoint
        
    Returns:
        Dependency function
        
    Raises:
        HTTPException: If user role not in allowed list
    """
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        # Plotra admin has full access
        if user_role.lower() == UserRole.PLOTRA_ADMIN.value.lower():
            return current_user
            
        if user_role.lower() not in [r.value.lower() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(r.value for r in allowed_roles)}"
            )
        return current_user
    
    return role_checker


# Pre-configured role checkers
require_farmer = require_role([UserRole.FARMER])
require_coop_admin = require_role([UserRole.COOPERATIVE_OFFICER])
require_plotra_admin = require_role([UserRole.PLOTRA_ADMIN])
require_platform_admin = require_role([UserRole.PLOTRA_ADMIN])
require_auditor = require_role([UserRole.EUDR_REVIEWER])
require_admin = require_role([UserRole.PLOTRA_ADMIN, UserRole.COOPERATIVE_OFFICER, UserRole.EUDR_REVIEWER])


def _normalize_phone(phone: str) -> Optional[str]:
    """Normalize a local phone number to E.164 (Kenya default)."""
    import re
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 9:
        return '+254' + digits
    if len(digits) == 10 and digits.startswith('0'):
        return '+254' + digits[1:]
    return None


def _to_local_phone(phone: str) -> Optional[str]:
    """Convert E.164 (+254...) to local (0...) format."""
    import re
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('254'):
        return '0' + digits[3:]
    return None


async def authenticate_user(
    db: AsyncSession,
    identifier: str,
    password: str
) -> Optional[User]:
    """
    Authenticate a user by email/phone and password.
    Accepts phone in E.164 (+254712345678) or local format (0712345678).
    """
    # Determine if identifier is email or phone
    if '@' in identifier:
        query = select(User).where(User.email == identifier)
    else:
        # Build all phone variants (as-is, E.164, local) and match any
        normalized = _normalize_phone(identifier)
        local = _to_local_phone(identifier)
        candidates = list({identifier, normalized, local} - {None})
        query = select(User).where(User.phone.in_(candidates))

    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.auth.max_login_attempts:
            user.is_locked = True
        await db.commit()
        return None
    
    # Check if account is locked
    if user.is_locked:
        return None
    
    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.last_login = datetime.utcnow()
    await db.commit()
    
    return user


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: UserRole = UserRole.FARMER,
    phone_number: Optional[str] = None,
    **kwargs
) -> User:
    """
    Create a new user with hashed password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        first_name: User first name
        last_name: User last name
        role: User role
        phone_number: Optional phone number
        **kwargs: Additional user fields
        
    Returns:
        Created User object
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == email)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise ValueError(f"User with email {email} already exists")
    
    user = User(
        email=email,
        password_hash=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        role=role,
        phone_number=phone_number,
        verification_status=VerificationStatus.PENDING,
        **kwargs
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


class TokenData:
    """Data class for JWT token payload"""
    def __init__(
        self,
        user_id: str,
        email: str,
        role: str,
        exp: datetime = None
    ):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.exp = exp
    
    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TokenData":
        return cls(
            user_id=payload.get("sub"),
            email=payload.get("email"),
            role=payload.get("role"),
            exp=payload.get("exp")
        )
