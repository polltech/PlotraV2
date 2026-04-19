"""
Plotra Platform - EUDR Integration Layer
Due Diligence Statement generation, certificate creation, and compliance reporting
"""
import hashlib
import hmac
import json
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from app.core.config import settings
from app.models.compliance import (
    EUDRCompliance, Certificate, DueDiligenceStatement,
    ComplianceStatus, CertificateStatus, SubmissionStatus
)


@dataclass
class DDSData:
    """Data structure for Due Diligence Statement generation"""
    operator_name: str
    operator_id: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_address: str = ""
    commodity_type: str = "Coffee"
    hs_code: str = "090111"  # Coffee, not roasted, not decaffeinated
    country_of_origin: str = "Kenya"
    quantity: float = 0.0
    unit: str = "kg"
    supplier_name: str = ""
    supplier_country: str = ""
    supplier_id: str = ""
    first_placement_country: str = ""
    first_placement_date: Optional[datetime] = None
    risk_assessment: Dict = field(default_factory=dict)
    risk_level: str = "low"
    mitigation_measures: List[str] = field(default_factory=list)
    evidence_references: List[str] = field(default_factory=list)


@dataclass
class CertificateData:
    """Data structure for certificate generation"""
    certificate_type: str
    entity_type: str
    entity_id: int
    entity_name: str
    scope_description: str = ""
    geographic_scope: Dict = field(default_factory=dict)
    product_scope: List[str] = field(default_factory=list)
    verification_standard: str = "EUDR"
    verification_body: str = "Plotra Platform"
    validity_days: int = 365


