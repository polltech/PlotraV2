"""
Plotra Platform - User Models
Role-based access control with cooperative-level isolation
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Enum, Text, JSON, DateTime, ARRAY
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """User roles for the four-tier verification system"""
    FARMER = "farmer"
    COOPERATIVE_OFFICER = "cooperative_officer"
    PLOTRA_ADMIN = "plotra_admin"
    EUDR_REVIEWER = "eudr_reviewer"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized or member.name.lower() == normalized:
                    return member
        return super()._missing_(value)


class UserStatus(str, enum.Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized or member.name.lower() == normalized:
                    return member
        return super()._missing_(value)


class VerificationStatus(str, enum.Enum):
    """User verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized or member.name.lower() == normalized:
                    return member
        return super()._missing_(value)


class User(BaseModel):
    """
    User model with role-based access control.
    
    Roles:
    - Farmer: Field-level data entry, GPS mapping
    - Cooperative Officer: Cooperative management and member verification
    - Plotra Admin: System oversight, satellite analysis
    - EUDR Reviewer: Compliance review and certification
    - Super Admin: Full system access
    """
    
    __allow_unmapped__ = True
    __tablename__ = "users"
    
    # Verification status
    verification_status = Column(
        Enum(
            VerificationStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=True,
            name="verificationstatus",
        ),
        nullable=False,
        default=VerificationStatus.PENDING,
    )

    # Two-stage farmer verification tracking
    coop_status = Column(String(50), nullable=True)          # coop_approved / coop_rejected
    coop_verified_by_name = Column(String(150), nullable=True)
    coop_verified_at = Column(DateTime, nullable=True)
    coop_notes = Column(Text, nullable=True)
    admin_verified_by_name = Column(String(150), nullable=True)
    admin_verified_at = Column(DateTime, nullable=True)
    admin_notes = Column(Text, nullable=True)

    # Password reset fields
    password_reset_token = Column(String(255), nullable=True, unique=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # Authentication
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(20), nullable=True, index=True, unique=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(DateTime, nullable=True)
    national_id = Column(String(50), nullable=True, unique=True)
    
    # EUDR Compliance - Hard stop fields
    gender = Column(String(20), nullable=True)  # Male, Female, Other
    payout_recipient_id = Column(String(20), nullable=True)  # M-Pesa number for Phase 2 payments
    data_consent = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime, nullable=True)
    
    # Role and permissions
    role = Column(
        Enum(
            UserRole,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=True,
            name="userrole",
        ),
        nullable=False,
        default=UserRole.FARMER,
    )
    status = Column(
        Enum(
            UserStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=True,
            name="userstatus",
        ),
        nullable=False,
        default=UserStatus.PENDING_VERIFICATION,
    )
    
    # Security
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    
    # Location
    country = Column(String(100), default="Kenya")
    county = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    
    # Preferences
    language = Column(String(10), default="en")
    timezone = Column(String(50), default="Africa/Nairobi")
    notification_preferences = Column(JSON, nullable=True)
    
    # Metadata
    kyc_data = Column(JSON, nullable=True)
    profile_photo_url = Column(String(500), nullable=True)
    
    # Relationships
    cooperative_memberships = relationship("CooperativeMember", back_populates="user", cascade="all, delete-orphan")
    # owned_farms - removed to fix relationship issue
    verification_records = relationship("VerificationRecord", back_populates="reviewer")
    
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def can_access_cooperative(self, cooperative_id: str) -> bool:
        """
        Check if user can access a specific cooperative.
        
        Args:
            cooperative_id: ID of the cooperative
            
        Returns:
            True if user has access
        """
        if self.role == UserRole.PLOTRA_ADMIN:
            return True
        
        if self.role == UserRole.EUDR_REVIEWER:
            return True
        
        # Check cooperative membership
        for membership in self.cooperative_memberships:
            if membership.cooperative_id == cooperative_id and membership.is_active:
                return True
        
        return False
    
    def can_verify(self) -> bool:
        """Check if user can verify records"""
        return self.role in [
            UserRole.COOPERATIVE_OFFICER,
            UserRole.PLOTRA_ADMIN,
            UserRole.EUDR_REVIEWER
        ]
    
    def can_manage_users(self) -> bool:
        """Check if user can manage other users"""
        return self.role in [
            UserRole.COOPERATIVE_OFFICER,
            UserRole.PLOTRA_ADMIN
        ]


class Cooperative(BaseModel):
    """
    Cooperative model for grouping farmers.
    Implements cooperative-level access isolation with detailed information.
    """
    
    __tablename__ = "cooperatives"
    
    # Identification
    name = Column(String(255), nullable=False)
    code = Column(String(20), unique=True, nullable=False)  # Unique code for farmer registration
    registration_number = Column(String(50), unique=True, nullable=True)
    tax_id = Column(String(50), nullable=True)
    
    # Contact
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Address
    address = Column(Text, nullable=True)
    country = Column(String(100), default="Kenya")
    county = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    subcounty = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    
    # Location coordinates
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    
    # Organization
    cooperative_type = Column(String(100), nullable=True)
    establishment_date = Column(DateTime, nullable=True)
    member_count = Column(Integer, default=0)
    
    # Additional details
    contact_person = Column(String(255), nullable=True)
    contact_person_phone = Column(String(20), nullable=True)
    contact_person_email = Column(String(255), nullable=True)
    legal_status = Column(String(100), nullable=True)
    governing_document = Column(String(500), nullable=True)
    
    # Required documents array (stored as JSON for database compatibility)
    required_documents = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    verification_status = Column(String(50), default="pending")
    verification_date = Column(DateTime, nullable=True)
    
    # Relationships
    members = relationship("CooperativeMember", back_populates="cooperative", cascade="all, delete-orphan")
    primary_officer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    farms = relationship("Farm", back_populates="cooperative")
    warehouses = relationship("Warehouse", back_populates="cooperative")
    batches = relationship("Batch", back_populates="cooperative")
    
    def get_member_count(self) -> int:
        """Get count of active members"""
        return len([m for m in self.members if m.is_active])


class CooperativeMember(BaseModel):
    """
    Association table for cooperative membership.
    Farmers can belong to multiple cooperatives.
    Implements record-level access control with roles.
    """
    
    __tablename__ = "cooperative_members"
    
    # Foreign keys
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cooperative_id = Column(String(36), ForeignKey("cooperatives.id"), nullable=False)
    
    # Membership details
    membership_number = Column(String(50), nullable=True)
    membership_type = Column(String(50), default="regular")  # regular, board, staff
    join_date = Column(DateTime, default=datetime.utcnow)
    exit_date = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)
    verification_status = Column(String(50), default="pending")
    
    # Role in cooperative
    cooperative_role = Column(String(100), default="member")
    
    # Relationships
    user = relationship("User", back_populates="cooperative_memberships")
    cooperative = relationship("Cooperative", back_populates="members")
    
    def can_access_record(self, record_cooperative_id: str) -> bool:
        """
        Check if member can access a record from another cooperative.
        
        Args:
            record_cooperative_id: ID of the cooperative that owns the record
            
        Returns:
            True if access is allowed
        """
        return self.cooperative_id == record_cooperative_id and self.is_active
