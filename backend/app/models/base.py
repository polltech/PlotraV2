"""
Plotra Platform - Base Model Classes
Provides UUID primary keys, timestamps, audit logging, and soft delete
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Column, DateTime, String, Text, Integer, JSON, CheckConstraint
from geoalchemy2 import Geometry
from app.core.database import Base
from app.core.config import settings

def SafeGeometry(geometry_type='GEOMETRY', srid=4326):
    """
    Return a Geometry column if using PostgreSQL, 
    otherwise return a JSON column for SQLite compatibility.
    """
    if settings.database.async_url.startswith("postgresql"):
        return Geometry(geometry_type=geometry_type, srid=srid)
    return JSON

class UUIDMixin:
    """Mixin for UUID primary key"""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(Integer, default=0)  # 0 = active, 1 = deleted
    
    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
        self.is_deleted = 1
    
    def restore(self):
        self.deleted_at = None
        self.is_deleted = 0


class AuditMixin:
    """
    Mixin for immutable audit trail.
    Records every change to the model with tamper-evident hash chain.
    """
    
    audit_log = Column(JSON, nullable=True, default=list)
    
    def add_audit_entry(
        self,
        action: str,
        user_id: str,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None
    ):
        """
        Add an immutable audit entry.
        
        Args:
            action: Action type (CREATE, UPDATE, DELETE, VIEW)
            user_id: ID of user performing action
            changes: Dictionary of changed fields
            ip_address: Client IP address
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "changes": changes,
            "ip_address": ip_address,
            "hash": ""  # Will be computed for integrity
        }
        
        # Compute hash for tamper evidence
        import hashlib
        previous_hash = ""
        if self.audit_log:
            if isinstance(self.audit_log, list) and len(self.audit_log) > 0:
                previous_hash = self.audit_log[-1].get("hash", "")
        
        entry["previous_hash"] = previous_hash
        entry_content = f"{entry['timestamp']}{action}{user_id}{previous_hash}"
        entry["hash"] = hashlib.sha256(entry_content.encode()).hexdigest()
        
        if not self.audit_log:
            self.audit_log = []
        self.audit_log.append(entry)
    
    def verify_audit_chain(self) -> Dict[str, Any]:
        """
        Verify the integrity of the audit chain.
        
        Returns:
            Dictionary with verification result
        """
        if not self.audit_log or len(self.audit_log) == 0:
            return {"valid": True, "message": "No audit entries"}
        
        import hashlib
        
        for i, entry in enumerate(self.audit_log):
            # Verify hash
            entry_content = f"{entry['timestamp']}{entry['action']}{entry['user_id']}{entry.get('previous_hash', '')}"
            expected_hash = hashlib.sha256(entry_content.encode()).hexdigest()
            
            if entry.get("hash") != expected_hash:
                return {
                    "valid": False,
                    "message": f"Audit chain broken at entry {i}",
                    "entry": entry
                }
        
        return {"valid": True, "message": "Audit chain is valid"}


class BaseModel(Base, UUIDMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """
    Base model combining all common mixins.
    All models inherit from this class.
    """
    
    __abstract__ = True
    __allow_unmapped__ = True
    __tablename__: str
    
    # Common constraints
    __table_args__ = (
        CheckConstraint("length(id) = 36", name="uuid_format"),
    )
    
    # Record status
    status = Column(String(50), default="active")
    notes = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value
        return result
    
    def to_geojson(self) -> Dict[str, Any]:
        """Convert geometry to GeoJSON"""
        return {}


class GeoModel(BaseModel):
    """
    Base model for geospatial entities.
    Includes PostGIS geometry support.
    """
    
    __abstract__ = True
    
    # Geometry columns
    centroid = Column(SafeGeometry(geometry_type='POINT', srid=4326), nullable=True)
    boundary = Column(SafeGeometry(geometry_type='POLYGON', srid=4326), nullable=True)
    
    # Calculated fields
    area_hectares = Column(Integer, nullable=True)
    perimeter_meters = Column(Integer, nullable=True)
    
    # Validation
    validation_status = Column(String(50), default="pending")
    validation_errors = Column(JSON, nullable=True)
    
    def calculate_area(self) -> float:
        """
        Calculate area from geometry.
        Should be implemented in subclasses.
        """
        pass
    
    def calculate_perimeter(self) -> float:
        """
        Calculate perimeter from geometry.
        Should be implemented in subclasses.
        """
        pass
    
    def validate_geometry(self) -> Dict[str, Any]:
        """
        Validate geometry integrity.
        
        Returns:
            Dictionary with validation result
        """
        if not self.boundary:
            return {"valid": False, "errors": ["No boundary geometry defined"]}
        
        # Check if polygon is valid
        from shapely import wkb
        from shapely.validation import make_valid
        
        try:
            geom = wkb.loads(bytes(self.boundary.data))
            
            if not geom.is_valid:
                # Attempt to fix
                geom = make_valid(geom)
            
            if not geom.is_valid:
                return {"valid": False, "errors": ["Invalid polygon geometry"]}
            
            # Check minimum area
            area_hectares = geom.area / 10000  # Convert sq meters to hectares
            if area_hectares < 0.1:
                return {"valid": False, "errors": ["Polygon area below minimum threshold"]}
            
            return {
                "valid": True,
                "area_hectares": round(area_hectares, 4),
                "perimeter_meters": round(geom.length, 2)
            }
            
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}
