"""
Plotra Platform - Satellite Observation Models
Sentinel-2/Landsat ingestion, NDVI calculation, and biomass trends
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class SatelliteProvider(str, enum.Enum):
    """Satellite data providers"""
    SENTINEL_2 = "sentinel_2"
    LANDSAT_8 = "landsat_8"
    LANDSAT_9 = "landsat_9"
    SIMULATION = "simulation"


class CloudCoverLevel(str, enum.Enum):
    """Cloud cover quality levels"""
    CLEAR = "clear"           # 0-10%
    LOW = "low"              # 10-30%
    MEDIUM = "medium"        # 30-50%
    HIGH = "high"           # 50-70%
    CLOUDY = "cloudy"        # 70-100%


class AnalysisStatus(str, enum.Enum):
    """Satellite analysis status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SatelliteObservation(BaseModel):
    """
    Satellite observation for a parcel.
    Stores raw and processed satellite data.
    """
    
    __tablename__ = "satellite_observations"
    
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=True)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=True)
    
    # Acquisition details
    observation_id = Column(String(100), unique=True, nullable=False, index=True)
    satellite_source = Column(Enum(SatelliteProvider), nullable=False)
    acquisition_date = Column(DateTime, nullable=False)
    processing_date = Column(DateTime, default=datetime.utcnow)
    
    # Analysis status
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    # Tile information
    tile_id = Column(String(50), nullable=True)
    cloud_percentage = Column(Float, nullable=True)
    cloud_cover_level = Column(Enum(CloudCoverLevel), nullable=True)
    
    # NDVI values
    ndvi_mean = Column(Float, nullable=True)
    ndvi_min = Column(Float, nullable=True)
    ndvi_max = Column(Float, nullable=True)
    ndvi_std_dev = Column(Float, nullable=True)
    
    # Vegetation indices
    evi = Column(Float, nullable=True)  # Enhanced Vegetation Index
    savi = Column(Float, nullable=True)  # Soil Adjusted Vegetation Index
    ndwi = Column(Float, nullable=True)  # Normalized Difference Water Index
    lai = Column(Float, nullable=True)  # Leaf Area Index
    
    # Land cover classification
    land_cover_type = Column(String(50), nullable=True)
    land_cover_confidence = Column(Float, nullable=True)
    
    # Canopy metrics
    canopy_cover_percentage = Column(Float, nullable=True)
    tree_density = Column(Float, nullable=True)
    
    # Biomass estimation
    biomass_tons_hectare = Column(Float, nullable=True)
    biomass_confidence = Column(Float, nullable=True)
    
    # Relationships
    parcel = relationship("LandParcel", back_populates="satellite_observations")
    batch = relationship("Batch", back_populates="satellite_observations")
    biomass_trends = relationship("BiomassTrend", back_populates="observation")


class BiomassTrend(BaseModel):
    """
    Historical biomass trend analysis.
    Tracks changes over the 10-year lookback period.
    """
    
    __tablename__ = "biomass_trends"
    
    observation_id = Column(String(36), ForeignKey("satellite_observations.id"), nullable=False)
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    years_analyzed = Column(Integer, nullable=True)
    
    # Biomass metrics
    initial_biomass = Column(Float, nullable=True)
    final_biomass = Column(Float, nullable=True)
    biomass_change = Column(Float, nullable=True)
    biomass_change_percentage = Column(Float, nullable=True)
    
    # Trend analysis
    trend_direction = Column(String(20), nullable=True)  # "increasing", "stable", "decreasing"
    trend_confidence = Column(Float, nullable=True)
    annual_deforestation_rate = Column(Float, nullable=True)
    
    # Risk assessment
    deforestation_risk_score = Column(Float, nullable=True)
    is_deforestation_suspected = Column(Integer, default=0)  # 0=no, 1=yes
    alerts_triggered = Column(JSON, nullable=True)
    
    # Baseline comparison
    baseline_year = Column(Integer, default=2014)
    baseline_biomass = Column(Float, nullable=True)
    baseline_deviation = Column(Float, nullable=True)
    
    # Relationships
    observation = relationship("SatelliteObservation", back_populates="biomass_trends")


class SatelliteTask(BaseModel):
    """
    Background task for satellite data processing.
    Used by Celery for async processing.
    """
    
    __tablename__ = "satellite_tasks"
    
    # Task details
    task_type = Column(String(50), nullable=False)  # "ingestion", "analysis", "trend"
    entity_type = Column(String(50), nullable=False)  # "parcel", "farm", "batch"
    entity_id = Column(String(36), nullable=False)
    
    # Status
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    progress = Column(Float, default=0.0)
    
    # Result
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    # Scheduling
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Celery task ID
    celery_task_id = Column(String(100), nullable=True)
