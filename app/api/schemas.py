"""
Plotra Platform - Pydantic Schemas for API Validation
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator
from enum import Enum


# ============== User Schemas ==============

class UserRoleEnum(str, Enum):
    FARMER = "farmer"
    COOP_ADMIN = "coop_admin"
    COOP_OFFICER = "coop_officer"  # Factor/Competent person
    PLATFORM_ADMIN = "platform_admin"
    EUDR_REVIEWER = "eudr_reviewer"  # Belgian team
    AUDITOR = "auditor"
    SUPER_ADMIN = "super_admin"


class VerificationStatusEnum(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = None
    role: UserRoleEnum = UserRoleEnum.FARMER
    country: str = "Kenya"
    county: Optional[str] = None
    subcounty: Optional[str] = None
    # New fields for Layer 1
    gender: Optional[str] = None  # "F" or "M"
    id_type: Optional[str] = None  # "national_id", "passport", "birth_cert"
    id_number: Optional[str] = None
    # Payment/Payout fields (Layer 5)
    payout_method: Optional[str] = "mpesa"  # "mpesa", "bank", "cash"
    payout_recipient_id: Optional[str] = None  # M-Pesa number or bank account
    payout_bank_name: Optional[str] = None
    payout_account_number: Optional[str] = None
    # Cooperative membership (for farmers)
    cooperative_code: Optional[str] = None  # Code of cooperative farmer belongs to


class UserUpdate(BaseModel):
    """Schema for user profile updates"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    county: Optional[str] = None
    subcounty: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    date_of_birth: Optional[str] = None
    # New fields for updates
    gender: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    payout_method: Optional[str] = None
    payout_recipient_id: Optional[str] = None
    payout_bank_name: Optional[str] = None
    payout_account_number: Optional[str] = None


