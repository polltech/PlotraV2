"""
Plotra Platform - Farm and Land Models
PostGIS geometry, parent-child parcels, and land documents
"""
import enum
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, Enum, JSON, DateTime
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.models.base import BaseModel, GeoModel, SafeGeometry


class LandUseType(str, enum.Enum):
    """Classification of land use patterns"""
    AGROFORESTRY = "agroforestry"
    MONOCROP = "monocrop"
    MIXED_CROPPING = "mixed_cropping"
    FOREST_RESERVE = "forest_reserve"
    BUFFER_ZONE = "buffer_zone"
    OTHER = "other"


class OwnershipType(str, enum.Enum):
    """Land ownership types"""
    OWNED = "owned"
    LEASED = "leased"
    CUSTOMARY = "customary"
    TENANT = "tenant"
    COMMUNITY = "community"
    INHERITED = "inherited"


class DocumentType(str, enum.Enum):
    """Types of land documents"""
    TITLE_DEED = "title_deed"
    LEASE_AGREEMENT = "lease_agreement"
    CUSTOMARY_RIGHTS = "customary_rights"
    INHERITANCE_LETTER = "inheritance_letter"
    COMMUNITY_LAND_TITLE = "community_land_title"
    SURVEY_PLAN = "survey_plan"
    OTHER = "other"


class VerificationStatus(str, enum.Enum):
    """Verification status for parcels"""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    COOPERATIVE_APPROVED = "cooperative_approved"
    ADMIN_APPROVED = "admin_approved"
    EUDR_SUBMITTED = "eudr_submitted"
    CERTIFIED = "certified"
    REJECTED = "rejected"


class FarmStatus(str, enum.Enum):
    """Coffee farm operational status"""
    ACTIVE = "active"
    REHABILITATING = "rehabilitating"
    ABANDONED = "abandoned"


class PlantingMethod(str, enum.Enum):
    """Method of planting coffee"""
    MONOCULTURE = "monoculture"
    INTERCROPPED = "intercropped"
    AGROFORESTRY = "agroforestry"


class IrrigationType(str, enum.Enum):
    """Irrigation methods"""
    NONE = "none"
    DRIP = "drip"
    FURROW = "furrow"
    RAIN_FED = "rain_fed"
    SPRINKLER = "sprinkler"


class SoilType(str, enum.Enum):
    """Soil classification"""
    CLAY = "clay"
    LOAM = "loam"
    SANDY = "sandy"
    SILT = "silt"
    PEAT = "peat"
    UNKNOWN = "unknown"


class SlopeCategory(str, enum.Enum):
    """Terrain slope categories"""
    FLAT = "flat"  # <5%
    GENTLE = "gentle_slope"  # 5-15%
    MODERATE = "moderate_slope"  # 15-30%
    STEEP = "steep"  # >30%


class TreeSpecies(str, enum.Enum):
    """Enumerated tree species for standardization"""
    GREVILLEA = "grevillea"
    MACADAMIA = "macadamia"
    EUCALYPTUS = "eucalyptus"
    INDIGENOUS = "indigenous"
    AVOCADO = "avocado"
    MANGO = "mango"
    CITRUS = "citrus"
    OTHER = "other"


class CoffeeVariety(str, enum.Enum):
    """Coffee varieties for detailed differentiation"""
    SL28 = "SL28"
    SL34 = "SL34"
    BATIAN = "Batian"
    RUIRU_11 = "Ruiru 11"
    K7 = "K7"
    KAGERA = "Kagera"
    NYANZA = "Nyanza"
    BLUE_MOUNTAIN = "Blue Mountain"
    KONA = "Kona"
    ETHIOPIAN_YIRGACHEFFE = "Ethiopian Yirgacheffe"
    COLOMBIAN_SUPREMO = "Colombian Supremo"
    GUATEMALA_ANTIGUA = "Guatemala Antigua"
    OTHER = "other"


class CropCategory(str, enum.Enum):
    """Crop categories for organization"""
    COFFEE = "coffee"
    SHADE_TREE = "shade_tree"
    FRUIT_TREE = "fruit_tree"
    TIMBER = "timber"
    VEGETABLE = "vegetable"
    LEGUME = "legume"
    CEREAL = "cereal"
    OTHER = "other"


