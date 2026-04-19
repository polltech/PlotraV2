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


class TransitionEvent(BaseModel):
    __tablename__ = "transition_events"
    """
    Tracks sustainability practice transitions.
    Layer 3: Moves farmer from Monocrop → Mixed → Agroforestry.
    """
    
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False)
    
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


class BiomassLedger(BaseModel):
    __tablename__ = "biomass_ledgers"
    """
    Biomass accumulation ledger for carbon tracking.
    Layer 3: Quarterly updates to carbon baseline.
    Layer 7: Aggregates micro-scale biomass into tradeable units.
    """
    
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False)
    
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
    parcel = relationship("LandParcel", back_populates="biomass_ledgers")


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


class IncentiveClaim(BaseModel):
    __tablename__ = "incentive_claims"
    """
    Individual incentive claims generated from rules.
    Layer 4: Tracks which farmers qualify for which premiums.
    """
    
    farmer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    rule_id = Column(String(36), ForeignKey("incentive_rules.id"), nullable=False)
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=True)
    
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


# ==================== LAYER 6: BUYER & CONSUMER INTERFACES ====================

class ImpactClaimType(str, enum.Enum):
    """Types of impact claims"""
    HERITAGE = "heritage"
    AGROFORESTRY = "agroforestry"
    ORGANIC = "organic"
    CARBON_NEGATIVE = "carbon_negative"
    WATER_CONSERVATION = "water_conservation"
    BIODIVERSITY = "biodiversity"


class ImpactClaim(BaseModel):
    __tablename__ = "impact_claims"
    """
    Verifiable claims for buyers/roasters.
    Layer 6: e.g., "10 Years of Forest Stewardship"
    """
    
    # Claim identification
    claim_number = Column(String(100), unique=True, nullable=False)
    claim_type = Column(Enum(ImpactClaimType), nullable=False)
    
    # Entity
    entity_type = Column(String(50), nullable=False)  # "farm", "parcel", "cooperative"
    entity_id = Column(String(36), nullable=False)
    
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





# ==================== LAYER 7: CARBON READINESS ====================

class CarbonProjectStatus(str, enum.Enum):
    """Carbon project status"""
    DRAFT = "draft"
    VERIFICATION = "verification"
    APPROVED = "approved"
    REGISTERED = "registered"
    ISSUED = "issued"  # Tokens issued
    EXPIRED = "expired"


class CarbonProject(BaseModel):
    __tablename__ = "carbon_projects"
    """
    Carbon project aggregating multiple parcels.
    Layer 7: Aggregates micro-scale biomass into tradeable units.
    """
    
    # Project identification
    project_name = Column(String(255), nullable=False)
    project_code = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Cooperative
    cooperative_id = Column(String(36), ForeignKey("cooperatives.id"), nullable=False)
    
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
    cooperative = relationship("Cooperative", back_populates="carbon_projects")


class CarbonToken(BaseModel):
    __tablename__ = "carbon_tokens"
    """
    Carbon tokens representing verified carbon sequestration.
    Layer 7: Shards large carbon batches back to individual parcel contributions.
    """
    
    # Token identification
    token_id = Column(String(100), unique=True, nullable=False)
    project_id = Column(String(36), ForeignKey("carbon_projects.id"), nullable=False)
    
    # Parcel contribution
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False)
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
    project = relationship("CarbonProject", back_populates="tokens")
    parcel = relationship("LandParcel", back_populates="carbon_tokens")
    farmer = relationship("User", foreign_keys=[farmer_id])


# Update LandParcel to include new relationships
from .farm import LandParcel
LandParcel.transition_events = relationship("TransitionEvent", back_populates="parcel")
LandParcel.biomass_ledgers = relationship("BiomassLedger", back_populates="parcel")
LandParcel.carbon_tokens = relationship("CarbonToken", back_populates="parcel")

# Update Cooperative to include CarbonProjects
from .user import Cooperative
Cooperative.carbon_projects = relationship("CarbonProject", back_populates="cooperative")

# Update CarbonProject to include CarbonTokens
from .sustainability import CarbonProject
CarbonProject.tokens = relationship("CarbonToken", back_populates="project")
