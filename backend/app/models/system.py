"""
Plotra Platform - System Configuration Models
Stores system-wide configuration including required documents, session settings, and env credentials
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, JSON
from app.models.base import BaseModel


class SystemConfig(BaseModel):
    """
    Global system configuration model.
    Stores settings like required documents for cooperatives, session timeouts, and environment credentials.
    """
    
    __tablename__ = "system_config"
    
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(JSON, nullable=True)
    description = Column(String(500), nullable=True)
    is_public = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    @staticmethod
    def get_key(session_timeout_minutes):
        return f"session_timeout_{session_timeout_minutes}"
    
    @staticmethod
    def get_key_for_required_documents():
        return "required_documents"
    
    @staticmethod
    def get_key_for_env_credentials():
        return "env_credentials"


class RequiredDocument(BaseModel):
    """
    Required documents for cooperative registration.
    Admin can add/remove documents that cooperatives must to submit.
    """
    
    __tablename__ = "required_documents"
    
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    document_type = Column(String(100), nullable=True)
    is_required = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "document_type": self.document_type,
            "is_required": self.is_required,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class SyncLog(BaseModel):
    """
    Sync log for delta-sync analytics.
    Tracks sync success rate for KPI measurement.
    """
    
    __tablename__ = "sync_logs"
    
    device_id = Column(String(100), nullable=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    records_sent = Column(Integer, default=0)
    synced_count = Column(Integer, default=0)
    conflict_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    sync_timestamp = Column(String(50), nullable=True)
    checksum = Column(String(64), nullable=True)
    

class ConflictRecord(BaseModel):
    """
    Conflict record for polygon overlap resolution.
    Tracks 48h SLA compliance.
    """
    
    __tablename__ = "conflict_records"
    
    conflict_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    cooperative_id = Column(String(36), nullable=True, index=True)
    local_version = Column(JSON, nullable=True)
    server_version = Column(JSON, nullable=True)
    severity = Column(String(20), default="medium")
    status = Column(String(50), default="pending_resolution", index=True)
    resolved_by = Column(String(36), nullable=True)
    resolved_at = Column(String(50), nullable=True)
    resolution_data = Column(JSON, nullable=True)
    sla_alert_sent = Column(Boolean, default=False)