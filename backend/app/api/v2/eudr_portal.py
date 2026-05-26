"""
EUDR Portal API - Public endpoints for exporter and importer form submissions.
No authentication required — these forms are shared via public links.
"""
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.eudr_portal import EUDRExporterSubmission, EUDRImporterSubmission

logger = logging.getLogger(__name__)
router = APIRouter()


def _gen_ref(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ─────────────────────────────────────────
#  EXPORTER SCHEMAS
# ─────────────────────────────────────────

class ExporterKYC(BaseModel):
    full_name: str
    national_id: Optional[str] = None
    phone: Optional[str] = None
    email: str
    country: Optional[str] = None
    id_document_name: Optional[str] = None

class ExporterCompany(BaseModel):
    company_name: str
    reg_number: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    cert_document_name: Optional[str] = None

class ExporterConsignment(BaseModel):
    consignment_ref: Optional[str] = None
    coffee_variety: Optional[str] = None
    quantity_kg: Optional[str] = None
    harvest_year: Optional[str] = None
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    hs_code: Optional[str] = None
    destination_country: Optional[str] = None

class CooperativeData(BaseModel):
    name: Optional[str] = None
    reg_number: Optional[str] = None
    region: Optional[str] = None
    county: Optional[str] = None
    member_count: Optional[str] = None
    farm_area_ha: Optional[str] = None
    certification: Optional[str] = None

class ExporterPolygon(BaseModel):
    polygon_filename: Optional[str] = None
    lat: Optional[str] = None
    lon: Optional[str] = None

class ExporterDeclarations(BaseModel):
    d1: bool = False
    d2: bool = False
    d3: bool = False
    d4: bool = False
    d5: bool = False
    d6: bool = False
    signature: Optional[str] = None
    sign_date: Optional[str] = None

class ExporterSubmitRequest(BaseModel):
    kyc: ExporterKYC
    company: ExporterCompany
    consignment: ExporterConsignment
    cooperatives: List[CooperativeData] = []
    polygon: Optional[ExporterPolygon] = None
    declarations: ExporterDeclarations

class ExporterSubmitResponse(BaseModel):
    success: bool
    reference_number: str
    submission_id: str
    message: str


# ─────────────────────────────────────────
#  IMPORTER SCHEMAS
# ─────────────────────────────────────────

class ImporterKYC(BaseModel):
    full_name: str
    role: Optional[str] = None
    id_number: Optional[str] = None
    phone: Optional[str] = None
    email: str
    member_state: Optional[str] = None
    identity_doc_name: Optional[str] = None

class ImporterOperator(BaseModel):
    company_name: str
    eori: Optional[str] = None
    vat: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal: Optional[str] = None
    license_doc_name: Optional[str] = None

class ImporterSupplier(BaseModel):
    exporter_name: Optional[str] = None
    exporter_country: Optional[str] = None
    exporter_email: Optional[str] = None
    consignment_ref: Optional[str] = None
    submission_ref: Optional[str] = None

class ImporterConsignmentReview(BaseModel):
    coffee_variety: Optional[str] = None
    quantity_kg: Optional[str] = None
    harvest_year: Optional[str] = None
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    arrival_date: Optional[str] = None
    port: Optional[str] = None
    notes: Optional[str] = None

class ImporterRiskAssessment(BaseModel):
    country_risk: Optional[str] = None
    chain_complexity: Optional[str] = None
    evidence_1: bool = False
    evidence_2: bool = False
    evidence_3: bool = False
    evidence_4: bool = False
    evidence_5: bool = False
    risk_conclusion: Optional[str] = None
    notes: Optional[str] = None

class ImporterDueDiligence(BaseModel):
    reviewer_name: Optional[str] = None
    reviewer_title: Optional[str] = None
    review_date: Optional[str] = None
    approval_1: bool = False
    approval_2: bool = False
    approval_3: bool = False
    signature: Optional[str] = None
    internal_ref: Optional[str] = None

class ImporterSubmitRequest(BaseModel):
    kyc: ImporterKYC
    operator: ImporterOperator
    supplier: ImporterSupplier
    consignment_review: ImporterConsignmentReview
    risk_assessment: ImporterRiskAssessment
    due_diligence: ImporterDueDiligence

class ImporterSubmitResponse(BaseModel):
    success: bool
    reference_number: str
    submission_id: str
    message: str


# ─────────────────────────────────────────
#  EXPORTER ENDPOINTS
# ─────────────────────────────────────────

@router.post("/portal/exporter", response_model=ExporterSubmitResponse)
async def submit_exporter_form(
    payload: ExporterSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    ref = _gen_ref("PLT")
    client_ip = request.client.host if request.client else None

    submission = EUDRExporterSubmission(
        reference_number=ref,
        status="submitted",
        full_name=payload.kyc.full_name,
        email=payload.kyc.email,
        phone=payload.kyc.phone,
        national_id=payload.kyc.national_id,
        country_of_residence=payload.kyc.country,
        company_name=payload.company.company_name,
        business_reg_number=payload.company.reg_number,
        consignment_ref=payload.consignment.consignment_ref,
        coffee_variety=payload.consignment.coffee_variety,
        quantity_kg=payload.consignment.quantity_kg,
        harvest_year=payload.consignment.harvest_year,
        origin_country=payload.consignment.origin_country,
        destination_country=payload.consignment.destination_country,
        form_data=payload.model_dump(),
        ip_address=client_ip,
    )

    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    logger.info(f"Exporter submission created: {ref} from {client_ip}")
    return ExporterSubmitResponse(
        success=True,
        reference_number=ref,
        submission_id=submission.id,
        message="Exporter declaration submitted successfully."
    )


@router.get("/portal/exporter/{submission_id}")
async def get_exporter_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(EUDRExporterSubmission).where(EUDRExporterSubmission.id == submission_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {
        "id": s.id,
        "reference_number": s.reference_number,
        "status": s.status,
        "full_name": s.full_name,
        "email": s.email,
        "company_name": s.company_name,
        "consignment_ref": s.consignment_ref,
        "form_data": s.form_data,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
    }


@router.get("/portal/exporter")
async def list_exporter_submissions(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    result = await db.execute(
        select(EUDRExporterSubmission)
        .order_by(EUDRExporterSubmission.submitted_at.desc())
        .limit(limit).offset(offset)
    )
    submissions = result.scalars().all()
    return [
        {
            "id": s.id,
            "reference_number": s.reference_number,
            "full_name": s.full_name,
            "email": s.email,
            "company_name": s.company_name,
            "consignment_ref": s.consignment_ref,
            "origin_country": s.origin_country,
            "status": s.status,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        }
        for s in submissions
    ]


# ─────────────────────────────────────────
#  IMPORTER ENDPOINTS
# ─────────────────────────────────────────

@router.post("/portal/importer", response_model=ImporterSubmitResponse)
async def submit_importer_form(
    payload: ImporterSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    ref = _gen_ref("DDS")
    client_ip = request.client.host if request.client else None

    submission = EUDRImporterSubmission(
        reference_number=ref,
        status="submitted",
        full_name=payload.kyc.full_name,
        email=payload.kyc.email,
        phone=payload.kyc.phone,
        eu_member_state=payload.kyc.member_state,
        company_name=payload.operator.company_name,
        eori_number=payload.operator.eori,
        exporter_name=payload.supplier.exporter_name,
        consignment_ref=payload.supplier.consignment_ref,
        risk_conclusion=payload.risk_assessment.risk_conclusion,
        form_data=payload.model_dump(),
        ip_address=client_ip,
    )

    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    logger.info(f"Importer submission created: {ref} from {client_ip}")
    return ImporterSubmitResponse(
        success=True,
        reference_number=ref,
        submission_id=submission.id,
        message="Importer due diligence submitted successfully."
    )


@router.get("/portal/importer/{submission_id}")
async def get_importer_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(EUDRImporterSubmission).where(EUDRImporterSubmission.id == submission_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {
        "id": s.id,
        "reference_number": s.reference_number,
        "status": s.status,
        "full_name": s.full_name,
        "email": s.email,
        "company_name": s.company_name,
        "eori_number": s.eori_number,
        "exporter_name": s.exporter_name,
        "consignment_ref": s.consignment_ref,
        "risk_conclusion": s.risk_conclusion,
        "form_data": s.form_data,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
    }


@router.get("/portal/importer")
async def list_importer_submissions(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    result = await db.execute(
        select(EUDRImporterSubmission)
        .order_by(EUDRImporterSubmission.submitted_at.desc())
        .limit(limit).offset(offset)
    )
    submissions = result.scalars().all()
    return [
        {
            "id": s.id,
            "reference_number": s.reference_number,
            "full_name": s.full_name,
            "email": s.email,
            "company_name": s.company_name,
            "eori_number": s.eori_number,
            "consignment_ref": s.consignment_ref,
            "risk_conclusion": s.risk_conclusion,
            "status": s.status,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        }
        for s in submissions
    ]
