"""
Plotra Platform - Farm and Land Models
Includes GeoJSON/PostGIS polygon support for GPS farm boundary mapping
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Enum, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .base import BaseModel, UUIDMixin
from .safe_geometry import SafeGeometry


class LandUseType(str, enum.Enum):
    """Classification of land use patterns"""
    AGROFORESTRY = "agroforestry"
    MONOCROP = "monocrop"
    MIXED_CROPPING = "mixed_cropping"
    FOREST_RESERVE = "forest_reserve"
    BUFFER_ZONE = "buffer_zone"


class OwnershipType(str, enum.Enum):
    """Land ownership types"""
    OWNED = "owned"
    LEASED = "leased"
    CUSTOMARY = "customary"
    TENANT = "tenant"
    COMMUNITY = "community"


class DocumentType(str, enum.Enum):
    """Types of land documents"""
    TITLE_DEED = "title_deed"
    LEASE_AGREEMENT = "lease_agreement"
    CUSTOMARY_RIGHTS = "customary_rights"
    INHERITANCE_LETTER = "inheritance_letter"
    COMMUNITY_LAND_TITLE = "community_land_title"
    OTHER = "other"


class Farm(BaseModel, UUIDMixin):
    __tablename__ = "farm"
    """
    Farm model representing a farmer's agricultural holding.
    Can contain multiple farm parcels with geospatial boundaries.
    """
    
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Farm identification
    farm_name = Column(String(255), nullable=True)
    total_area_hectares = Column(Float, nullable=True)
    
    # Location
    centroid_lat = Column(Float, nullable=True)
    centroid_lon = Column(Float, nullable=True)
    
    # Farming details
    coffee_varieties = Column(JSON, nullable=True)  # e.g., ["SL28", "SL34", "Ruiru11"]
    years_farming = Column(Integer, nullable=True)
    average_annual_production_kg = Column(Float, nullable=True)
    
    # Land use
    land_use_type = Column(Enum(LandUseType), default=LandUseType.AGROFORESTRY)
    
    # Land & Parcel
    farm_type = Column(String(20), nullable=True)  # owned/leased/communal/other
    land_registration_number = Column(String(100), nullable=True)
    soil_type = Column(String(30), nullable=True)  # clay/loam/sandy/volcanic
    terrain = Column(String(30), nullable=True)  # flat/gentle_slope/steep

    # Coffee farming details
    year_coffee_planted = Column(Integer, nullable=True)
    coffee_tree_count = Column(Integer, nullable=True)
    farm_status = Column(String(30), nullable=True)  # active/rehabilitating/abandoned
    planting_method = Column(String(30), nullable=True)  # monoculture/intercropped/agroforestry
    irrigation_used = Column(Boolean, nullable=True)
    irrigation_type = Column(String(50), nullable=True)

    # Mixed farming declaration (EUDR critical)
    mixed_farming = Column(Boolean, nullable=True)
    coffee_percent = Column(Float, nullable=True)  # % of parcel under coffee
    other_crops = Column(JSON, nullable=True)  # list of crops
    livestock = Column(Boolean, nullable=True)
    livestock_type = Column(JSON, nullable=True)  # list of livestock types
    crop_rotation = Column(Boolean, nullable=True)

    # Tree cover & deforestation (EUDR critical)
    trees_planted_last5 = Column(Boolean, nullable=True)
    tree_species = Column(JSON, nullable=True)
    tree_count = Column(Integer, nullable=True)
    tree_planting_reason = Column(JSON, nullable=True)
    trees_cleared = Column(Boolean, nullable=True)  # HIGH RISK - triggers satellite review
    reason_for_clearing = Column(Text, nullable=True)
    current_canopy_cover = Column(String(20), nullable=True)  # 0-10/10-30/30-50/50+

    # Satellite verification consent (EUDR critical)
    satellite_consent = Column(Boolean, nullable=True)
    historical_imagery_consent = Column(Boolean, nullable=True)
    monitoring_frequency = Column(String(20), nullable=True)  # monthly/quarterly/biannual/annual

    # Certifications & compliance history
    certifications = Column(JSON, nullable=True)  # list: fairtrade/organic/rainforest_alliance/utz
    cert_expiry_date = Column(DateTime, nullable=True)
    previous_violations = Column(Boolean, nullable=True)
    violation_details = Column(Text, nullable=True)

    # EUDR risk tracking
    eudr_risk_flags = Column(JSON, nullable=True)  # list of risk flag strings
    profile_submitted = Column(Boolean, default=False)
    profile_submitted_at = Column(DateTime, nullable=True)

    # EUDR compliance
    deforestation_risk_score = Column(Float, default=0.0)  # 0-100
    last_satellite_analysis = Column(DateTime, nullable=True)
    compliance_status = Column(String(50), default="Under Review")
    
    # Relationships - simplified
    parcels = relationship("LandParcel", cascade="all, delete-orphan", back_populates="farm")
    documents = relationship("LandDocument", cascade="all, delete-orphan", back_populates="farm")
    deliveries = relationship("Delivery")
    
    # Digital Product Passport
    digital_passport = relationship("DigitalProductPassport", uselist=False, back_populates="farm")
    
    def get_parcel_count(self) -> int:
        return len(self.parcels)
    
    def get_total_area(self) -> float:
        if self.parcels:
            return sum(p.area_hectares for p in self.parcels if p.area_hectares)
        return self.total_area_hectares or 0.0


class LandParcel(BaseModel, UUIDMixin):
    __tablename__ = "land_parcel"
    """
    Individual farm parcel with GPS polygon boundary.
    Supports GeoJSON format for mobile GPS mapping.
    
    Russian Doll Model:
    - Parent parcel: Main registered land holding (Master Deed/Family Plot)
    - Child parcel: Sub-division of parent (e.g., inherited portion)
    - Resolves fractional tenure issues
    """
    
    farm_id = Column(Integer, ForeignKey("farm.id"), nullable=False)
    
    # Parcel identification
    parcel_number = Column(Integer, nullable=False)
    parcel_name = Column(String(100), nullable=True)
    
    # Parent-child relationship (Russian Doll Model)
    parent_parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=True)
    is_parent = Column(Boolean, default=False)  # True if this is a parent parcel
    
    # Geospatial data (PostGIS)
    boundary_geojson = Column(JSON, nullable=True)  # GeoJSON polygon
    boundary_geometry = Column(SafeGeometry(geometry_type='POLYGON', srid=4326), nullable=True)
    
    # Measurements
    area_hectares = Column(Float, nullable=True)
    perimeter_meters = Column(Float, nullable=True)
    
    # GPS metadata
    gps_accuracy_meters = Column(Float, nullable=True)
    gps_fix_type = Column(String(50), nullable=True)  # e.g., "RTK", "DGPS", "GPS"
    mapping_date = Column(DateTime, default=datetime.utcnow)
    mapping_device = Column(String(100), nullable=True)  # e.g., "Garmin GPSMAP 66i"
    
    # Terrain characteristics
    altitude_meters = Column(Float, nullable=True)
    slope_degrees = Column(Float, nullable=True)
    aspect = Column(String(20), nullable=True)  # North, South, East, West
    
    # Land use
    land_use_type = Column(Enum(LandUseType), default=LandUseType.AGROFORESTRY)
    
    # Coffee specific
    coffee_area_hectares = Column(Float, nullable=True)
    shade_tree_count = Column(Integer, nullable=True)
    
    # Analysis results
    ndvi_baseline = Column(Float, nullable=True)
    canopy_density = Column(Float, nullable=True)  # 0-100%
    
    # Entry state (Layer 3: Baseline status)
    entry_state = Column(String(50), default="monocrop")  # "monocrop", "transition", "heritage"
    
    # Relationships
    farm = relationship("Farm", back_populates="parcels")
    
    # Sustainability practices
    practice_logs = relationship("PracticeLog", back_populates="parcel")
    transition_events = relationship("TransitionEvent", back_populates="parcel")
    biomass_ledger = relationship("BiomassLedger", back_populates="parcel")
    carbon_tokens = relationship("CarbonToken", back_populates="parcel")
    
    # Satellite analysis
    satellite_analyses = relationship("SatelliteAnalysis", back_populates="parcel")
    ndvi_records = relationship("NDVIRecord", back_populates="parcel")


# Alias for compatibility
FarmParcel = LandParcel


class LandDocument(BaseModel, UUIDMixin):
    __tablename__ = "land_document"
    """
    Document vault for land ownership documents.
    Supports SHA-256 checksums for integrity verification.
    """
    
    farm_id = Column(Integer, ForeignKey("farm.id"), nullable=False)
    
    # Document details
    document_type = Column(Enum(DocumentType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # File information
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # Integrity verification
    checksum_sha256 = Column(String(64), nullable=True)
    checksum_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime, nullable=True)
    
    # Ownership
    ownership_type = Column(Enum(OwnershipType), default=OwnershipType.CUSTOMARY)
    document_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    
    # Metadata
    issuing_authority = Column(String(255), nullable=True)
    reference_number = Column(String(100), nullable=True)
    
    # Verification status
    verification_status = Column(String(50), default="pending")
    verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_date = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Relationships
    farm = relationship("Farm", back_populates="documents")
    verified_by = relationship("User", foreign_keys=[verified_by_id])
