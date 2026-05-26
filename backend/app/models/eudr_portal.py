"""
EUDR Portal Submission Models
Stores public exporter and importer form submissions from eudr-portal.html
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Text
from app.core.database import Base


class EUDRExporterSubmission(Base):
    __tablename__ = "eudr_exporter_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reference_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), default="submitted", nullable=False)

    # Key indexed fields for search/filter
    full_name = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    national_id = Column(String(100), nullable=True)
    country_of_residence = Column(String(100), nullable=True)
    company_name = Column(String(300), nullable=True, index=True)
    business_reg_number = Column(String(100), nullable=True)
    consignment_ref = Column(String(100), nullable=True, index=True)
    coffee_variety = Column(String(50), nullable=True)
    quantity_kg = Column(String(50), nullable=True)
    harvest_year = Column(String(10), nullable=True)
    origin_country = Column(String(100), nullable=True)
    destination_country = Column(String(100), nullable=True)

    # All 7 steps stored as JSON
    form_data = Column(JSON, nullable=True)

    # File references: [{name, type, size}]
    documents = Column(JSON, nullable=True, default=list)

    ip_address = Column(String(50), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EUDRImporterSubmission(Base):
    __tablename__ = "eudr_importer_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reference_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), default="submitted", nullable=False)

    # Key indexed fields
    full_name = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    eu_member_state = Column(String(100), nullable=True)
    company_name = Column(String(300), nullable=True, index=True)
    eori_number = Column(String(100), nullable=True, index=True)
    exporter_name = Column(String(300), nullable=True)
    consignment_ref = Column(String(100), nullable=True, index=True)
    risk_conclusion = Column(String(50), nullable=True)

    # All 7 steps stored as JSON
    form_data = Column(JSON, nullable=True)

    # File references
    documents = Column(JSON, nullable=True, default=list)

    ip_address = Column(String(50), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
