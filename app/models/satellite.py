"""
Plotra Platform - Satellite Analysis Models
NDVI calculation, deforestation risk assessment, and historical baselines
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, UUIDMixin


class RiskLevel(str, enum.Enum):
    """Deforestation risk classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalysisStatus(str, enum.Enum):
    """Satellite analysis status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LandCoverType(str, enum.Enum):
    """Satellite-detected land cover types"""
    FOREST = "forest"
    AGROFORESTRY = "agroforestry"
    AGRICULTURE = "agriculture"
    SETTLEMENT = "settlement"
    WATER = "water"
    BARE_GROUND = "bare_ground"
    COFFEE = "coffee"
    OTHER = "other"


class SatelliteAnalysis(BaseModel, UUIDMixin):
    __tablename__ = "satellite_analysis"
    """
    Satellite analysis results for farm parcels.
    Includes NDVI, deforestation risk, and land cover classification.
    """
    
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=False)
    
    # Analysis identification
    analysis_id = Column(String(100), unique=True, nullable=False)
    satellite_source = Column(String(50), nullable=True)  # Sentinel-2, Landsat-8
    
    # Timestamps
    acquisition_date = Column(DateTime, nullable=False)
    processing_date = Column(DateTime, default=datetime.utcnow)
    
    # Analysis status
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    # NDVI data
    ndvi_mean = Column(Float, nullable=True)
    ndvi_min = Column(Float, nullable=True)
    ndvi_max = Column(Float, nullable=True)
    ndvi_standard_deviation = Column(Float, nullable=True)
    
    # Vegetation indices
    evi = Column(Float, nullable=True)  # Enhanced Vegetation Index
    savi = Column(Float, nullable=True)  # Soil Adjusted Vegetation Index
    ndwi = Column(Float, nullable=True)  # Normalized Difference Water Index
    
    # Land cover classification
    land_cover_type = Column(Enum(LandCoverType), nullable=True)
    land_cover_confidence = Column(Float, nullable=True)  # 0-100%
    
    # Canopy metrics
    canopy_cover_percentage = Column(Float, nullable=True)
    tree_density = Column(Float, nullable=True)  # trees per hectare
    
    # Deforestation risk assessment
    risk_level = Column(Enum(RiskLevel), nullable=True)
    risk_score = Column(Float, default=0.0)  # 0-100 scale
    deforestation_detected = Column(Integer, default=0)  # 0=no, 1=yes
    deforestation_area_hectares = Column(Float, nullable=True)
    
    # Historical comparison
    baseline_year = Column(Integer, default=2020)
    baseline_ndvi = Column(Float, nullable=True)
    ndvi_change_percentage = Column(Float, nullable=True)
    
    # Heritage Analysis (Layer 2: Heritage Lookback)
    heritage_slope = Column(Float, nullable=True)  # 10-year biomass trend (2015-2020)
    heritage_verified = Column(Integer, default=0)  # 0=no, 1=yes
    heritage_start_date = Column(DateTime, nullable=True)  # Start of heritage period
    
    # Confidence score (Layer 2: Cloud cover/terrain adjustment)
    confidence_score = Column(Float, nullable=True)  # 0-100 confidence in analysis
    
    # Change detection
    change_detected = Column(Integer, default=0)
    change_type = Column(String(50), nullable=True)  # deforestation, reforestation, etc.
    change_date_estimate = Column(DateTime, nullable=True)
    
    # Raw data references
    imagery_tile_id = Column(String(100), nullable=True)
    cloud_percentage = Column(Float, nullable=True)
    
    # Relationships
    parcel = relationship("LandParcel", back_populates="satellite_analyses")


class NDVIRecord(BaseModel, UUIDMixin):
    __tablename__ = "ndvi_record"
    """
    Individual NDVI readings for a parcel over time.
    Used for historical baseline and trend analysis.
    """
    
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=False)
    analysis_id = Column(Integer, ForeignKey("satellite_analysis.id"), nullable=True)
    
    # Temporal data
    observation_date = Column(DateTime, nullable=False)
    satellite_source = Column(String(50), nullable=True)
    
    # NDVI values
    ndvi_value = Column(Float, nullable=False)
    pixel_count = Column(Integer, nullable=True)
    
    # Environmental conditions
    cloud_cover = Column(Float, nullable=True)
    precipitation = Column(Float, nullable=True)  # mm
    temperature = Column(Float, nullable=True)  # Celsius
    
    # Quality
    quality_flag = Column(Integer, default=0)
    quality_description = Column(String(255), nullable=True)
    
    # Relationships
    parcel = relationship("LandParcel", back_populates="ndvi_records")


class DeforestationRisk(BaseModel, UUIDMixin):
    __tablename__ = "deforestation_risk"
    """
    Comprehensive deforestation risk assessment for farms.
    Aggregates multiple risk factors into a final score.
    """
    
    farm_id = Column(Integer, ForeignKey("farm.id"), nullable=False)
    
    # Assessment
    assessment_date = Column(DateTime, default=datetime.utcnow)
    assessor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Risk scores (0-100)
    overall_risk_score = Column(Float, default=0.0)
    land_use_risk = Column(Float, default=0.0)
    historical_risk = Column(Float, default=0.0)
    proximity_risk = Column(Float, default=0.0)  # Proximity to protected areas
    climate_risk = Column(Float, default=0.0)
    
    # Risk level
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW)
    
    # Factors
    risk_factors = Column(JSON, nullable=True)  # Detailed breakdown
    recommendations = Column(JSON, nullable=True)
    
    # Compliance impact
    eudr_compliant = Column(Integer, default=0)  # 0=no, 1=yes
    compliance_notes = Column(Text, nullable=True)
    
    # Expiration
    valid_until = Column(DateTime, nullable=True)
    
    # Relationships
    farm = relationship("Farm")
