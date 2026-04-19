"""
Plotra Platform - Verification Workflow Models
Four-tier state machine for compliance verification
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, UUIDMixin


class VerificationStatus(str, enum.Enum):
    """
    Four-tier verification states:
    1. Draft - Initial data entry
    2. Submitted - Farmer submits for verification
    3. CooperativeApproved - Cooperative officer verifies
    4. AdminApproved - Plotra admin approves
    5. EUDRSubmitted - Submitted to EUDR portal
    6. Certified - EUDR certified
    7. Rejected - Rejected at any stage
    """
    DRAFT = "draft"
    SUBMITTED = "submitted"
    COOPERATIVE_APPROVED = "cooperative_approved"
    ADMIN_APPROVED = "admin_approved"
    EUDR_SUBMITTED = "eudr_submitted"
    CERTIFIED = "certified"
    REJECTED = "rejected"


class VerificationType(str, enum.Enum):
    """Types of verification"""
    FARM_REGISTRATION = "farm_registration"
    PARCEL_MAPPING = "parcel_mapping"
    DELIVERY_RECORD = "delivery_record"
    BATCH_CREATION = "batch_creation"
    COMPLIANCE_CHECK = "compliance_check"
    EUDR_SUBMISSION = "eudr_submission"


class VerificationRecord(BaseModel, UUIDMixin):
    """
    Verification record for audit trail.
    Implements the four-tier verification workflow.
    """
    
    __tablename__ = "verification_records"
    
    # Entity being verified
    entity_type = Column(String(50), nullable=False)  # "farm", "parcel", "batch", "delivery"
    entity_id = Column(Integer, nullable=False)
    
    # Verification details
    verification_type = Column(Enum(VerificationType), nullable=False)
    current_status = Column(Enum(VerificationStatus), nullable=False, default=VerificationStatus.DRAFT)
    previous_status = Column(Enum(VerificationStatus), nullable=True)
    
    # Reviewer
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewer_role = Column(String(50), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Decision
    decision = Column(String(50), nullable=True)  # "approved", "rejected", "returned"
    decision_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Feedback
    feedback = Column(JSON, nullable=True)  # Structured feedback for improvement
    
    # Requirements checklist
    requirements_met = Column(JSON, nullable=True)  # Checklist results
    
    # Priority and due dates
    priority = Column(String(20), default="normal")
    due_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    
    # Relationships
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    history = relationship("VerificationHistory", back_populates="record", cascade="all, delete-orphan")
    
    def transition_to(
        self,
        new_status: VerificationStatus,
        reviewer_id: int,
        reviewer_role: str,
        notes: str = None
    ) -> bool:
        """
        Transition to a new status.
        
        Args:
            new_status: Target status
            reviewer_id: ID of user making the transition
            reviewer_role: Role of the reviewer
            notes: Optional notes for the transition
            
        Returns:
            True if transition was successful
        """
        valid_transitions = {
            VerificationStatus.DRAFT: [VerificationStatus.SUBMITTED],
            VerificationStatus.SUBMITTED: [VerificationStatus.COOPERATIVE_APPROVED, VerificationStatus.REJECTED],
            VerificationStatus.COOPERATIVE_APPROVED: [VerificationStatus.ADMIN_APPROVED, VerificationStatus.REJECTED],
            VerificationStatus.ADMIN_APPROVED: [VerificationStatus.EUDR_SUBMITTED, VerificationStatus.REJECTED],
            VerificationStatus.EUDR_SUBMITTED: [VerificationStatus.CERTIFIED, VerificationStatus.REJECTED],
            VerificationStatus.CERTIFIED: [VerificationStatus.REJECTED],
            VerificationStatus.REJECTED: [VerificationStatus.DRAFT],  # Allow resubmission
        }
        
        if new_status not in valid_transitions.get(self.current_status, []):
            return False
        
        # Create history entry
        history = VerificationHistory(
            record_id=self.id,
            from_status=self.current_status,
            to_status=new_status,
            changed_by_id=reviewer_id,
            changed_by_role=reviewer_role,
            notes=notes
        )
        self.history.append(history)
        
        # Update status
        self.previous_status = self.current_status
        self.current_status = new_status
        self.reviewer_id = reviewer_id
        self.reviewer_role = reviewer_role
        self.reviewed_at = datetime.utcnow()
        
        if new_status == VerificationStatus.CERTIFIED:
            self.completed_date = datetime.utcnow()
        
        return True


class VerificationHistory(BaseModel, UUIDMixin):
    """
    History of all status changes for a verification record.
    Provides complete audit trail.
    """
    
    __tablename__ = "verification_history"
    
    record_id = Column(Integer, ForeignKey("verification_records.id"), nullable=False)
    
    # Transition details
    from_status = Column(Enum(VerificationStatus), nullable=True)
    to_status = Column(Enum(VerificationStatus), nullable=False)
    
    # Who made the change
    changed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    changed_by_role = Column(String(50), nullable=True)
    
    # When
    changed_at = Column(DateTime, default=datetime.utcnow)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Auto-transition flag
    is_automatic = Column(Integer, default=0)  # 0=no, 1=yes
    
    # Relationships
    record = relationship("VerificationRecord", foreign_keys=[record_id])
    changed_by = relationship("User")


class VerificationRule(BaseModel, UUIDMixin):
    """
    Rules for automatic verification requirements.
    Can trigger alerts or auto-approve certain conditions.
    """
    
    __tablename__ = "verification_rules"
    
    # Rule identification
    rule_code = Column(String(100), unique=True, nullable=False)
    rule_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Scope
    entity_type = Column(String(50), nullable=False)  # "farm", "parcel", "batch"
    applies_to_status = Column(Enum(VerificationStatus), nullable=True)
    
    # Conditions (JSON logic)
    conditions = Column(JSON, nullable=False)  # Rule conditions
    actions = Column(JSON, nullable=False)  # Actions when triggered
    
    # Priority
    priority = Column(Integer, default=100)
    is_active = Column(Integer, default=1)  # 0=inactive, 1=active
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