class EUDRIntegrationService:
    """
    EUDR compliance integration service.
    Generates Due Diligence Statements and compliance certificates.
    """
    
    def __init__(self, secret_key: str = None):
        """
        Initialize the EUDR integration service.
        
        Args:
            secret_key: Secret key for HMAC signatures (defaults to app config)
        """
        self.secret_key = secret_key or settings.app.secret_key
        self.certificate_validity_days = settings.eudr.certificate_validity_days
    
    def generate_due_diligence_statement(
        self,
        dds_data: DDSData,
        farms: List[Dict] = None
    ) -> DueDiligenceStatement:
        """
        Generate an EUDR-compliant Due Diligence Statement.
        
        Args:
            dds_data: DDS data structure
            farms: List of associated farm data
            
        Returns:
            DueDiligenceStatement record
        """
        # Generate unique DDS number
        dds_number = f"DDS-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Build DDS payload
        dds_payload = {
            "dds_number": dds_number,
            "version": settings.eudr.dds_version,
            "operator": {
                "name": dds_data.operator_name,
                "id": dds_data.operator_id,
                "contact": {
                    "name": dds_data.contact_name,
                    "email": dds_data.contact_email,
                    "address": dds_data.contact_address
                }
            },
            "commodity": {
                "type": dds_data.commodity_type,
                "hs_code": dds_data.hs_code,
                "country_of_origin": dds_data.country_of_origin,
                "quantity": dds_data.quantity,
                "unit": dds_data.unit
            },
            "supplier": {
                "name": dds_data.supplier_name,
                "country": dds_data.supplier_country,
                "id": dds_data.supplier_id
            },
            "first_placement": {
                "country": dds_data.first_placement_country,
                "date": dds_data.first_placement_date.isoformat() if dds_data.first_placement_date else None
            },
            "risk_assessment": dds_data.risk_assessment,
            "risk_level": dds_data.risk_level,
            "mitigation_measures": dds_data.mitigation_measures,
            "evidence": dds_data.evidence_references
        }
        
        # Create hash and signature
        dds_hash = self._generate_hash(json.dumps(dds_payload, sort_keys=True))
        signature = self._generate_signature(dds_hash)
        
        # Create record
        dds = DueDiligenceStatement(
            dds_number=dds_number,
            version=settings.eudr.dds_version,
            operator_name=dds_data.operator_name,
            operator_id=dds_data.operator_id,
            contact_name=dds_data.contact_name,
            contact_email=dds_data.contact_email,
            contact_address=dds_data.contact_address,
            commodity_type=dds_data.commodity_type,
            hs_code=dds_data.hs_code,
            country_of_origin=dds_data.country_of_origin,
            quantity=dds_data.quantity,
            unit=dds_data.unit,
            supplier_name=dds_data.supplier_name,
            supplier_country=dds_data.supplier_country,
            supplier_id=dds_data.supplier_id,
            first_placement_country=dds_data.first_placement_country,
            risk_assessment=dds_data.risk_assessment,
            risk_level=dds_data.risk_level,
            mitigation_measures=dds_data.mitigation_measures,
            evidence_references=dds_data.evidence_references,
            submission_status=SubmissionStatus.DRAFT,
            dds_hash=dds_hash,
            signature=signature,
            farms=farms
        )
        
        return dds
    
    def generate_certificate(
        self,
        cert_data: CertificateData,
        compliance_id: int = None
    ) -> Certificate:
        """
        Generate an EUDR compliance certificate with HMAC signature.
        
        Args:
            cert_data: Certificate data structure
            compliance_id: Associated compliance record ID
            
        Returns:
            Certificate record with digital signature
        """
        # Generate certificate number
        cert_number = f"Cert-EUDR-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate expiry date
        issue_date = datetime.utcnow()
        expiry_date = issue_date + timedelta(days=cert_data.validity_days)
        
        # Build certificate payload
        cert_payload = {
            "certificate_number": cert_number,
            "certificate_type": cert_data.certificate_type,
            "entity": {
                "type": cert_data.entity_type,
                "id": cert_data.entity_id,
                "name": cert_data.entity_name
            },
            "scope": {
                "description": cert_data.scope_description,
                "geographic": cert_data.geographic_scope,
                "products": cert_data.product_scope
            },
            "verification": {
                "standard": cert_data.verification_standard,
                "body": cert_data.verification_body
            },
            "validity": {
                "issue_date": issue_date.isoformat(),
                "expiry_date": expiry_date.isoformat()
            }
        }
        
        # Generate HMAC signature
        hmac_signature = self._generate_hmac(json.dumps(cert_payload, sort_keys=True))
        
        # Create certificate record
        certificate = Certificate(
            certificate_number=cert_number,
            certificate_type=cert_data.certificate_type,
            entity_type=cert_data.entity_type,
            entity_id=cert_data.entity_id,
            issue_date=issue_date,
            expiry_date=expiry_date,
            scope_description=cert_data.scope_description,
            geographic_scope=cert_data.geographic_scope,
            product_scope=cert_data.product_scope,
            verification_standard=cert_data.verification_standard,
            verification_body=cert_data.verification_body,
            hmac_signature=hmac_signature,
            signing_algorithm="HMAC-SHA256",
            status=CertificateStatus.ACTIVE
        )
        
        return certificate
    
    def verify_certificate(self, certificate: Certificate) -> Dict[str, Any]:
        """
        Verify the authenticity of a certificate.
        
        Args:
            certificate: Certificate to verify
            
        Returns:
            Verification result dictionary
        """
        result = {
            "valid": False,
            "certificate_number": certificate.certificate_number,
            "checks": []
        }
        
        # Check 1: Certificate is not expired
        if certificate.expiry_date and certificate.expiry_date > datetime.utcnow():
            result["checks"].append({
                "check": "expiry_date",
                "passed": True,
                "message": "Certificate is within validity period"
            })
        else:
            result["checks"].append({
                "check": "expiry_date",
                "passed": False,
                "message": "Certificate has expired" if certificate.expiry_date else "No expiry date set"
            })
            return result
        
        # Check 2: Certificate is active
        if certificate.status == CertificateStatus.ACTIVE:
            result["checks"].append({
                "check": "status",
                "passed": True,
                "message": "Certificate is active"
            })
        else:
            result["checks"].append({
                "check": "status",
                "passed": False,
                "message": f"Certificate status is {certificate.status}"
            })
            return result
        
        # Check 3: Verify HMAC signature
        cert_payload = json.dumps({
            "certificate_number": certificate.certificate_number,
            "certificate_type": certificate.certificate_type,
            "entity_type": certificate.entity_type,
            "entity_id": certificate.entity_id,
            "issue_date": certificate.issue_date.isoformat() if certificate.issue_date else None,
            "expiry_date": certificate.expiry_date.isoformat() if certificate.expiry_date else None,
        }, sort_keys=True)
        
        expected_signature = self._generate_hmac(cert_payload)
        
        if certificate.hmac_signature == expected_signature:
            result["checks"].append({
                "check": "hmac_signature",
                "passed": True,
                "message": "HMAC signature verified"
            })
        else:
            result["checks"].append({
                "check": "hmac_signature",
                "passed": False,
                "message": "HMAC signature mismatch - certificate may be tampered"
            })
            return result
        
        result["valid"] = True
        result["message"] = "Certificate is valid and authentic"
        
        return result
    
    def generate_dds_xml(self, dds: DueDiligenceStatement) -> str:
        """
        Generate EUDR-compliant XML representation of DDS.
        
        Args:
            dds: DueDiligenceStatement instance
            
        Returns:
            XML string
        """
        root = ET.Element("DueDiligenceStatement")
        
        # Header
        header = ET.SubElement(root, "Header")
        ET.SubElement(header, "DDSNumber").text = dds.dds_number
        ET.SubElement(header, "Version").text = dds.version
        ET.SubElement(header, "GenerationDate").text = datetime.utcnow().isoformat()
        
        # Operator
        operator = ET.SubElement(root, "Operator")
        ET.SubElement(operator, "Name").text = dds.operator_name
        ET.SubElement(operator, "ID").text = dds.operator_id or ""
        
        contact = ET.SubElement(operator, "Contact")
        ET.SubElement(contact, "Name").text = dds.contact_name or ""
        ET.SubElement(contact, "Email").text = dds.contact_email or ""
        ET.SubElement(contact, "Address").text = dds.contact_address or ""
        
        # Commodity
        commodity = ET.SubElement(root, "Commodity")
        ET.SubElement(commodity, "Type").text = dds.commodity_type
        ET.SubElement(commodity, "HSCode").text = dds.hs_code
        ET.SubElement(commodity, "CountryOfOrigin").text = dds.country_of_origin
        ET.SubElement(commodity, "Quantity").text = str(dds.quantity)
        ET.SubElement(commodity, "Unit").text = dds.unit
        
        # Risk Assessment
        risk = ET.SubElement(root, "RiskAssessment")
        ET.SubElement(risk, "Level").text = dds.risk_level
        
        if dds.risk_assessment:
            details = ET.SubElement(risk, "Details")
            for key, value in dds.risk_assessment.items():
                ET.SubElement(details, key.capitalize()).text = str(value)
        
        # Signature
        signature = ET.SubElement(root, "DigitalSignature")
        ET.SubElement(signature, "Algorithm").text = "HMAC-SHA256"
        ET.SubElement(signature, "Hash").text = dds.dds_hash or ""
        ET.SubElement(signature, "Value").text = dds.signature or ""
        
        return ET.tostring(root, encoding='unicode', method='xml')
    
    def calculate_compliance_score(
        self,
        compliance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate overall EUDR compliance score.
        
        Args:
            compliance_data: Dictionary with compliance requirements
            
        Returns:
            Compliance score and status
        """
        requirements = settings.eudr.compliance_scoring_weights
        
        total_score = 0
        max_score = sum(requirements.values())
        
        results = {}
        passed_count = 0
        
        for field_name, weight in requirements.items():
            value = compliance_data.get(field_name, 0)
            if value == 1:  # Passed
                total_score += weight
                passed_count += 1
                results[field_name] = {"status": "passed", "score": weight}
            elif value == 2:  # Unknown
                total_score += weight / 2
                results[field_name] = {"status": "unknown", "score": weight / 2}
            else:  # Failed or missing
                results[field_name] = {"status": "failed", "score": 0}
        
        # Calculate percentage
        compliance_percentage = (total_score / max_score) * 100
        
        # Determine status
        thresholds = settings.eudr.compliance_thresholds
        if compliance_percentage >= thresholds["compliant"]:
            status = ComplianceStatus.COMPLIANT
        elif compliance_percentage >= thresholds["under_review"]:
            status = ComplianceStatus.UNDER_REVIEW
        elif compliance_percentage >= thresholds["requires_action"]:
            status = ComplianceStatus.REQUIRES_ACTION
        else:
            status = ComplianceStatus.NON_COMPLIANT
        
        return {
            "compliance_percentage": compliance_percentage,
            "total_score": total_score,
            "max_score": max_score,
            "status": status.value,
            "details": results,
            "passed_requirements": passed_count,
            "total_requirements": len(requirements)
        }
    
    def _generate_hash(self, data: str) -> str:
        """Generate SHA-256 hash of data"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _generate_signature(self, data_hash: str) -> str:
        """Generate HMAC signature for data hash"""
        return hmac.new(
            self.secret_key.encode(),
            data_hash.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _generate_hmac(self, data: str) -> str:
        """Generate HMAC signature for data"""
        return hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()


# Service instance
eudr_service = EUDRIntegrationService()
