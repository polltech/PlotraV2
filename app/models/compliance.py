"""
Plotra Platform - EUDR Compliance Models
Due Diligence Statements, certificates, and compliance tracking
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel, UUIDMixin


class ComplianceStatus(str, enum.Enum):
    """EUDR compliance status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    PENDING_DOCUMENTS = "pending_documents"
    REQUIRES_ACTION = "requires_action"


class CertificateStatus(str, enum.Enum):
    """Certificate lifecycle status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class SubmissionStatus(str, enum.Enum):
    """EUDR portal submission status"""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNDER_REVIEW = "under_review"


class EUDRCompliance(BaseModel, UUIDMixin):
    __tablename__ = "eudr_compliance"
    """
    EUDR compliance tracking for farms and batches.
    Aggregates all compliance requirements for EUDR certification.
    """
    
    entity_type = Column(String(50), nullable=False)  # farm, batch, cooperative
    entity_id = Column(Integer, nullable=False)
    
    # Compliance status
    status = Column(Enum(ComplianceStatus), default=ComplianceStatus.UNDER_REVIEW)
    last_review_date = Column(DateTime, nullable=True)
    next_review_date = Column(DateTime, nullable=True)
    
    # Requirements checklist
    deforestation_free = Column(Integer, default=0)  # 0=no, 1=yes, 2=unknown
    legal_ownership = Column(Integer, default=0)
    traceability_verified = Column(Integer, default=0)
    documents_complete = Column(Integer, default=0)
    satellite_analysis_complete = Column(Integer, default=0)
    
    # Risk assessment
    risk_score = Column(Float, default=0.0)
    risk_factors = Column(JSON, nullable=True)
    
    # Review information
    reviewed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Compliance certificate reference
    certificate_id = Column(Integer, ForeignKey("certificate.id"), nullable=True)
    
    # Relationships
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    certificate = relationship("Certificate", back_populates="compliance_records")


class Certificate(BaseModel, UUIDMixin):
    __tablename__ = "certificate"
    """
    EUDR compliance certificate.
    Digitally signed with HMAC for authenticity verification.
    """
    
    # Certificate identification
    certificate_number = Column(String(100), unique=True, nullable=False)
    certificate_type = Column(String(50), nullable=False)  # e.g., "EUDR_COMPLIANCE"
    
    # Entity being certified
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    
    # Validity
    issue_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    is_valid = Column(Integer, default=1)  # 1=active, 0=revoked
    
    # Scope
    scope_description = Column(Text, nullable=True)
    geographic_scope = Column(JSON, nullable=True)  # Coordinates or regions
    product_scope = Column(JSON, nullable=True)  # e.g., ["Coffee Cherries", "Green Coffee"]
    
    # Verification details
    verification_standard = Column(String(100), nullable=True)
    verification_body = Column(String(255), nullable=True)
    standard_reference = Column(String(255), nullable=True)
    
    # Digital signatures
    hmac_signature = Column(String(512), nullable=True)
    signing_algorithm = Column(String(50), default="HMAC-SHA256")
    public_key_id = Column(String(100), nullable=True)
    
    # Status
    status = Column(Enum(CertificateStatus), default=CertificateStatus.ACTIVE)
    revocation_reason = Column(Text, nullable=True)
    revocation_date = Column(DateTime, nullable=True)
    
    # Relationships - back reference to EUDRCompliance
    # Note: This is a reverse relationship from Certificate to EUDRCompliance
    # The foreign key is defined on the EUDRCompliance side (certificate_id)
    compliance_records = relationship("EUDRCompliance", back_populates="certificate")


class DueDiligenceStatement(BaseModel, UUIDMixin):
    __tablename__ = "due_diligence_statement"
    """
    EUDR Due Diligence Statement (DDS) generation and tracking.
    Required for all commodity operators placing commodities on the EU market.
    """
    
    # DDS identification
    dds_number = Column(String(100), unique=True, nullable=False)
    version = Column(String(20), default="1.0")
    
    # Entity information
    operator_name = Column(String(255), nullable=False)
    operator_id = Column(String(100), nullable=True)  # EUDR operator ID
    
    # Contact details
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_address = Column(Text, nullable=True)
    
    # Commodity details
    commodity_type = Column(String(100), default="Coffee")
    hs_code = Column(String(20), nullable=True)  # Harmonized System code
    country_of_origin = Column(String(100), nullable=True)
    quantity = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)  # kg, tonnes, bags
    
    # Supplier information
    supplier_name = Column(String(255), nullable=True)
    supplier_country = Column(String(100), nullable=True)
    supplier_id = Column(String(100), nullable=True)
    
    # Country of first placement
    first_placement_country = Column(String(100), nullable=True)
    first_placement_date = Column(DateTime, nullable=True)
    
    # Risk assessment
    risk_assessment = Column(JSON, nullable=True)
    risk_level = Column(String(50), default="low")
    mitigation_measures = Column(JSON, nullable=True)
    
    # Supporting evidence
    evidence_references = Column(JSON, nullable=True)
    satellite_analysis_ids = Column(JSON, nullable=True)
    
    # Submission status
    submission_status = Column(Enum(SubmissionStatus), default=SubmissionStatus.DRAFT)
    submitted_date = Column(DateTime, nullable=True)
    portal_response = Column(JSON, nullable=True)
    
    # Digital signature
    dds_hash = Column(String(64), nullable=True)
    signature = Column(String(512), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    farms = Column(JSON, nullable=True)  # Associated farm IDs