class GrowthStage(str, enum.Enum):
    """Growth stages for crops"""
    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    FRUITING = "fruiting"
    HARVESTING = "harvesting"
    DORMANT = "dormant"


class HealthStatus(str, enum.Enum):
    """Crop health status"""
    HEALTHY = "healthy"
    STRESSED = "stressed"
    DISEASED = "diseased"
    PEST_INFESTED = "pest_infested"
    WATER_STRESSED = "water_stressed"
    NUTRIENT_DEFICIENT = "nutrient_deficient"


class CertificationType(str, enum.Enum):
    """Quality and sustainability certifications"""
    FAIRTRADE = "fairtrade"
    RAINFOREST_ALLIANCE = "rainforest_alliance"
    ORGANIC = "organic"
    UTZ_CERTIFIED = "utz"
    GLOBALGAP = "globalgap"
    NONE = "none"


class CanopyCover(str, enum.Enum):
    """Tree canopy cover percentage"""
    NONE = "none"
    VERY_LOW = "very_low"  # <10%
    LOW = "low"  # 10-30%
    MODERATE = "moderate"  # 30-50%
    HIGH = "high"  # >50%


class MonitoringFrequency(str, enum.Enum):
    """Satellite monitoring frequency preference"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class Farm(BaseModel):
    """
    Farm model representing a farmer's agricultural holding.
    Can contain multiple land parcels with geospatial boundaries.
    """
    
    __tablename__ = "farms"
    
    # Owner
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cooperative_id = Column(String(36), ForeignKey("cooperatives.id"), nullable=True)
    
    # Identification
    farm_name = Column(String(255), nullable=True)
    farm_code = Column(String(50), unique=True, nullable=True, index=True)
    
    # Location
    centroid_lat = Column(Float, nullable=True)
    centroid_lon = Column(Float, nullable=True)
    
    # Measurements
    total_area_hectares = Column(Float, nullable=True)
    coffee_area_hectares = Column(Float, nullable=True)
    
    # Farming details
    coffee_varieties = Column(JSON, nullable=True)  # e.g., ["SL28", "SL34", "Ruiru11"]
    years_farming = Column(Integer, nullable=True)
    average_annual_production_kg = Column(Float, nullable=True)
    
    # Land use
    land_use_type = Column(Enum(LandUseType), default=LandUseType.AGROFORESTRY)
    
    # EUDR compliance
    deforestation_risk_score = Column(Float, default=0.0)  # 0-100
    last_satellite_analysis = Column(DateTime, nullable=True)
    compliance_status = Column(String(50), default="Under Review")
    
    # Verification workflow: draft → pending → coop_approved/rejected → verified/rejected
    verification_status = Column(String(50), default="draft")
    certified_date = Column(DateTime, nullable=True)
    certification_expiry = Column(DateTime, nullable=True)

    # Two-stage approval tracking
    coop_status = Column(String(50), nullable=True)          # pending_coop / coop_approved / coop_rejected
    coop_verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    coop_verified_at = Column(DateTime, nullable=True)
    coop_notes = Column(Text, nullable=True)                 # reason from cooperative
    admin_verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    admin_verified_at = Column(DateTime, nullable=True)
    admin_notes = Column(Text, nullable=True)                # reason from admin
    
    # Relationships
    owner = relationship("User", foreign_keys="Farm.owner_id")
    cooperative = relationship("Cooperative", back_populates="farms")
    parcels = relationship("LandParcel", back_populates="farm", cascade="all, delete-orphan")
    documents = relationship("LandDocument", back_populates="farm", cascade="all, delete-orphan")
    deliveries = relationship("Delivery", back_populates="farm")
    digital_passport = relationship("DigitalProductPassport", back_populates="farm", uselist=False)
    
    def get_parcel_count(self) -> int:
        return len([p for p in self.parcels if p.is_deleted == 0])
    
    def get_verified_parcels(self) -> list:
        return [p for p in self.parcels if p.verification_status == VerificationStatus.CERTIFIED]


class LandParcel(GeoModel):
    """
    Individual land parcel with GPS polygon boundary.
    Supports parent-child relationships for complex land structures.
    
    Parent-Child Model:
    - Parent parcel: Main registered land holding
    - Child parcel: Sub-division of parent (e.g., inherited portion)
    
    Validation:
    - Child must be entirely contained within parent
    - No overlapping parcels allowed
    """
    
    __tablename__ = "land_parcels"
    
    farm_id = Column(String(36), ForeignKey("farms.id"), nullable=False)
    
    # Parcel identification
    parcel_number = Column(String(50), nullable=False)
    parcel_name = Column(String(100), nullable=True)
    
    # Parent-child relationship
    parent_parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=True)
    is_parent = Column(Integer, default=0)  # 0=no, 1=yes
    
    # Child parcels
    child_parcels = relationship("LandParcel", back_populates="parent")
    
    # Geospatial data (PostGIS) - MANDATORY for EUDR compliance
    boundary_geojson = Column(JSON, nullable=False)  # GeoJSON polygon - REQUIRED
    boundary_geometry = Column(SafeGeometry(geometry_type='POLYGON', srid=4326), nullable=False)
    
    # Measurements (calculated or user-provided)
    area_hectares = Column(Float, nullable=True)
    perimeter_meters = Column(Float, nullable=True)
    
    # GPS metadata
    gps_accuracy_meters = Column(Float, nullable=True)
    gps_fix_type = Column(String(50), nullable=True)  # e.g., "RTK", "DGPS", "GPS"
    mapping_date = Column(DateTime, default=datetime.utcnow)
    mapping_device = Column(String(100), nullable=True)
    mapping_method = Column(String(50), nullable=True)  # "gps", "survey", "cadastral"
    
    # Terrain characteristics
    altitude_meters = Column(Float, nullable=True)
    slope_degrees = Column(Float, nullable=True)
    aspect = Column(String(20), nullable=True)  # North, South, East, West
    
    # Land use
    land_use_type = Column(Enum(LandUseType), default=LandUseType.AGROFORESTRY)
    ownership_type = Column(Enum(OwnershipType), default=OwnershipType.CUSTOMARY)
    land_registration_number = Column(String(100), nullable=True)
    soil_type = Column(Enum(SoilType), nullable=True)
    terrain_slope = Column(Enum(SlopeCategory), nullable=True)
    
    # Coffee farming details
    year_coffee_first_planted = Column(Integer, nullable=True)
    estimated_coffee_plants = Column(Integer, nullable=True)
    farm_status = Column(Enum(FarmStatus), default=FarmStatus.ACTIVE)
    planting_method = Column(Enum(PlantingMethod), nullable=True)
    irrigation_type = Column(Enum(IrrigationType), default=IrrigationType.RAIN_FED)
    
    # Mixed farming declaration (EUDR critical)
    practice_mixed_farming = Column(Integer, default=0)  # 0=no, 1=yes
    other_crops = Column(JSON, nullable=True)  # e.g., ["maize", "banana"]
    livestock_on_parcel = Column(Integer, default=0)  # 0=no, 1=yes
    livestock_type = Column(JSON, nullable=True)  # e.g., ["cattle", "goats"]
    coffee_percentage = Column(Integer, nullable=True)  # % of parcel under coffee
    crop_rotation_practiced = Column(Integer, default=0)  # 0=no, 1=yes
    
    # Tree cover & deforestation declaration (EUDR critical)
    trees_planted_last_5_years = Column(Integer, default=0)  # Triggers satellite cross-check
    tree_species_planted = Column(JSON, nullable=True)
    trees_planted_count = Column(Integer, nullable=True)
    reason_for_planting = Column(JSON, nullable=True)  # shade, windbreak, timber, soil_health
    trees_cleared_last_5_years = Column(Integer, default=0)  # HIGH RISK flag
    reason_for_clearing = Column(JSON, nullable=True)  # expanding_farmland, disease, construction
    canopy_cover = Column(Enum(CanopyCover), nullable=True)
    
    # Satellite verification consent
    consent_satellite_monitoring = Column(Integer, default=0)  # Required for EUDR
    consent_historical_imagery = Column(Integer, default=0)  # 2020-present alignment
    monitoring_frequency = Column(Enum(MonitoringFrequency), default=MonitoringFrequency.QUARTERLY)
    
    # EUDR Hard stop fields - Sustainability schema
    heritage_score = Column(Float, nullable=True)  # NDVI slope 2015-2020, critical for Phase 2
    agroforestry_start_year = Column(Integer, nullable=True)
    previous_land_use = Column(String(50), nullable=True)  # Forest, Pasture, Cropland, Other
    certification_status = Column(JSON, nullable=True)  # Array of certifications
    programme_support = Column(JSON, nullable=True)  # NGO programme support details
    
    # Entry state for compliance
    entry_state = Column(String(50), nullable=True)  # Monocrop, Transition, Heritage
    
    # Certifications
    certifications = Column(JSON, nullable=True)  # e.g., ["fairtrade", "organic"]
    certificate_expiry_date = Column(DateTime, nullable=True)
    previously_flagged = Column(Integer, default=0)  # Self-declaration
    cooperative_registration_number = Column(String(50), nullable=True)
    
    # Coffee specific
    coffee_area_hectares = Column(Float, nullable=True)
    shade_tree_count = Column(Integer, nullable=True)
    
    # Satellite analysis results
    ndvi_baseline = Column(Float, nullable=True)
    canopy_density = Column(Float, nullable=True)
    biomass_tons = Column(Float, nullable=True)
    
    # Verification workflow
    verification_status = Column(String(50), default="draft")

    # Relationships
    farm = relationship("Farm", back_populates="parcels")
    parent = relationship("LandParcel", remote_side="LandParcel.id", back_populates="child_parcels")
    satellite_observations = relationship("SatelliteObservation", back_populates="parcel")
    practices = relationship("PracticeLog", back_populates="parcel")
    photos = relationship("ParcelPhoto", back_populates="parcel")
    trees = relationship("Tree", back_populates="parcel", cascade="all, delete-orphan")
    crops = relationship("ParcelCrop", back_populates="parcel", cascade="all, delete-orphan")
    
    def validate_parent_child_relationship(self) -> Dict:
        """
        Validate parent-child parcel relationship.
        
        Returns:
            Dictionary with validation result
        """
        if not self.parent_parcel_id:
            return {"valid": True, "message": "No parent relationship"}
        
        if not self.boundary_geometry:
            return {"valid": False, "errors": ["No boundary geometry for validation"]}
        
        from shapely import wkb
        from shapely.ops import within
        
        try:
            child_geom = wkb.loads(bytes(self.boundary_geometry.data))
            parent_geom = wkb.loads(bytes(self.parent.boundary_geometry.data))
            
            # Check containment
            if not within(child_geom, parent_geom):
                return {
                    "valid": False,
                    "errors": ["Child parcel is not contained within parent"]
                }
            
            return {"valid": True, "message": "Parent-child relationship valid"}
            
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}


# Alias for compatibility with older code
FarmParcel = LandParcel


class GeoPolygon(BaseModel):
    """
    Individual polygon vertices for GPS recording.
    Supports offline GPS recording with later upload.
    """
    
    __tablename__ = "geo_polygons"
    
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=True)
    delivery_id = Column(String(36), ForeignKey("deliveries.id"), nullable=True)
    
    # Vertex data
    vertex_order = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    
    # Metadata
    recorded_at = Column(DateTime, default=datetime.utcnow)
    device_id = Column(String(100), nullable=True)
    is_synced = Column(Integer, default=0)  # 0=no, 1=yes
    offline_created = Column(Integer, default=0)  # Created offline flag


class LandDocument(BaseModel):
    """
    Document vault for land ownership documents.
    Supports SHA-256 checksums for integrity verification.
    """
    
    __tablename__ = "land_documents"
    
    farm_id = Column(String(36), ForeignKey("farms.id"), nullable=False)
    
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
    checksum_verified = Column(Integer, default=0)  # 0=no, 1=yes, 2=failed
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


class Tree(BaseModel):
    """
    Individual tree mapping and monitoring.
    Supports agroforestry, shade trees, and biodiversity tracking.
    """

    __tablename__ = "trees"

    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False)

    # Tree identification
    tree_number = Column(String(50), nullable=False)  # Unique within parcel
    tree_type = Column(Enum(TreeSpecies), default=TreeSpecies.OTHER)
    tree_age_years = Column(Float, nullable=True)

    # Location (GPS coordinates)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_meters = Column(Float, nullable=True)
    accuracy_meters = Column(Float, nullable=True)

    # Physical characteristics
    height_meters = Column(Float, nullable=True)
    canopy_diameter_meters = Column(Float, nullable=True)
    trunk_diameter_cm = Column(Float, nullable=True)

    # Health and status
    health_status = Column(String(50), default="healthy")  # healthy, stressed, diseased, dead
    planted_date = Column(DateTime, nullable=True)
    last_health_check = Column(DateTime, nullable=True)

    # Economic value
    economic_value_usd = Column(Float, nullable=True)
    timber_value_usd = Column(Float, nullable=True)
    fruit_yield_kg_year = Column(Float, nullable=True)

    # Environmental benefits
    carbon_sequestered_kg_year = Column(Float, nullable=True)
    biodiversity_score = Column(Float, nullable=True)  # 0-10 scale

    # Metadata
    notes = Column(Text, nullable=True)
    is_native_species = Column(Integer, default=0)  # 0=no, 1=yes
    provides_shade = Column(Integer, default=0)  # 0=no, 1=yes
    is_fruit_bearing = Column(Integer, default=0)  # 0=no, 1=yes

    # Monitoring history
    monitoring_history = Column(JSON, nullable=True)  # Array of health checks over time

    # Relationships
    parcel = relationship("LandParcel", back_populates="trees")

    def get_age_years(self) -> Optional[float]:
        """Calculate tree age in years."""
        if self.planted_date:
            return (datetime.utcnow() - self.planted_date).days / 365.25
        return self.tree_age_years


class TreeSpecies(str, enum.Enum):
    """Enumerated tree species for standardization"""
    GREVILLEA = "grevillea"
    MACADAMIA = "macadamia"
    EUCALYPTUS = "eucalyptus"
    INDIGENOUS = "indigenous"
    AVOCADO = "avocado"
    MANGO = "mango"
    CITRUS = "citrus"
    OTHER = "other"


class CoffeeVariety(str, enum.Enum):
    """Coffee varieties for detailed differentiation"""
    SL28 = "SL28"
    SL34 = "SL34"
    BATIAN = "Batian"
    RUIRU_11 = "Ruiru 11"
    K7 = "K7"
    KAGERA = "Kagera"
    NYANZA = "Nyanza"
    BLUE_MOUNTAIN = "Blue Mountain"
    KONA = "Kona"
    ETHIOPIAN_YIRGACHEFFE = "Ethiopian Yirgacheffe"
    COLOMBIAN_SUPREMO = "Colombian Supremo"
    GUATEMALA_ANTIGUA = "Guatemala Antigua"
    OTHER = "other"


class CropCategory(str, enum.Enum):
    """Crop categories for organization"""
    COFFEE = "coffee"
    SHADE_TREE = "shade_tree"
    FRUIT_TREE = "fruit_tree"
    TIMBER = "timber"
    VEGETABLE = "vegetable"
    LEGUME = "legume"
    CEREAL = "cereal"
    OTHER = "other"


class GrowthStage(str, enum.Enum):
    """Growth stages for crops"""
    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    FRUITING = "fruiting"
    HARVESTING = "harvesting"
    DORMANT = "dormant"


class HealthStatus(str, enum.Enum):
    """Crop health status"""
    HEALTHY = "healthy"
    STRESSED = "stressed"
    DISEASED = "diseased"
    PEST_INFESTED = "pest_infested"
    WATER_STRESSED = "water_stressed"
    NUTRIENT_DEFICIENT = "nutrient_deficient"


class CropCategory(str, enum.Enum):
    """Crop categories for organization"""
    COFFEE = "coffee"
    SHADE_TREE = "shade_tree"
    FRUIT_TREE = "fruit_tree"
    TIMBER = "timber"
    VEGETABLE = "vegetable"
    LEGUME = "legume"
    CEREAL = "cereal"
    OTHER = "other"


class CropType(BaseModel):
    """
    Comprehensive crop type definitions with spectral signatures and growth characteristics.
    Supports detailed differentiation between coffee varieties and other crops.
    """

    __tablename__ = "crop_types"

    name = Column(String(100), unique=True, nullable=False)
    scientific_name = Column(String(150), nullable=True)
    category = Column(Enum(CropCategory), nullable=False, default=CropCategory.OTHER)

    # Coffee-specific fields
    coffee_variety = Column(Enum(CoffeeVariety), nullable=True)
    is_coffee = Column(Integer, default=0)  # 1 if this is a coffee variety

    # Growth characteristics
    ndvi_range_min = Column(Float, nullable=True)  # Typical NDVI range for identification
    ndvi_range_max = Column(Float, nullable=True)
    canopy_height_min_m = Column(Float, nullable=True)
    canopy_height_max_m = Column(Float, nullable=True)
    growth_cycle_days = Column(Integer, nullable=True)
    is_perennial = Column(Integer, default=0)  # 0=annual, 1=perennial

    # Environmental preferences
    optimal_temperature_min_c = Column(Float, nullable=True)
    optimal_temperature_max_c = Column(Float, nullable=True)
    rainfall_requirement_mm_year = Column(Float, nullable=True)
    soil_ph_min = Column(Float, nullable=True)
    soil_ph_max = Column(Float, nullable=True)

    # Economic data
    market_price_usd_kg = Column(Float, nullable=True)
    yield_potential_kg_ha = Column(Float, nullable=True)
    establishment_cost_usd_ha = Column(Float, nullable=True)

    # Spectral signatures for crop identification
    spectral_signature = Column(JSON, nullable=True)  # NDVI, EVI, SAVI patterns over growth cycle

    # Color coding for visualization
    display_color = Column(String(7), nullable=True)  # Hex color code (e.g., "#8B4513")

    # Additional metadata
    description = Column(Text, nullable=True)
    origin_country = Column(String(100), nullable=True)
    climate_zone = Column(String(50), nullable=True)  # tropical, subtropical, etc.


class GrowthStage(str, enum.Enum):
    """Growth stages for crops"""
    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    FRUITING = "fruiting"
    HARVESTING = "harvesting"
    DORMANT = "dormant"


class HealthStatus(str, enum.Enum):
    """Crop health status"""
    HEALTHY = "healthy"
    STRESSED = "stressed"
    DISEASED = "diseased"
    PEST_INFESTED = "pest_infested"
    WATER_STRESSED = "water_stressed"
    NUTRIENT_DEFICIENT = "nutrient_deficient"


class ParcelCrop(BaseModel):
    """
    Detailed crop areas within parcels for comprehensive differentiation.
    Supports mixed cropping systems, agroforestry, and detailed crop management.
    """

    __tablename__ = "parcel_crops"

    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False)
    crop_type_id = Column(String(36), ForeignKey("crop_types.id"), nullable=False)

    # Area and location
    area_hectares = Column(Float, nullable=True)
    boundary_geojson = Column(JSON, nullable=True)  # Polygon for crop area
    centroid_lat = Column(Float, nullable=True)
    centroid_lon = Column(Float, nullable=True)

    # Planting details
    planted_date = Column(DateTime, nullable=True)
    expected_harvest_date = Column(DateTime, nullable=True)
    planting_density_per_ha = Column(Float, nullable=True)  # plants/hectare
    row_spacing_m = Column(Float, nullable=True)
    plant_spacing_m = Column(Float, nullable=True)

    # Current status
    growth_stage = Column(Enum(GrowthStage), nullable=True, default=GrowthStage.VEGETATIVE)
    health_status = Column(Enum(HealthStatus), nullable=True, default=HealthStatus.HEALTHY)
    maturity_percentage = Column(Float, nullable=True)  # 0-100% maturity

    # Yield expectations and tracking
    expected_yield_kg_ha = Column(Float, nullable=True)
    actual_yield_kg_ha = Column(Float, nullable=True)
    harvest_date = Column(DateTime, nullable=True)
    harvest_quality_grade = Column(String(20), nullable=True)  # AA, AB, C, etc.

    # Management practices
    irrigation_method = Column(String(50), nullable=True)  # drip, sprinkler, flood
    fertilizer_type = Column(String(100), nullable=True)
    fertilizer_amount_kg_ha = Column(Float, nullable=True)
    pesticide_used = Column(String(100), nullable=True)
    last_fertilizer_date = Column(DateTime, nullable=True)
    last_pesticide_date = Column(DateTime, nullable=True)

    # Environmental monitoring
    soil_moisture_percentage = Column(Float, nullable=True)
    soil_ph = Column(Float, nullable=True)
    last_soil_test_date = Column(DateTime, nullable=True)

    # Economic tracking
    establishment_cost_usd = Column(Float, nullable=True)
    maintenance_cost_usd_year = Column(Float, nullable=True)
    revenue_usd_year = Column(Float, nullable=True)

    # Quality and certification
    organic_certified = Column(Integer, default=0)
    fair_trade_certified = Column(Integer, default=0)
    rain_forest_alliance_certified = Column(Integer, default=0)

    # Notes and observations
    notes = Column(Text, nullable=True)
    issues_observed = Column(JSON, nullable=True)  # Array of issues with dates
    treatment_history = Column(JSON, nullable=True)  # Array of treatments applied

    # Satellite analysis integration
    last_satellite_analysis = Column(DateTime, nullable=True)
    ndvi_baseline = Column(Float, nullable=True)
    health_score = Column(Float, nullable=True)  # 0-10 scale

    # Relationships
    parcel = relationship("LandParcel", back_populates="crops")
    crop_type = relationship("CropType")


class HistoricalAnalysis(BaseModel):
    """
    Historical farm and satellite analysis data storage.
    Allows users to view analysis from years back.
    """

    __tablename__ = "historical_analyses"

    entity_type = Column(String(50), nullable=False)  # "farm", "parcel", "batch"
    entity_id = Column(String(36), nullable=False)

    # Analysis period
    analysis_date = Column(DateTime, nullable=False)
    analysis_year = Column(Integer, nullable=False)
    analysis_period = Column(String(20), nullable=True)  # "annual", "quarterly", "monthly"

    # Satellite data
    satellite_source = Column(String(50), nullable=True)
    acquisition_date = Column(DateTime, nullable=True)
    cloud_cover_percentage = Column(Float, nullable=True)

    # Vegetation indices
    ndvi_mean = Column(Float, nullable=True)
    ndvi_min = Column(Float, nullable=True)
    ndvi_max = Column(Float, nullable=True)
    evi_mean = Column(Float, nullable=True)
    savi_mean = Column(Float, nullable=True)
    lai_mean = Column(Float, nullable=True)

    # Land cover analysis
    canopy_cover_percentage = Column(Float, nullable=True)
    tree_cover_percentage = Column(Float, nullable=True)
    crop_cover_percentage = Column(Float, nullable=True)
    bare_soil_percentage = Column(Float, nullable=True)

    # Biomass and carbon
    biomass_tons_hectare = Column(Float, nullable=True)
    carbon_stored_tons = Column(Float, nullable=True)
    carbon_sequestered_kg_year = Column(Float, nullable=True)

    # Risk assessment
    deforestation_detected = Column(Integer, default=0)
    deforestation_area_ha = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True)
    risk_score = Column(Float, nullable=True)

    # Tree and crop specific data
    tree_count = Column(Integer, nullable=True)
    tree_health_score = Column(Float, nullable=True)  # 0-10 scale
    crop_health_score = Column(Float, nullable=True)  # 0-10 scale

    # Weather and environmental data
    rainfall_mm = Column(Float, nullable=True)
    temperature_celsius = Column(Float, nullable=True)
    soil_moisture_percentage = Column(Float, nullable=True)

    # Raw analysis data
    analysis_metadata = Column(JSON, nullable=True)
    satellite_imagery_url = Column(String(500), nullable=True)

    # Processing info
    processing_version = Column(String(20), default="1.0")
    processing_date = Column(DateTime, default=datetime.utcnow)

    def get_seasonal_trend(self) -> str:
        """Determine seasonal trend based on NDVI and time."""
        if not self.ndvi_mean:
            return "unknown"

        # Simple seasonal classification (would be more sophisticated in production)
        month = self.analysis_date.month if self.analysis_date else 1

        if month in [3, 4, 5]:  # Long rains season
            return "long_rains" if self.ndvi_mean > 0.6 else "dry_season"
        elif month in [10, 11, 12]:  # Short rains season
            return "short_rains" if self.ndvi_mean > 0.5 else "dry_season"
        else:
            return "dry_season" if self.ndvi_mean < 0.4 else "growing_season"


class ParcelPhoto(BaseModel):
    """
    Photos of parcels for verification.
    GPS-tagged with hash chain integrity.
    """

    __tablename__ = "parcel_photos"

    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False)

    # Photo details
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    checksum_sha256 = Column(String(64), nullable=True)

    # GPS data
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)

    # Metadata
    captured_at = Column(DateTime, default=datetime.utcnow)
    captured_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    description = Column(Text, nullable=True)

    # Verification
    is_verified = Column(Integer, default=0)

    # Relationships
    parcel = relationship("LandParcel", back_populates="photos")
