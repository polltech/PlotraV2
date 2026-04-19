"""
Plotra Platform - Base Model Classes
"""
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import Column, DateTime, Integer, Text, JSON
from sqlalchemy.orm import declared_attr
from app.core.database import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AuditMixin:
    """Mixin for audit trail functionality"""
    
    @declared_attr
    def audit_log(cls) -> Column:
        return Column(JSON, nullable=True, default=list)


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    
    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(Integer, default=0)  # 0 = active, 1 = deleted
    
    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
        self.is_deleted = 1


class UUIDMixin:
    """Mixin for UUID primary key"""
    
    id = Column(Integer, primary_key=True, autoincrement=True)


class BaseModel(Base, TimestampMixin, AuditMixin):
    """Base model combining all common mixins"""
    
    __abstract__ = True
    __allow_unmapped__ = True
    
    @declared_attr
    def audit_log(cls) -> Column:
        return Column(JSON, nullable=True, default=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
