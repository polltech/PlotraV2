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


class WeatherObservation(BaseModel):
    """
    Quarterly weather aggregates for a parcel, sourced from Open-Meteo Historical API.
    Stored alongside satellite observations to enable drought vs deforestation discrimination.
    """

    __tablename__ = "weather_observations"

    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False, index=True)

    # Quarter dates (matches satellite quarter windows)
    period_from = Column(String(10), nullable=False)   # "2021-03-01"
    period_to   = Column(String(10), nullable=False)   # "2021-05-31"

    # Aggregated weather for the quarter
    rainfall_mm       = Column(Float, nullable=True)   # total precipitation (mm)
    et0_mm            = Column(Float, nullable=True)   # total reference evapotranspiration (mm)
    water_deficit_mm  = Column(Float, nullable=True)   # rainfall - ET0 (negative = drought stress)
    temp_max_avg_c    = Column(Float, nullable=True)   # average daily max temperature (°C)

    # Drought flag: 1 if quarter exhibits drought-level water stress
    drought_flag = Column(Integer, default=0)

    data_source = Column(String(50), default="open-meteo")

    parcel = relationship("LandParcel")


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


class EudrFarmingAnalysis(BaseModel):
    """
    EUDR Farming History Analysis result for a parcel.
    Stores detected farming start date, land clearing event, Hansen forest
    loss data, and multi-index monthly chart data.
    One row per parcel — re-running the analysis overwrites the existing row.
    """

    __tablename__ = "eudr_farming_analyses"

    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False, index=True, unique=True)
    farm_id   = Column(String(36), ForeignKey("farms.id"),        nullable=False, index=True)

    # Farming start detection
    farming_start_month      = Column(String(7),  nullable=True)   # "2019-03"
    farming_start_confidence = Column(String(10), nullable=True)   # HIGH / MEDIUM / LOW

    # Land clearing event
    land_clearing_month      = Column(String(7),  nullable=True)
    clearing_confidence      = Column(String(10), nullable=True)

    # Deforestation / forest evidence
    forest_present_before_clearing = Column(Integer, default=0)    # 0/1 bool
    pre_2020_farming_confirmed     = Column(Integer, default=0)

    # Hansen GFC data
    hansen_treecover2000 = Column(Float,   nullable=True)  # % tree cover in 2000
    hansen_loss_year     = Column(Integer, nullable=True)  # year of forest loss (2001-2023)
    hansen_was_forested  = Column(Integer, nullable=True)  # 0/1 bool
    hansen_tile          = Column(String(20), nullable=True)

    # EUDR verdict
    eudr_status  = Column(String(30), nullable=True)  # COMPLIANT / RISK / INVESTIGATE / INSUFFICIENT_DATA
    eudr_summary = Column(String(500), nullable=True)
    eudr_risk_flags = Column(JSON, nullable=True)

    # Data quality
    timeseries_months = Column(Integer, nullable=True)
    cloud_gap_months  = Column(Integer, nullable=True)

    # Full monthly chart data (stored as JSON for frontend chart)
    chart_data = Column(JSON, nullable=True)

    analysed_at = Column(DateTime, nullable=True)

    parcel = relationship("LandParcel")
