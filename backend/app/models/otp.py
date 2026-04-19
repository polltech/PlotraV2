import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Boolean, DateTime, Integer
from app.core.database import Base


class OTPVerification(Base):
    __tablename__ = "otp_verifications"
    __allow_unmapped__ = True

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    @classmethod
    def generate(cls, phone: str) -> "OTPVerification":
        code = f"{random.randint(0, 999999):06d}"
        return cls(
            phone=phone,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )

    def is_valid(self, code: str) -> bool:
        return (
            not self.is_used
            and self.code == code
            and datetime.utcnow() < self.expires_at
            and self.attempts < 5
        )
