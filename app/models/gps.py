"""
Plotra Platform - GPS Capture Model
Stores GPS point captures from mobile app for farm boundary verification and analysis.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Enum, Text, Index
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .base import BaseModel, UUIDMixin


class CaptureTypeEnum(str, enum.Enum):
    """Type of GPS capture"""
    BOUNDARY_POINT = "boundary_point"  # Part of farm boundary
    SAMPLE_POINT = "sample_point"  # Random verification point
    CORNER_POINT = "corner_point"  # Corner of parcel
    ENTRY_POINT = "entry_point"  # Main entry/gate
    MISCELLANEOUS = "misc"


class CaptureMethodEnum(str, enum.Enum):
    """How the GPS point was captured"""
    MANUAL = "manual"  # User tapped on map
    GPS_DEVICE = "gps_device"  # External GPS receiver
    PHONE_GPS = "phone_gps"  # Smartphone GPS
    RTK = "rtk"  # Real-time kinematic (high precision)
    DGPS = "dgps"  # Differential GPS


class GpsCapture(BaseModel, UUIDMixin):
    """
    GPS point capture for farm verification and analysis.
    Supports both boundary collection and spot checks.
    """
    __tablename__ = "gps_capture"
    __table_args__ = (
        Index('idx_gps_capture_farm', 'farm_id'),
        Index('idx_gps_capture_parcel', 'parcel_id'),
        Index('idx_gps_capture_coordinates', 'latitude', 'longitude'),
    )

    # Foreign keys
    farm_id = Column(Integer, ForeignKey("farm.id"), nullable=False)
    parcel_id = Column(Integer, ForeignKey("land_parcel.id"), nullable=True)
    captured_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Who captured (if authenticated)

    # GPS coordinates
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)  # Meters above sea level
    accuracy_meters = Column(Float, nullable=True)  # GPS accuracy in meters

    # GPS metadata
    capture_type = Column(Enum(CaptureTypeEnum), default=CaptureTypeEnum.BOUNDARY_POINT)
    capture_method = Column(Enum(CaptureMethodEnum), default=CaptureMethodEnum.PHONE_GPS)
    gps_fix_type = Column(String(20), nullable=True)  # "3D", "2D", "None"
    satellites_used = Column(Integer, nullable=True)  # Number of satellites in fix

    # Device information
    device_id = Column(String(100), nullable=True)  # Unique device identifier
    device_model = Column(String(100), nullable=True)  # e.g., "iPhone 14 Pro"
    app_version = Column(String(20), nullable=True)  # App version that captured

    # Timestamps
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When sent to server

    # Additional data
    notes = Column(Text, nullable=True)  # Field notes
    photo_url = Column(String(500), nullable=True)  # Photo of location (if taken)

    # Analysis flags
    is_outside_parcel = Column(Boolean, default=False)  # True if point falls outside known parcel
    analysis_completed = Column(Boolean, default=False)
    analysis_timestamp = Column(DateTime, nullable=True)

    # Relationships
    farm = relationship("Farm", back_populates="gps_captures")
    parcel = relationship("LandParcel", back_populates="gps_captures")
    captured_by = relationship("User", foreign_keys=[captured_by_id])

    def __repr__(self):
        return f"<GpsCapture(farm={self.farm_id}, lat={self.latitude}, lon={self.longitude})>"


# Add relationship to existing models (these will be picked up by Base.metadata)
# The relationship is defined here in the child model, but we also add back_populates
# in the parent models for completeness.
# In farm.py, Farm will have:
#   gps_captures = relationship("GpsCapture", back_populates="farm", cascade="all, delete-orphan")
# In land_parcel (farm.py), LandParcel will have:
#   gps_captures = relationship("GpsCapture", back_populates="parcel", cascade="all, delete-orphan")
