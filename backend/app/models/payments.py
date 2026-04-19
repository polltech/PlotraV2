"""
Plotra Platform - Payments Module (Future-Ready)
Escrow records and conditional payout triggers
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class PayoutStatus(str, enum.Enum):
    """Payout status"""
    PENDING = "pending"
    ESCROW = "escrow"
    CONDITIONAL = "conditional"
    RELEASED = "released"
    FAILED = "failed"


class IncentiveType(str, enum.Enum):
    """Types of incentives"""
    YIELD_BONUS = "yield_bonus"
    QUALITY_BONUS = "quality_bonus"
    SUSTAINABILITY_BONUS = "sustainability_bonus"
    VERIFICATION_BONUS = "verification_bonus"
    EUDR_COMPLIANCE = "eudr_compliance"


class PaymentEscrow(BaseModel):
    """
    Escrow record for conditional payments.
    Supports future M-Pesa integration.
    """
    
    __tablename__ = "payment_escrows"
    
    # Reference
    reference_number = Column(String(100), unique=True, nullable=False, index=True)
    
    # Payer/Payee
    payer_id = Column(String(36), nullable=True)  # Cooperative or buyer
    payer_name = Column(String(255), nullable=True)
    payee_id = Column(String(36), nullable=False)  # Farmer or cooperative
    payee_name = Column(String(255), nullable=True)
    
    # Amount
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="KES")
    
    # Status
    status = Column(Enum(PayoutStatus), default=PayoutStatus.PENDING)
    
    # Conditions
    conditions = Column(JSON, nullable=False)  # Release conditions
    conditions_met = Column(JSON, nullable=True)
    
    # Timeline
    escrow_date = Column(DateTime, default=datetime.utcnow)
    release_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    
    # Payment details
    payment_method = Column(String(50), nullable=True)  # "mpesa", "bank", "cash"
    payment_reference = Column(String(100), nullable=True)
    transaction_id = Column(String(100), nullable=True)
    
    # Digital signatures
    payer_signature = Column(String(512), nullable=True)
    payee_signature = Column(String(512), nullable=True)
    
    # Notes
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


class IncentiveRule(BaseModel):
    """
    Incentive rules for conditional payouts.
    Evaluates farmer performance against criteria.
    """
    
    __tablename__ = "incentive_rules"
    
    # Rule identification
    rule_code = Column(String(100), unique=True, nullable=False)
    rule_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Incentive type
    incentive_type = Column(Enum(IncentiveType), nullable=False)
    
    # Calculation
    calculation_type = Column(String(50), nullable=False)  # "percentage", "fixed", "tiered"
    base_amount = Column(Float, nullable=True)
    percentage_rate = Column(Float, nullable=True)
    tier_config = Column(JSON, nullable=True)  # Tiered calculation config
    
    # Conditions
    conditions = Column(JSON, nullable=False)  # Rule conditions
    minimum_threshold = Column(Float, nullable=True)
    maximum_amount = Column(Float, nullable=True)
    
    # Scope
    applies_to_cooperative_id = Column(String(36), nullable=True)  # Null = all
    applies_to_crop_year = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Integer, default=1)
    effective_from = Column(DateTime, nullable=True)
    effective_until = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PayoutTrigger(BaseModel):
    """
    Tracks payout trigger evaluations.
    Links to escrow records when conditions are met.
    """
    
    __tablename__ = "payout_triggers"
    
    # Trigger details
    trigger_type = Column(String(50), nullable=False)  # "scheduled", "event", "manual"
    rule_id = Column(String(36), ForeignKey("incentive_rules.id"), nullable=True)
    escrow_id = Column(String(36), ForeignKey("payment_escrows.id"), nullable=True)
    
    # Entity
    entity_type = Column(String(50), nullable=False)  # "farmer", "cooperative", "batch"
    entity_id = Column(String(36), nullable=False)
    
    # Evaluation
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    conditions_met = Column(JSON, nullable=True)
    calculated_amount = Column(Float, nullable=True)
    
    # Result
    triggered = Column(Integer, default=0)  # 0=no, 1=yes
    payout_created = Column(Integer, default=0)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    rule = relationship("IncentiveRule")


class DigitalSignature(BaseModel):
    """
    Digital signatures for payment authorization.
    Supports key recovery mechanism.
    """
    
    __tablename__ = "digital_signatures"
    
    # Signature details
    signature_id = Column(String(36), unique=True, nullable=False)
    entity_type = Column(String(50), nullable=False)  # "user", "organization"
    entity_id = Column(String(36), nullable=False)
    
    # Keys
    public_key = Column(Text, nullable=True)
    encrypted_private_key = Column(Text, nullable=True)
    key_fingerprint = Column(String(64), nullable=True)
    
    # Status
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    
    # Key recovery
    recovery_email = Column(String(255), nullable=True)
    recovery_phone = Column(String(20), nullable=True)
    recovery_verified = Column(Integer, default=0)
