"""
Plotra Platform - EUDR Compliance Models
Due Diligence Statements, certificates, and Digital Product Passports
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ComplianceStatus(str, enum.Enum):
    """EUDR compliance status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    PENDING_DOCUMENTS = "pending_documents"
    REQUIRES_ACTION = "requires_action"


class EUDRCompliance(BaseModel):
    """
    EUDR compliance tracking for farms, batches, and cooperatives.
    Aggregates all compliance requirements for EUDR certification.
    """

    __tablename__ = "eudr_compliance"

    entity_type = Column(String(50), nullable=False)  # farm, batch, cooperative
    entity_id = Column(String(36), nullable=False)

    # Compliance status
    status = Column(Enum(ComplianceStatus), default=ComplianceStatus.UNDER_REVIEW)
    last_review_date = Column(DateTime, nullable=True)
    next_review_date = Column(DateTime, nullable=True)

    # Requirements checklist
    deforestation_free = Column(Integer, default=0)   # 0=no, 1=yes, 2=unknown
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
    certificate_id = Column(String(36), ForeignKey("certificates.id"), nullable=True)

    # Relationships
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    certificate = relationship("Certificate", back_populates="eudr_compliance_records")


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


class DueDiligenceStatement(BaseModel):
    """
    EUDR Due Diligence Statement (DDS) submission.
    Required for all commodity operators placing commodities on EU market.
    """
    
    __tablename__ = "eudr_submissions"
    
    # DDS identification
    dds_number = Column(String(100), unique=True, nullable=False, index=True)
    version = Column(String(20), default="1.0")
    
    # Linked entity
    entity_type = Column(String(50), nullable=False)  # "farm", "batch", "cooperative"
    entity_id = Column(String(36), nullable=False)
    
    # Operator information
    operator_name = Column(String(255), nullable=False)
    operator_id = Column(String(100), nullable=True)  # EUDR operator ID
    
    # Contact details
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_address = Column(Text, nullable=True)
    contact_phone = Column(String(50), nullable=True)
    
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
    risk_level = Column(String(50), default="low")  # low, medium, high
    mitigation_measures = Column(JSON, nullable=True)
    
    # Supporting evidence
    evidence_references = Column(JSON, nullable=True)
    satellite_analysis_ids = Column(JSON, nullable=True)
    
    # Geospatial evidence
    farm_coordinates = Column(JSON, nullable=True)
    polygon_references = Column(JSON, nullable=True)
    
    # Submission status
    submission_status = Column(Enum(SubmissionStatus), default=SubmissionStatus.DRAFT)
    submitted_date = Column(DateTime, nullable=True)
    portal_reference = Column(String(100), nullable=True)
    portal_response = Column(JSON, nullable=True)
    
    # Digital signatures
    dds_hash = Column(String(64), nullable=True)
    signature = Column(String(512), nullable=True)
    public_key_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    certificates = relationship("Certificate", back_populates="submission")


class Certificate(BaseModel):
    """
    EUDR compliance certificate.
    Digitally signed with HMAC for authenticity verification.
    """
    
    __tablename__ = "certificates"
    
    submission_id = Column(String(36), ForeignKey("eudr_submissions.id"), nullable=True)
    
    # Certificate identification
    certificate_number = Column(String(100), unique=True, nullable=False, index=True)
    certificate_type = Column(String(50), nullable=False)  # "EUDR_COMPLIANCE", "ORIGIN"
    
    # Entity being certified
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    
    # Validity
    issue_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    is_valid = Column(Integer, default=1)  # 1=active, 0=revoked
    
    # Scope
    scope_description = Column(Text, nullable=True)
    geographic_scope = Column(JSON, nullable=True)
    product_scope = Column(JSON, nullable=True)
    
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
    
    # Relationships
    submission = relationship("DueDiligenceStatement", back_populates="certificates")
    eudr_compliance_records = relationship("EUDRCompliance", back_populates="certificate")


class DigitalProductPassport(BaseModel):
    """
    EU Digital Product Passport for coffee.
    Tracks product through supply chain.
    """
    
    __tablename__ = "digital_product_passports"
    
    farm_id = Column(String(36), ForeignKey("farms.id"), nullable=False)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=True)
    
    # Passport identification
    passport_number = Column(String(100), unique=True, nullable=False, index=True)
    version = Column(String(20), default="1.0")
    
    # Product information
    product_name = Column(String(255), nullable=False)
    product_description = Column(Text, nullable=True)
    
    # Origin
    country_of_origin = Column(String(100), nullable=True)
    region_of_origin = Column(String(100), nullable=True)
    harvest_date = Column(DateTime, nullable=True)
    
    # Sustainability data
    certifications = Column(JSON, nullable=True)  # Organic, Fairtrade, Rainforest
    sustainability_score = Column(Float, nullable=True)
    
    # Supply chain
    supply_chain_nodes = Column(JSON, nullable=True)  # Farm -> Coop -> Exporter -> Importer
    chain_of_custody = Column(JSON, nullable=True)
    
    # Carbon footprint
    carbon_footprint_kg_co2 = Column(Float, nullable=True)
    carbon_offset = Column(Float, nullable=True)
    
    # Compliance
    eudr_compliant = Column(Integer, default=0)
    compliance_certificates = Column(JSON, nullable=True)
    
    # QR Code
    qr_code_data = Column(String(500), nullable=True)
    
    # Relationships
    farm = relationship("Farm", back_populates="digital_passport")


class EUDRWebhookLog(BaseModel):
    """
    Log of EUDR portal webhook responses.
    For error reconciliation and auditing.
    """
    
    __tablename__ = "eudr_webhook_logs"
    
    submission_id = Column(String(36), nullable=True)
    
    # Webhook details
    webhook_type = Column(String(50), nullable=False)  # "submission", "verification", "certificate"
    request_id = Column(String(100), nullable=True)
    
    # Payload
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    
    # Status
    status_code = Column(Integer, nullable=True)
    success = Column(Integer, default=0)  # 0=no, 1=yes
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