class UserResponse(BaseModel):
    """Schema for user data in responses"""
    id: str
    email: str
    first_name: str
    last_name: str
    phone_number: Optional[str] = Field(None, alias="phone")
    role: str  # Use str to handle both uppercase and lowercase from database
    verification_status: Optional[str] = None  # Use str to handle both uppercase and lowercase
    country: str
    county: Optional[str]
    created_at: datetime
    # New fields in responses
    gender: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    payout_method: Optional[str] = None
    payout_recipient_id: Optional[str] = None
    payout_bank_name: Optional[str] = None
    payout_account_number: Optional[str] = None
    # Cooperative membership
    cooperative_id: Optional[int] = None
    belongs_to_cooperative: Optional[bool] = False
    
    class Config:
        from_attributes = True
        populate_by_name = True
    
    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v
    
    @field_validator('verification_status', mode='before')
    @classmethod
    def normalize_verification_status(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v


# ============== Authentication Schemas ==============

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Token payload data"""
    sub: str
    email: str
    role: str
    exp: datetime


class LoginRequest(BaseModel):
    """Login request"""
    username: EmailStr  # Can be email
    password: str


class LoginFormRequest(BaseModel):
    """Form-based login request"""
    username: EmailStr
    password: str
    grant_type: str = "password"


# ============== Farm Schemas ==============

class LandUseTypeEnum(str, Enum):
    AGROFORESTRY = "agroforestry"
    MONOCROP = "monocrop"
    MIXED_CROPPING = "mixed_cropping"
    FOREST_RESERVE = "forest_reserve"
    BUFFER_ZONE = "buffer_zone"


class OwnershipTypeEnum(str, Enum):
    OWNED = "owned"
    LEASED = "leased"
    CUSTOMARY = "customary"
    TENANT = "tenant"
    COMMUNITY = "community"


class ParcelCreate(BaseModel):
    """Schema for creating farm parcel with GPS coordinates"""
    parcel_number: int
    parcel_name: Optional[str] = None
    boundary_geojson: Dict[str, Any]  # GeoJSON polygon
    area_hectares: Optional[float] = None
    gps_accuracy_meters: Optional[float] = None
    mapping_device: Optional[str] = None
    land_use_type: LandUseTypeEnum = LandUseTypeEnum.AGROFORESTRY
    coffee_area_hectares: Optional[float] = None


class ParcelResponse(BaseModel):
    """Parcel response schema"""
    id: int
    parcel_number: int
    parcel_name: Optional[str]
    area_hectares: Optional[float]
    boundary_geojson: Optional[Dict[str, Any]]
    land_use_type: LandUseTypeEnum
    created_at: datetime


class FarmCreate(BaseModel):
    """Schema for creating a farm"""
    farm_name: Optional[str] = None
    total_area_hectares: Optional[float] = None
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    coffee_varieties: List[str] = []
    years_farming: Optional[int] = None
    average_annual_production_kg: Optional[float] = None
    parcels: List[ParcelCreate] = []


class FarmResponse(BaseModel):
    """Farm response schema"""
    id: int
    owner_id: int
    farm_name: Optional[str]
    total_area_hectares: Optional[float]
    coffee_varieties: Optional[List[str]] = []
    land_use_type: LandUseTypeEnum
    deforestation_risk_score: float
    compliance_status: str
    # Profile fields
    farm_type: Optional[str] = None
    land_registration_number: Optional[str] = None
    soil_type: Optional[str] = None
    terrain: Optional[str] = None
    year_coffee_planted: Optional[int] = None
    coffee_tree_count: Optional[int] = None
    farm_status: Optional[str] = None
    planting_method: Optional[str] = None
    irrigation_used: Optional[bool] = None
    irrigation_type: Optional[str] = None
    mixed_farming: Optional[bool] = None
    coffee_percent: Optional[float] = None
    other_crops: Optional[List[str]] = None
    livestock: Optional[bool] = None
    livestock_type: Optional[List[str]] = None
    crop_rotation: Optional[bool] = None
    trees_planted_last5: Optional[bool] = None
    tree_species: Optional[List[str]] = None
    tree_count: Optional[int] = None
    tree_planting_reason: Optional[List[str]] = None
    trees_cleared: Optional[bool] = None
    reason_for_clearing: Optional[str] = None
    current_canopy_cover: Optional[str] = None
    satellite_consent: Optional[bool] = None
    historical_imagery_consent: Optional[bool] = None
    monitoring_frequency: Optional[str] = None
    certifications: Optional[List[str]] = None
    cert_expiry_date: Optional[datetime] = None
    previous_violations: Optional[bool] = None
    violation_details: Optional[str] = None
    eudr_risk_flags: Optional[List[str]] = None
    profile_submitted: bool = False
    parcels: List[ParcelResponse]
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Farmer Profile Submission Schema ==============

class EudrRisks(BaseModel):
    """EUDR risk flags extracted from profile submission"""
    trees_cleared: bool = False
    established_after_2020: bool = False
    communal_no_registration: bool = False
    high_risk_flags: List[str] = []


class FarmerProfilePersonal(BaseModel):
    """Section 1 — personal details from farmer profile form"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dob: Optional[str] = None
    national_id: Optional[str] = None
    county: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    address: Optional[str] = None
    member_of_coop: Optional[str] = None  # "yes" or "no"
    cooperative_name: Optional[str] = None
    coop_reg_number: Optional[str] = None


class FarmerProfileFarm(BaseModel):
    """Section 2 — farm & EUDR fields from farmer profile form"""
    farm_name: Optional[str] = None
    farm_type: Optional[str] = None
    land_reg_number: Optional[str] = None
    total_area: Optional[float] = None
    altitude: Optional[float] = None
    soil_type: Optional[str] = None
    terrain: Optional[str] = None
    boundary_geojson: Optional[Dict[str, Any]] = None
    area_calculated: Optional[float] = None
    coffee_variety: Optional[List[str]] = None
    year_coffee_planted: Optional[int] = None
    coffee_tree_count: Optional[int] = None
    farm_status: Optional[str] = None
    planting_method: Optional[str] = None
    irrigation_used: Optional[str] = None  # "yes"/"no"
    irrigation_type: Optional[str] = None
    estimated_yield: Optional[float] = None
    mixed_farming: Optional[str] = None  # "yes"/"no"
    coffee_percent: Optional[str] = None
    other_crops: Optional[List[str]] = None
    livestock: Optional[str] = None  # "yes"/"no"
    livestock_type: Optional[List[str]] = None
    crop_rotation: Optional[str] = None  # "yes"/"no"
    trees_planted_last5: Optional[str] = None  # "yes"/"no"
    tree_species: Optional[List[str]] = None
    tree_count: Optional[int] = None
    tree_planting_reason: Optional[List[str]] = None
    trees_cleared: Optional[str] = None  # "yes"/"no"
    reason_for_clearing: Optional[str] = None
    current_canopy_cover: Optional[str] = None
    satellite_consent: Optional[bool] = None
    historical_imagery_consent: Optional[bool] = None
    monitoring_frequency: Optional[str] = None
    certifications: Optional[List[str]] = None
    cert_expiry_date: Optional[str] = None
    previous_violations: Optional[str] = None  # "yes"/"no"
    violation_details: Optional[str] = None


class FarmerProfileSubmit(BaseModel):
    """Full farmer profile submission payload (matches frontend farmer-profile.js)"""
    personal: FarmerProfilePersonal
    farm: FarmerProfileFarm
    eudr_risks: Optional[EudrRisks] = None


# ============== Document Schemas ==============

class DocumentTypeEnum(str, Enum):
    TITLE_DEED = "title_deed"
    LEASE_AGREEMENT = "lease_agreement"
    CUSTOMARY_RIGHTS = "customary_rights"
    INHERITANCE_LETTER = "inheritance_letter"
    COMMUNITY_LAND_TITLE = "community_land_title"
    OTHER = "other"


class DocumentUpload(BaseModel):
    """Schema for document upload metadata"""
    document_type: DocumentTypeEnum
    title: str
    description: Optional[str] = None
    ownership_type: OwnershipTypeEnum = OwnershipTypeEnum.CUSTOMARY
    issuing_authority: Optional[str] = None
    reference_number: Optional[str] = None
    document_date: Optional[datetime] = None


class DocumentResponse(BaseModel):
    """Document response schema"""
    id: int
    farm_id: int
    document_type: DocumentTypeEnum
    title: str
    description: Optional[str]
    checksum_sha256: Optional[str]
    verification_status: str
    created_at: datetime


# ============== Traceability Schemas ==============

class QualityGradeEnum(str, Enum):
    AA = "AA"
    AB = "AB"
    PB = "PB"
    C = "C"
    AAAA = "AAAA"
    UNGRADED = "ungraded"


class DeliveryStatusEnum(str, Enum):
    PENDING = "pending"
    RECEIVED = "received"
    WEIGHED = "weighed"
    QUALITY_CHECKED = "quality_checked"
    PROCESSED = "processed"
    REJECTED = "rejected"


class DeliveryCreate(BaseModel):
    """Schema for recording coffee delivery"""
    farm_id: int
    gross_weight_kg: float
    tare_weight_kg: float = 0.0
    quality_grade: Optional[QualityGradeEnum] = None
    moisture_content: Optional[float] = None
    cherry_type: Optional[str] = None
    picking_date: Optional[datetime] = None


class DeliveryResponse(BaseModel):
    """Delivery response schema"""
    id: int
    delivery_number: str
    farm_id: int
    net_weight_kg: float
    quality_grade: Optional[QualityGradeEnum]
    status: DeliveryStatusEnum
    created_at: datetime


class BatchCreate(BaseModel):
    """Schema for creating a coffee batch"""
    batch_number: str
    crop_year: int
    harvest_start_date: Optional[datetime] = None
    harvest_end_date: Optional[datetime] = None
    processing_method: str = "washed"
    delivery_ids: List[int] = []


class BatchResponse(BaseModel):
    """Batch response schema"""
    id: int
    batch_number: str
    cooperative_id: int
    crop_year: int
    total_weight_kg: Optional[float]
    quality_grade: Optional[QualityGradeEnum]
    compliance_status: str
    created_at: datetime


# ============== Compliance Schemas ==============

class ComplianceStatusEnum(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    PENDING_DOCUMENTS = "pending_documents"
    REQUIRES_ACTION = "requires_action"


class ComplianceChecklist(BaseModel):
    """EUDR compliance checklist"""
    deforestation_free: int = 0  # 0=no, 1=yes, 2=unknown
    legal_ownership: int = 0
    traceability_verified: int = 0
    documents_complete: int = 0
    satellite_analysis_complete: int = 0


class ComplianceResponse(BaseModel):
    """Compliance status response"""
    id: int
    entity_type: str
    entity_id: int
    status: ComplianceStatusEnum
    risk_score: float
    checklist: ComplianceChecklist
    reviewed_by: Optional[int]
    created_at: datetime


# ============== Satellite Analysis Schemas ==============

class AnalysisStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRequest(BaseModel):
    """Request satellite analysis for parcels"""
    parcel_ids: List[int]
    acquisition_date: Optional[datetime] = None


class AnalysisResponse(BaseModel):
    """Satellite analysis response"""
    id: int
    analysis_id: str
    parcel_id: int
    status: AnalysisStatusEnum
    ndvi_mean: Optional[float]
    risk_score: Optional[float]
    risk_level: Optional[str]
    acquisition_date: datetime


# ============== EUDR Schemas ==============

class DDSRequest(BaseModel):
    """Due Diligence Statement request"""
    operator_name: str
    operator_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_address: Optional[str] = None
    commodity_type: str = "Coffee"
    hs_code: str = "090111"
    country_of_origin: str = "Kenya"
    quantity: float
    unit: str = "kg"
    supplier_name: Optional[str] = None
    supplier_country: Optional[str] = None
    first_placement_country: Optional[str] = None
    first_placement_date: Optional[datetime] = None
    farm_ids: List[int] = []


class DDSResponse(BaseModel):
    """Due Diligence Statement response"""
    id: int
    dds_number: str
    operator_name: str
    submission_status: str
    risk_level: str
    dds_hash: Optional[str]
    signature: Optional[str]
    created_at: datetime


class CertificateRequest(BaseModel):
    """Certificate generation request"""
    certificate_type: str
    entity_type: str
    entity_id: int
    entity_name: str
    scope_description: str = ""
    product_scope: List[str] = []
    validity_days: int = 365


class CertificateResponse(BaseModel):
    """Certificate response"""
    id: int
    certificate_number: str
    certificate_type: str
    issue_date: datetime
    expiry_date: datetime
    status: str
    is_valid: bool


# ============== Utility Schemas ==============

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response schema"""
    detail: str
    error_code: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class GeoJSONFeature(BaseModel):
    """GeoJSON feature schema"""
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any] = {}


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON feature collection"""
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]


# ============== Cooperative Schemas ==============

class CooperativeCreate(BaseModel):
    """Schema for creating a cooperative"""
    name: str = Field(..., min_length=1, max_length=255)
    registration_number: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    country: str = "Kenya"
    county: Optional[str] = None
    subcounty: Optional[str] = None
    cooperative_type: Optional[str] = None  # "general" or "women"
    # Admin user to create and assign
    admin_email: Optional[EmailStr] = None
    admin_first_name: Optional[str] = None
    admin_last_name: Optional[str] = None
    admin_phone: Optional[str] = None
    admin_password: Optional[str] = Field(None, min_length=8)
    # Contact person user (optional)
    contact_person_email: Optional[EmailStr] = None
    contact_person_first_name: Optional[str] = None
    contact_person_last_name: Optional[str] = None
    contact_person_phone: Optional[str] = None
    send_password_reset: bool = True  # Whether to send password reset emails


class CooperativeUpdate(BaseModel):
    """Schema for updating a cooperative"""
    name: Optional[str] = None
    registration_number: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    country: Optional[str] = None
    county: Optional[str] = None
    subcounty: Optional[str] = None
    cooperative_type: Optional[str] = None
    is_verified: Optional[bool] = None


class CooperativeResponse(BaseModel):
    """Schema for cooperative response"""
    id: int
    name: str
    code: str  # Unique code for farmer registration
    registration_number: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    country: str
    county: Optional[str]
    subcounty: Optional[str]
    cooperative_type: Optional[str]
    primary_admin_id: Optional[int]
    contact_person_id: Optional[int]
    is_verified: bool
    verification_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    # Password reset email status
    admin_password_reset_sent: Optional[bool] = None
    contact_person_password_reset_sent: Optional[bool] = None

    class Config:
        from_attributes = True


class CooperativeWithMembers(CooperativeResponse):
    """Cooperative with member count"""
    member_count: int = 0
    admin_name: Optional[str] = None
