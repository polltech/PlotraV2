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