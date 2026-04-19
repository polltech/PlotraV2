"""
Plotra Platform - User Models
Four-tier verification system: Farmer, Coop Admin, Platform Admin, Auditor
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from .base import BaseModel, UUIDMixin


class UserRole(str, enum.Enum):
    """User roles for the four-tier verification system"""
    FARMER = "farmer"
    COOP_ADMIN = "coop_admin"
    COOP_OFFICER = "coop_officer"  # Factor/competent person for verification
    PLATFORM_ADMIN = "platform_admin"
    PLOTRA_ADMIN = "plotra_admin"
    EUDR_REVIEWER = "eudr_reviewer"  # Belgian team reviewer
    AUDITOR = "auditor"
    SUPER_ADMIN = "super_admin"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized or member.name.lower() == normalized:
                    return member
        return super()._missing_(value)


class VerificationStatus(str, enum.Enum):
    """KYC verification status"""
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


class UserStatus(str, enum.Enum):
    """User account status"""
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized or member.name.lower() == normalized:
                    return member
        return super()._missing_(value)


class User(BaseModel, UUIDMixin):
    __tablename__ = "users"
    """
    User model supporting the four-tier verification system.
    
    Tiers:
    - Farmer: Field-level data entry, GPS mapping
    - Coop Admin: Cooperative verification and management
    - Platform Admin: System oversight and satellite analysis
    - Auditor: Compliance review and certification
    """
    
    __allow_unmapped__ = True
    
    # Authentication fields
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    
    # Role and permissions
    role = Column(String(19), nullable=False, default="farmer")
    status = Column(String(20), nullable=False, default="active")
    verification_status = Column(String(20), nullable=False, default="pending")
    
    # Profile information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(DateTime, nullable=True)
    national_id = Column(String(50), nullable=True, unique=True)
    
    # Address
    country = Column(String(100), default="Kenya")
    county = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    
    # Security
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    
    # Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # Relationships
    # Relationships - temporarily simplified for authentication
    # farm relationship requires Farm.owner relationship
    # cooperative_memberships requires proper FK setup in all related tables
    
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def is_farmer(self) -> bool:
        return self.role == UserRole.FARMER
    
    def is_coop_admin(self) -> bool:
        return self.role == UserRole.COOP_ADMIN
    
    def is_platform_admin(self) -> bool:
        return self.role == UserRole.PLATFORM_ADMIN
    
    def is_auditor(self) -> bool:
        return self.role == UserRole.AUDITOR
    
    def can_verify(self) -> bool:
        """Check if user can verify other users"""
        return self.role in [UserRole.COOP_ADMIN, UserRole.PLATFORM_ADMIN, UserRole.AUDITOR]


class CooperativeMember(BaseModel, UUIDMixin):
    __tablename__ = "cooperative_member"
    """
    Association table for cooperative membership.
    Farmers can belong to multiple cooperatives.
    """
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cooperative_id = Column(String(36), ForeignKey("cooperative.id"), nullable=False)
    membership_number = Column(String(50), nullable=True)
    join_date = Column(DateTime, default=datetime.utcnow)
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    
    # Role in cooperative (Member / Lead / Admin)
    cooperative_role = Column(String(50), default="member")  # "member", "lead", "admin"
    
    user = relationship("User", foreign_keys=[user_id])
    cooperative = relationship("Cooperative", foreign_keys=[cooperative_id])


class CooperativeType(str, enum.Enum):
    """Cooperative type for categorization"""
    GENERAL = "general"
    WOMEN_BASED = "women"


class Cooperative(BaseModel, UUIDMixin):
    __tablename__ = "cooperative"
    """
    Cooperative model for grouping farmers.
    Coop Admins manage member verification and coffee batch creation.
    """
    
    name = Column(String(255), nullable=False)
    code = Column(String(20), unique=True, nullable=False)  # Unique code for farmer registration
    registration_number = Column(String(50), unique=True, nullable=True)
    address = Column(Text, nullable=True)
    
    # Contact information
    phone = Column(String(20), nullable=True)  # Main phone (kept for backward compatibility)
    contact_phone = Column(String(20), nullable=True)  # Contact phone
    contact_email = Column(String(255), nullable=True)  # Contact email (renamed from email)
    
    # Location
    country = Column(String(100), default="Kenya")
    county = Column(String(100), nullable=True)
    subcounty = Column(String(100), nullable=True)
    
    # Cooperative type
    cooperative_type = Column(String(20), nullable=True)  # "general" or "women"
    
    # Admin (assigned Coop Admin)
    primary_admin_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Contact person user (optional)
    contact_person_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime, nullable=True)
    
    # Relationships - simplified
    carbon_projects = relationship("CarbonProject", back_populates="cooperative")
