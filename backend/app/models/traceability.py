"""
Plotra Platform - Traceability Models
Coffee tracking from farm through cooperative to export
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class QualityGrade(str, enum.Enum):
    """Coffee quality grades based on screen size and defects"""
    AA = "AA"      # 17-18 mesh, premium
    AB = "AB"      # 15-16 mesh, standard
    PB = "PB"      # Peaberry, single bean
    C = "C"        # Lower grade
    AAAA = "AAAA"  # Super premium
    UNGRADED = "ungraded"


class DeliveryStatus(str, enum.Enum):
    """Status of coffee delivery"""
    PENDING = "pending"
    RECEIVED = "received"
    WEIGHED = "weighed"
    QUALITY_CHECKED = "quality_checked"
    PROCESSED = "processed"
    REJECTED = "rejected"


class ProcessingMethod(str, enum.Enum):
    """Coffee processing methods"""
    WASHED = "washed"
    NATURAL = "natural"
    HONEY = "honey"
    PULPED_NATURAL = "pulped_natural"


class BatchStatus(str, enum.Enum):
    """Batch status"""
    DRAFT = "draft"
    FINALIZED = "finalized"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


class Delivery(BaseModel):
    """
    Coffee delivery from farmer to cooperative.
    Links to specific parcel via GPS correlation.
    """
    
    __tablename__ = "deliveries"
    
    farm_id = Column(String(36), ForeignKey("farms.id"), nullable=False)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=True)
    
    # Delivery identification
    delivery_number = Column(String(50), unique=True, nullable=False, index=True)
    weighing_slip_number = Column(String(50), nullable=True, index=True)
    
    # Weight information
    gross_weight_kg = Column(Float, nullable=False)
    tare_weight_kg = Column(Float, default=0.0)
    net_weight_kg = Column(Float, nullable=False)
    moisture_content = Column(Float, nullable=True)
    
    # Quality assessment
    quality_grade = Column(Enum(QualityGrade), nullable=True)
    processing_method = Column(Enum(ProcessingMethod), nullable=True)
    defect_count = Column(Integer, default=0)
    quality_notes = Column(Text, nullable=True)
    
    # Status
    status = Column(Enum(DeliveryStatus), default=DeliveryStatus.PENDING)
    reception_date = Column(DateTime, default=datetime.utcnow)
    
    # Staff
    received_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Cherry specifics
    cherry_type = Column(String(50), nullable=True)  # Red, Yellow, Mixed
    picking_date = Column(DateTime, nullable=True)
    
    # Parcel correlation
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=True)
    gps_correlation = Column(JSON, nullable=True)  # Spatial correlation data
    
    # GPS coordinates of delivery point
    delivery_lat = Column(Float, nullable=True)
    delivery_lon = Column(Float, nullable=True)
    
    # Relationships
    farm = relationship("Farm", back_populates="deliveries")
    batch = relationship("Batch", back_populates="deliveries")
    received_by = relationship("User", foreign_keys=[received_by_id])
    parcel = relationship("LandParcel")


class Batch(BaseModel):
    """
    Coffee batch aggregating deliveries from multiple farmers.
    Created by Cooperative Officers for traceability and export.
    """
    
    __tablename__ = "batches"
    
    cooperative_id = Column(String(36), ForeignKey("cooperatives.id"), nullable=False)
    
    # Batch identification
    batch_number = Column(String(50), unique=True, nullable=False, index=True)
    lot_number = Column(String(50), nullable=True, index=True)
    
    # Production details
    crop_year = Column(Integer, nullable=True)
    harvest_start_date = Column(DateTime, nullable=True)
    harvest_end_date = Column(DateTime, nullable=True)
    
    # Processing
    processing_method = Column(Enum(ProcessingMethod), default=ProcessingMethod.WASHED)
    
    # Quality summary
    quality_grade = Column(Enum(QualityGrade), nullable=True)
    average_moisture = Column(Float, nullable=True)
    total_weight_kg = Column(Float, nullable=True)
    bag_count = Column(Integer, nullable=True)
    
    # Storage
    warehouse_id = Column(String(36), ForeignKey("warehouses.id"), nullable=True)
    warehouse_location = Column(String(255), nullable=True)
    
    # EUDR traceability
    origin_farms = Column(JSON, nullable=True)  # List of farm IDs
    compliance_status = Column(String(50), default="Under Review")
    
    # Status
    status = Column(Enum(BatchStatus), default=BatchStatus.DRAFT)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cooperative = relationship("Cooperative", back_populates="batches")
    deliveries = relationship("Delivery", back_populates="batch")
    warehouse = relationship("Warehouse", back_populates="batches")
    satellite_observations = relationship("SatelliteObservation", back_populates="batch")
    
    # QR Code for traceability
    qr_code_path = Column(String(500), nullable=True)
    traceability_hash = Column(String(64), nullable=True)


class PracticeLog(BaseModel):
    """
    Agricultural practice log for sustainability tracking.
    Links to specific parcel for spatial correlation.
    Used for satellite screening layer (Tier 3) false positive suppression.
    """
    
    __tablename__ = "practice_logs"
    
    parcel_id = Column(String(36), ForeignKey("land_parcels.id"), nullable=False)
    
    # Practice details - maps to spec event_type
    event_type = Column(String(50), nullable=False)  # "Pruning", "Harvesting", "Planting", "Intercropping"
    event_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)  # For planting "what was planted"
    
    # Photo evidence - required for re-survey tasks
    photo_evidence_url = Column(String(500), nullable=True)
    
    # Inputs
    inputs_used = Column(JSON, nullable=True)  # Fertilizers, pesticides, etc.
    quantity = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    
    # Method
    method = Column(String(100), nullable=True)
    labor_hours = Column(Float, nullable=True)
    
    # Compliance
    is_organic = Column(Integer, default=0)  # 0=no, 1=yes
    is_fairtrade = Column(Integer, default=0)
    
    # Relationships
    parcel = relationship("LandParcel", back_populates="practices")


class Warehouse(BaseModel):
    """
    Physical warehouse for storing coffee before export.
    """
    
    __tablename__ = "warehouses"
    
    cooperative_id = Column(String(36), ForeignKey("cooperatives.id"), nullable=False)
    
    # Warehouse details
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=True)
    address = Column(Text, nullable=True)
    
    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Capacity
    total_capacity_bags = Column(Integer, nullable=True)
    current_capacity_bags = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Certifications
    organic_certified = Column(Boolean, default=False)
    fairtrade_certified = Column(Boolean, default=False)
    
    # Relationships
    cooperative = relationship("Cooperative", back_populates="warehouses")
    batches = relationship("Batch", back_populates="warehouse")
    
    def get_utilization(self) -> float:
        if self.total_capacity_bags and self.current_capacity_bags is not None:
            return (self.current_capacity_bags / self.total_capacity_bags) * 100
        return 0.0
