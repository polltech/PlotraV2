"""
Plotra Platform - Sustainability & Incentive Models
Layer 3: Sustainability Classification & Transition Engine
Layer 4: Incentives & Premium Logic Engine
Layer 5: Conditional Payments & Settlement
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel, UUIDMixin


class PracticeState(str, enum.Enum):
    """Farm practice states for sustainability transition"""
    MONOCROP = "monocrop"
    TRANSITION = "transition"
    AGROFORESTRY = "agroforestry"
    HERITAGE = "heritage"


class TransitionEventType(str, enum.Enum):
    """Types of practice transition events"""
    INTERCROPPING = "intercropping"
    AGROFORESTRY_ADOPTION = "agroforestry_adoption"
    SHADE_TREE_PLANTING = "shade_tree_planting"
    ORGANIC_CONVERSION = "organic_conversion"
    WATER_CONSERVATION = "water_conservation"


class PracticeLog(BaseModel, UUIDMixin):
    __tablename__ = "practice_log"
    """
    Agricultural practice log for sustainability tracking.
    Tracks pruning, harvesting, intercropping events.
    Layer 1: Practice_logs for satellite cross-reference.
    """
    
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=False)
    
    # Practice details
    practice_type = Column(String(100), nullable=False)  # "pruning", "fertilizing", "harvesting"
    practice_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    description = Column(Text, nullable=True)
    
    # Inputs
    inputs_used = Column(JSON, nullable=True)  # Fertilizers, pesticides, etc.
    quantity = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    
    # Method
    method = Column(String(100), nullable=True)
    labor_hours = Column(Float, nullable=True)
    
    # Compliance
    is_organic = Column(Boolean, default=False)
    is_fairtrade = Column(Boolean, default=False)
    
    # GPS location of practice
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Photo evidence
    photo_url = Column(String(500), nullable=True)
    
    # Relationships
    parcel = relationship("LandParcel", back_populates="practice_logs")


class TransitionEvent(BaseModel, UUIDMixin):
    __tablename__ = "transition_event"
    """
    Tracks sustainability practice transitions.
    Layer 3: Moves farmer from Monocrop → Mixed → Agroforestry.
    """
    
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=False)
    
    # Transition details
    event_type = Column(Enum(TransitionEventType), nullable=False)
    from_state = Column(Enum(PracticeState), nullable=False)
    to_state = Column(Enum(PracticeState), nullable=False)
    event_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Description
    description = Column(Text, nullable=True)
    
    # Evidence
    evidence_photos = Column(JSON, nullable=True)
    satellite_correlation = Column(JSON, nullable=True)  # Cross-reference with satellite
    
    # Biomass impact (for carbon)
    biomass_change_tons = Column(Float, nullable=True)
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_date = Column(DateTime, nullable=True)
    
    # Relationships
    parcel = relationship("LandParcel", back_populates="transition_events")


class BiomassLedger(BaseModel, UUIDMixin):
    __tablename__ = "biomass_ledger"
    """
    Biomass accumulation ledger for carbon tracking.
    Layer 3: Quarterly updates to carbon baseline.
    Layer 7: Aggregates micro-scale biomass into tradeable units.
    """
    
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=False)
    
    # Reporting period
    quarter = Column(Integer, nullable=False)  # 1-4
    year = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Biomass measurements
    biomass_tons = Column(Float, nullable=False)
    biomass_source = Column(String(50), default="satellite")  # "satellite", "field", "model"
    
    # Carbon calculation
    carbon_tons_co2 = Column(Float, nullable=True)
    conversion_factor = Column(Float, default=0.5)  # Default biomass to carbon
    
    # Change from previous period
    biomass_change_tons = Column(Float, nullable=True)
    biomass_change_percent = Column(Float, nullable=True)
    
    # Verification status
    is_verified = Column(Boolean, default=False)
    
    # Relationships
    parcel = relationship("LandParcel", back_populates="biomass_ledger")


# ==================== LAYER 4: INCENTIVES & PREMIUM LOGIC ====================

class IncentiveType(str, enum.Enum):
    """Types of incentives"""
    YIELD_BONUS = "yield_bonus"
    QUALITY_BONUS = "quality_bonus"
    SUSTAINABILITY_BONUS = "sustainability_bonus"
    VERIFICATION_BONUS = "verification_bonus"
    EUDR_COMPLIANCE = "eudr_compliance"
    GENDER_INCENTIVE = "gender_incentive"  # Women farmers bonus
    HERITAGE_BONUS = "heritage_bonus"


class IncentiveRule(BaseModel, UUIDMixin):
    __tablename__ = "incentive_rule"
    """
    Incentive rules for conditional payouts.
    Layer 4: JSON-based conditions for premium calculation.
    """
    
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
    
    # Conditions (JSON logic)
    # Example: {"heritage_slope": {"$gt": 0.05}, "gender": "F"}
    conditions = Column(JSON, nullable=False)
    minimum_threshold = Column(Float, nullable=True)
    maximum_amount = Column(Float, nullable=True)
    
    # Scope
    applies_to_cooperative_id = Column(Integer, ForeignKey("cooperative.id"), nullable=True)
    applies_to_crop_year = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    effective_from = Column(DateTime, nullable=True)
    effective_until = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IncentiveClaim(BaseModel, UUIDMixin):
    __tablename__ = "incentive_claim"
    """
    Individual incentive claims generated from rules.
    Layer 4: Tracks which farmers qualify for which premiums.
    """
    
    farmer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("incentive_rule.id"), nullable=False)
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=True)
    
    # Claim details
    claim_number = Column(String(100), unique=True, nullable=False)
    claim_date = Column(DateTime, default=datetime.utcnow)
    
    # Calculation
    base_amount = Column(Float, nullable=False)
    bonus_amount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="KES")
    
    # Conditions met
    conditions_met = Column(JSON, nullable=True)
    
    # Status
    status = Column(String(50), default="pending")  # pending, approved, paid, rejected
    approved_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_date = Column(DateTime, nullable=True)
    
    # Payment
    payment_date = Column(DateTime, nullable=True)
    payment_reference = Column(String(100), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    farmer = relationship("User", foreign_keys=[farmer_id])
    rule = relationship("IncentiveRule")


# ==================== LAYER 5: CONDITIONAL PAYMENTS ====================

class PayoutStatus(str, enum.Enum):
    """Payout status"""
    PENDING = "pending"
    ESCROW = "escrow"
    CONDITIONAL = "conditional"
    RELEASED = "released"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentEscrow(BaseModel, UUIDMixin):
    __tablename__ = "payment_escrow"
    """
    Escrow record for conditional payments.
    Layer 5: Triggered by delivery_confirmed + verification_passed.
    """
    
    # Reference
    reference_number = Column(String(100), unique=True, nullable=False)
    
    # Payer/Payee
    payer_id = Column(Integer, nullable=True)  # Cooperative or buyer
    payer_name = Column(String(255), nullable=True)
    payee_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    payee_name = Column(String(255), nullable=True)
    
    # Payment recipient (M-Pesa/Wallet - ensures financial agency)
    payout_recipient_id = Column(String(100), nullable=True)  # M-Pesa number or wallet ID
    payout_method = Column(String(50), default="mpesa")  # "mpesa", "bank", "cash"
    
    # Amount
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="KES")
    
    # Status
    status = Column(Enum(PayoutStatus), default=PayoutStatus.PENDING)
    
    # Conditions
    conditions = Column(JSON, nullable=False)  # Release conditions
    conditions_met = Column(JSON, nullable=True)
    
    # Trigger reference
    delivery_id = Column(Integer, ForeignKey("delivery.id"), nullable=True)
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=True)
    
    # Timeline
    escrow_date = Column(DateTime, default=datetime.utcnow)
    release_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    
    # Payment details
    payment_reference = Column(String(100), nullable=True)
    transaction_id = Column(String(100), nullable=True)
    
    # Digital signatures
    payer_signature = Column(String(512), nullable=True)
    payee_signature = Column(String(512), nullable=True)
    
    # Notes
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    payee = relationship("User", foreign_keys=[payee_id])


class DigitalSignature(BaseModel, UUIDMixin):
    __tablename__ = "digital_signature"
    """
    Digital signatures for payment and delivery authorization.
    Layer 5: Offline-compatible keys for farmers to sign deliveries.
    """
    
    # Signature details
    signature_id = Column(String(36), unique=True, nullable=False)
    entity_type = Column(String(50), nullable=False)  # "user", "organization"
    entity_id = Column(Integer, nullable=False)
    
    # Keys
    public_key = Column(Text, nullable=True)
    encrypted_private_key = Column(Text, nullable=True)
    key_fingerprint = Column(String(64), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    
    # Key recovery
    recovery_email = Column(String(255), nullable=True)
    recovery_phone = Column(String(20), nullable=True)
    recovery_verified = Column(Boolean, default=False)


# ==================== LAYER 6: BUYER & CONSUMER INTERFACES ====================

class ImpactClaimType(str, enum.Enum):
    """Types of impact claims"""
    HERITAGE = "heritage"
    AGROFORESTRY = "agroforestry"
    ORGANIC = "organic"
    CARBON_NEGATIVE = "carbon_negative"
    WATER_CONSERVATION = "water_conservation"
    BIODIVERSITY = "biodiversity"


class ImpactClaim(BaseModel, UUIDMixin):
    __tablename__ = "impact_claim"
    """
    Verifiable claims for buyers/roasters.
    Layer 6: e.g., "10 Years of Forest Stewardship"
    """
    
    # Claim identification
    claim_number = Column(String(100), unique=True, nullable=False)
    claim_type = Column(Enum(ImpactClaimType), nullable=False)
    
    # Entity
    entity_type = Column(String(50), nullable=False)  # "farm", "parcel", "cooperative"
    entity_id = Column(Integer, nullable=False)
    
    # Claim details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    claim_value = Column(String(100), nullable=True)  # e.g., "10 years", "50 hectares"
    
    # Evidence
    evidence_start_date = Column(DateTime, nullable=True)
    evidence_end_date = Column(DateTime, nullable=True)
    supporting_documents = Column(JSON, nullable=True)
    satellite_analysis_ids = Column(JSON, nullable=True)
    
    # Validity
    issue_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    is_verified = Column(Boolean, default=False)
    verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # QR Code for consumer access
    qr_code_data = Column(String(500), nullable=True)
    
    # Relationships
    verified_by = relationship("User", foreign_keys=[verified_by_id])


class DigitalProductPassport(BaseModel, UUIDMixin):
    __tablename__ = "digital_product_passport"
    """
    EU Digital Product Passport for coffee.
    Layer 6: QR-linked journey showing Heritage → Compliance → Future.
    """
    
    farm_id = Column(Integer, ForeignKey("farm.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=True)
    
    # Passport identification
    passport_number = Column(String(100), unique=True, nullable=False)
    version = Column(String(20), default="1.0")
    
    # Product information
    product_name = Column(String(255), nullable=False)
    product_description = Column(Text, nullable=True)
    
    # Origin
    country_of_origin = Column(String(100), nullable=True)
    region_of_origin = Column(String(100), nullable=True)
    harvest_date = Column(DateTime, nullable=True)
    
    # Sustainability data (Layer 6: separate from EUDR for Phase 2)
    certifications = Column(JSON, nullable=True)  # Organic, Fairtrade, Rainforest
    sustainability_score = Column(Float, nullable=True)
    
    # Supply chain
    supply_chain_nodes = Column(JSON, nullable=True)  # Farm → Coop → Exporter → Importer
    chain_of_custody = Column(JSON, nullable=True)
    
    # Carbon footprint
    carbon_footprint_kg_co2 = Column(Float, nullable=True)
    carbon_offset = Column(Float, nullable=True)
    
    # Compliance (EUDR specific - for Phase 1)
    eudr_compliant = Column(Boolean, default=False)
    compliance_certificates = Column(JSON, nullable=True)
    
    # Heritage (Pre-2020 data)
    heritage_verified = Column(Boolean, default=False)
    heritage_start_date = Column(DateTime, nullable=True)
    
    # QR Code
    qr_code_data = Column(String(500), nullable=True)
    
    # Relationships
    farm = relationship("Farm", foreign_keys=[farm_id])


# ==================== LAYER 7: CARBON READINESS ====================

class CarbonProjectStatus(str, enum.Enum):
    """Carbon project status"""
    DRAFT = "draft"
    VERIFICATION = "verification"
    APPROVED = "approved"
    REGISTERED = "registered"
    ISSUED = "issued"  # Tokens issued
    EXPIRED = "expired"


class CarbonProject(BaseModel, UUIDMixin):
    __tablename__ = "carbon_project"
    """
    Carbon project aggregating multiple parcels.
    Layer 7: Aggregates micro-scale biomass into tradeable units.
    """
    
    # Project identification
    project_name = Column(String(255), nullable=False)
    project_code = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Cooperative
    cooperative_id = Column(Integer, ForeignKey("cooperative.id"), nullable=False)
    
    # Carbon standard
    carbon_standard = Column(String(100), nullable=True)  # VCS, Gold Standard, etc.
    methodology = Column(String(255), nullable=True)
    
    # Area
    total_area_hectares = Column(Float, nullable=False)
    parcel_count = Column(Integer, default=0)
    
    # Carbon metrics
    baseline_carbon_tons = Column(Float, nullable=True)
    current_carbon_tons = Column(Float, nullable=True)
    projected_carbon_tons = Column(Float, nullable=True)
    
    # Status
    status = Column(Enum(CarbonProjectStatus), default=CarbonProjectStatus.DRAFT)
    registration_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    
    # Risk buffers
    permanence_buffer_percent = Column(Float, default=20.0)
    leakage_risk_percent = Column(Float, default=10.0)
    
    # Relationships
    cooperative = relationship("Cooperative", foreign_keys=[cooperative_id])


class CarbonToken(BaseModel, UUIDMixin):
    __tablename__ = "carbon_token"
    """
    Carbon tokens representing verified carbon sequestration.
    Layer 7: Shards large carbon batches back to individual parcel contributions.
    """
    
    # Token identification
    token_id = Column(String(100), unique=True, nullable=False)
    project_id = Column(Integer, ForeignKey("carbon_project.id"), nullable=False)
    
    # Parcel contribution
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=False)
    farmer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Carbon amount
    carbon_tons = Column(Float, nullable=False)
    carbon_tons_co2 = Column(Float, nullable=False)  # Converted to CO2 equivalent
    
    # Token details
    serial_number = Column(String(100), nullable=False)
    vintage_year = Column(Integer, nullable=False)
    
    # Status
    status = Column(String(50), default="issued")  # issued, retired, transferred
    issue_date = Column(DateTime, default=datetime.utcnow)
    retirement_date = Column(DateTime, nullable=True)
    
    # Verification
    verification_standard = Column(String(100), nullable=True)
    verification_body = Column(String(255), nullable=True)
    
    # Value
    price_per_ton_usd = Column(Float, nullable=True)
    
    # Relationships
    project = relationship("CarbonProject", foreign_keys=[project_id])
    parcel = relationship("LandParcel", back_populates="carbon_tokens")
    farmer = relationship("User", foreign_keys=[farmer_id])


