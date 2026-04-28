"""
Plotra Platform - Polygon Capture Model (Offline-first Mobile App)
URS v0.1 compliant — matches Data Captured table fields exactly.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Enum, Text
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .base import BaseModel, UUIDMixin


class SyncStatus(str, enum.Enum):
    """Synchronization status for offline captures (URS: Pending/Synced/Failed)"""
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


class PolygonCapture(BaseModel, UUIDMixin):
    """
    Polygon boundary capture from mobile app — URS v0.1 compliant.
    Stores raw polygon data before sync to Plotra web.
    """
    __tablename__ = "polygon_capture"

    # Foreign keys
    farm_id = Column(Integer, ForeignKey("farm.id"), nullable=False)  # URS: farm_id (can be text code or numeric)
    captured_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Agent/user

    # URS required fields
    polygon_coordinates = Column(JSON, nullable=False)  # Array of {lat, lng} pairs (original order)
    area_ha = Column(Float, nullable=False)  # Calculated area in hectares
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # ISO 8601 timestamp
    device_id = Column(String(100), nullable=False)  # Unique device identifier
    accuracy_m = Column(Float, nullable=True)  # Mean GPS accuracy across all points (meters)

    # Additional fields (URS optional / extended)
    agent_id = Column(String(100), nullable=True)  # Optional agent identifier
    parcel_name = Column(String(100), nullable=True)  # Optional parcel name
    
    # Calculated geometry (for queries)
    boundary_geojson = Column(JSON, nullable=True)  # Full GeoJSON Polygon (converted form)
    boundary_geometry = Column(Geometry(geometry_type='POLYGON', srid=4326), nullable=True)  # PostGIS
    
    # Sync & audit
    sync_status = Column(Enum(SyncStatus), default=SyncStatus.PENDING)
    synced_at = Column(DateTime, nullable=True)
    external_id = Column(String(100), nullable=True)  # server record_id after sync
    sync_attempts = Column(Integer, default=0)
    last_sync_error = Column(Text, nullable=True)

    # Metadata
    notes = Column(Text, nullable=True)
    device_info = Column(JSON, nullable=True)  # {model, app_version, os}
    points_count = Column(Integer, nullable=False)

    # Validation
    topology_validated = Column(Boolean, default=False)
    validation_errors = Column(JSON, nullable=True)  # List of error strings

    # Relationships
    farm = relationship("Farm", back_populates="polygon_captures")
    captured_by = relationship("User", foreign_keys=[captured_by_id])

    def __repr__(self):
        return f"<PolygonCapture(farm={self.farm_id}, area={self.area_ha}ha, status={self.sync_status})>"
