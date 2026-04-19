from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Notification(BaseModel):
    __tablename__ = "notifications"

    recipient_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="info")        # info / success / warning / error
    reference_id = Column(String(36), nullable=True) # farm_id or user_id related
    reference_type = Column(String(50), nullable=True) # "farm" / "user"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    recipient = relationship("User", foreign_keys=[recipient_id])
