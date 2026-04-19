"""
Plotra Platform - Traceability Models
Coffee tracking from farm through cooperative to export
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel, UUIDMixin


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


class WarehouseStatus(str, enum.Enum):
    """Warehouse status"""
    AVAILABLE = "available"
    FULL = "full"
    MAINTENANCE = "maintenance"


class Delivery(BaseModel, UUIDMixin):
    __tablename__ = "delivery"
    """
    Coffee delivery from farmer to cooperative.
    Records weight, quality, and traceability information.
    """
    
    farm_id = Column(Integer, ForeignKey("farm.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=True)
    
    # Delivery identification
    delivery_number = Column(String(50), unique=True, nullable=False)
    weighing_slip_number = Column(String(50), nullable=True)
    
    # Weight information
    gross_weight_kg = Column(Float, nullable=False)
    tare_weight_kg = Column(Float, default=0.0)
    net_weight_kg = Column(Float, nullable=False)
    moisture_content = Column(Float, nullable=True)  # Percentage
    
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
    
    # Relationships
    farm = relationship("Farm", foreign_keys=[farm_id])
    batch = relationship("Batch", foreign_keys=[batch_id])
    received_by = relationship("User", foreign_keys=[received_by_id])


class Batch(BaseModel, UUIDMixin):
    __tablename__ = "batch"
    """
    Coffee batch aggregating deliveries from multiple farmers.
    Created by Cooperative Admins for traceability and export.
    """
    
    cooperative_id = Column(Integer, ForeignKey("cooperative.id"), nullable=False)
    
    # Batch identification
    batch_number = Column(String(50), unique=True, nullable=False)
    lot_number = Column(String(50), nullable=True)
    
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
    warehouse_id = Column(Integer, ForeignKey("warehouse.id"), nullable=True)
    warehouse_location = Column(String(255), nullable=True)
    
    # EUDR traceability
    origin_farms = Column(JSON, nullable=True)  # List of farm IDs
    compliance_status = Column(String(50), default="Under Review")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cooperative = relationship("Cooperative", foreign_keys=[cooperative_id])
    deliveries = relationship("Delivery", back_populates="batch")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id], back_populates="batches")
    
    # QR Code for traceability
    qr_code_path = Column(String(500), nullable=True)


class Warehouse(BaseModel, UUIDMixin):
    __tablename__ = "warehouse"
    """
    Physical warehouse for storing coffee before export.
    """
    
    cooperative_id = Column(Integer, ForeignKey("cooperative.id"), nullable=False)
    
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
    status = Column(Enum(WarehouseStatus), default=WarehouseStatus.AVAILABLE)
    
    # Certifications
    organic_certified = Column(Boolean, default=False)
    fairtrade_certified = Column(Boolean, default=False)
    
    # Relationships
    batches = relationship("Batch", back_populates="warehouse")
    
    def get_utilization(self) -> float:
        if self.total_capacity_bags and self.current_capacity_bags is not None:
            return (self.current_capacity_bags / self.total_capacity_bags) * 100
        return 0.0
