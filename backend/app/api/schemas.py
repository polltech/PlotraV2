"""
Plotra Platform - Pydantic Schemas for API Validation
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict, model_validator
from enum import Enum


# ============== Cooperative Schemas ==============

class CooperativeTypeEnum(str, Enum):
    AGRICULTURAL = "agricultural"
    MARKETING = "marketing"
    PROCESSING = "processing"
    MULTIPURPOSE = "multipurpose"
    WOMEN_BASED = "women"
    GENERAL = "general"
    MEN_BASED = "men"


# ============== Country and Phone ==============

ALLOWED_COUNTRIES = ["Kenya", "Uganda", "Tanzania"]

# Mapping from country name to phone prefix
COUNTRY_PHONE_PREFIXES = {
    "Kenya": "+254",
    "Uganda": "+256",
    "Tanzania": "+255",
}


class CooperativeCreate(BaseModel):
    """Schema for creating a cooperative with detailed information"""
    # Basic Cooperative Information
    name: str = Field(..., min_length=1, max_length=255)
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: str = "Kenya"
    county: Optional[str] = None
    district: Optional[str] = None
    subcounty: Optional[str] = None
    ward: Optional[str] = None
    cooperative_type: Optional[CooperativeTypeEnum] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    establishment_date: Optional[datetime] = None
    contact_person: Optional[str] = None
    contact_person_phone: Optional[str] = None
    contact_person_email: Optional[str] = None
    legal_status: Optional[str] = None
    governing_document: Optional[str] = None
    
    # Required Documents (array of document IDs to submit)
    required_documents: Optional[List[str]] = Field(default_factory=list, description="Array of required document IDs that will be submitted")
    
    # Cooperative Admin Information (Required)
    admin_email: EmailStr = Field(..., description="Email address of the cooperative admin (will receive login setup link)")
    admin_first_name: Optional[str] = None
    admin_last_name: Optional[str] = None
    admin_phone: Optional[str] = None


class CooperativeResponse(BaseModel):
    """Schema for cooperative data in responses (detailed view)"""
    id: str
    name: str
    code: str  # Unique code for farmer registration
    registration_number: Optional[str]
    tax_id: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    country: str
    county: Optional[str]
    district: Optional[str]
    subcounty: Optional[str]
    ward: Optional[str]
    cooperative_type: Optional[CooperativeTypeEnum]
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    establishment_date: Optional[datetime]
    member_count: int
    contact_person: Optional[str] = None
    contact_person_phone: Optional[str] = None
    contact_person_email: Optional[str] = None
    legal_status: Optional[str] = None
    governing_document: Optional[str] = None
    required_documents: Optional[List[str]] = Field(default_factory=list)
    is_active: bool
    verification_status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CooperativeAdminCreate(BaseModel):
    """Schema for creating a cooperative admin user"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = None
    cooperative_id: str


class CooperativeUserRoleEnum(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    ACCOUNTANT = "accountant"
    FIELD_OFFICER = "field_officer"
    QUALITY_CONTROL = "quality_control"


class CooperativeUserAddRequest(BaseModel):
    """Request to add a user to cooperative with specific role"""
    user_id: int
    cooperative_role: CooperativeUserRoleEnum = CooperativeUserRoleEnum.MEMBER
    membership_number: Optional[str] = None
    is_active: bool = True


class CooperativeUserResponse(BaseModel):
    """Schema for cooperative user with role information"""
    id: str
    email: str
    first_name: str
    last_name: str
    phone_number: Optional[str]
    role: str
    cooperative_role: Optional[CooperativeUserRoleEnum]
    membership_number: Optional[str]
    is_active: bool
    joined_at: datetime
    
    class Config:
        from_attributes = True


# ============== User Schemas ==============

class UserRoleEnum(str, Enum):
    FARMER = "farmer"
    COOPERATIVE_OFFICER = "cooperative_officer"
    PLOTRA_ADMIN = "plotra_admin"
    EUDR_REVIEWER = "eudr_reviewer"


class VerificationStatusEnum(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class UserCreate(BaseModel):
    """Schema for user registration"""
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = None
    role: UserRoleEnum = UserRoleEnum.FARMER
    country: Optional[str] = Field(None, description="Country (Kenya, Uganda, Tanzania)")
    county: Optional[str] = None
    subcounty: Optional[str] = None
    gender: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    cooperative_code: Optional[str] = None
    payout_method: Optional[str] = None
    payout_recipient_id: Optional[str] = None
    payout_bank_name: Optional[str] = None
    payout_account_number: Optional[str] = None

    @field_validator('country')
    def validate_country(cls, v):
        if v is not None and v not in ALLOWED_COUNTRIES:
            raise ValueError("Country must be one of: Kenya, Uganda, Tanzania")
        return v

    @field_validator('phone_number')
    def validate_phone_number(cls, v):
        if v is None:
            return v
        phone = v.strip()
        # Accept E.164 format or local format (will normalize in model_validator)
        if phone.startswith('+'):
            # Validate E.164
            digits = phone[1:]
            if not digits.isdigit():
                raise ValueError("Phone number must contain only digits after country code")
            if len(digits) < 9 or len(digits) > 12:
                raise ValueError("Phone number length appears invalid")
            allowed_prefixes = ['+254', '+255', '+256']
            if not any(phone.startswith(p) for p in allowed_prefixes):
                raise ValueError("Phone number must be from Kenya (+254), Uganda (+256), or Tanzania (+255)")
        else:
            # Local format: allow digits only, with optional leading 0
            digits = phone.lstrip('0')
            if not digits.isdigit() or len(digits) < 8 or len(digits) > 10:
                raise ValueError("Enter phone as local number (e.g., 0712345678) or with country code (e.g., +254712345678)")
        return phone

    @model_validator(mode='after')
    def check_contact_info(self):
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone number must be provided")
        # Normalize local phone to E.164 using country
        if self.phone_number and not self.phone_number.startswith('+'):
            country = self.country or 'Kenya'
            prefix = COUNTRY_PHONE_PREFIXES.get(country, '+254')
            digits = self.phone_number.lstrip('0')
            self.phone_number = prefix + digits
        return self


class UserUpdate(BaseModel):
    """Schema for user profile updates"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    county: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None


class UserResponse(BaseModel):
    """Schema for user data in responses"""
    id: str
    email: Optional[str] = None
    first_name: str
    last_name: str
    phone_number: Optional[str] = Field(None, alias="phone")
    role: UserRoleEnum
    verification_status: Optional[VerificationStatusEnum] = None
    country: Optional[str] = None
    county: Optional[str] = None
    subcounty: Optional[str] = None
    gender: Optional[str] = None
    national_id: Optional[str] = None
    created_at: datetime
    # Two-stage farmer verification tracking
    coop_status: Optional[str] = None
    coop_verified_by_name: Optional[str] = None
    coop_verified_at: Optional[datetime] = None
    coop_notes: Optional[str] = None
    admin_verified_by_name: Optional[str] = None
    admin_verified_at: Optional[datetime] = None
    admin_notes: Optional[str] = None
    page_permissions: Optional[list] = None
    cooperative_id: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True


class PendingVerificationResponse(BaseModel):
    """Schema for pending verification data in admin dashboard"""
    id: str
    farmer_name: str  # first_name + last_name
    farmer_email: str
    cooperative_code: Optional[str] = None
    cooperative_name: Optional[str] = None  # Name of the cooperative
    status: str = "Pending"
    created_at: datetime
    
    class Config:
        from_attributes = True


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
    """Login request - username can be email or phone number"""
    username: str
    password: str

    @field_validator('username')
    def validate_username(cls, v):
        if not v:
            raise ValueError("Username is required")
        if '@' in v:
            return v
        # Accept E.164 or local phone format
        if v.startswith('+'):
            allowed_prefixes = ['+254', '+255', '+256']
            if not any(v.startswith(prefix) for prefix in allowed_prefixes):
                raise ValueError("Phone number must be from Kenya (+254), Uganda (+256), or Tanzania (+255)")
        # Local format is accepted — normalization happens in authenticate_user
        return v


class LoginFormRequest(BaseModel):
    """Form-based login request - username can be email or phone number"""
    username: str
    password: str
    grant_type: str = "password"

    @field_validator('username')
    def validate_username(cls, v):
        if not v:
            raise ValueError("Username is required")
        if '@' in v:
            return v
        if v.startswith('+'):
            allowed_prefixes = ['+254', '+255', '+256']
            if not any(v.startswith(prefix) for prefix in allowed_prefixes):
                raise ValueError("Phone number must be from Kenya (+254), Uganda (+256), or Tanzania (+255)")
        # Local format accepted — normalization happens in authenticate_user
        return v


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
    id: str
    parcel_number: Optional[str] = None
    parcel_name: Optional[str] = None
    area_hectares: Optional[float] = None
    coffee_area_hectares: Optional[float] = None
    boundary_geojson: Optional[Dict[str, Any]] = None
    land_use_type: Optional[LandUseTypeEnum] = None
    ownership_type: Optional[str] = None
    soil_type: Optional[str] = None
    altitude_meters: Optional[float] = None
    slope_degrees: Optional[float] = None
    gps_accuracy_meters: Optional[float] = None
    mapping_date: Optional[datetime] = None
    estimated_coffee_plants: Optional[int] = None
    canopy_cover: Optional[str] = None
    irrigation_type: Optional[str] = None
    planting_method: Optional[str] = None
    practice_mixed_farming: Optional[int] = None
    other_crops: Optional[Any] = None
    ndvi_baseline: Optional[float] = None
    agroforestry_start_year: Optional[int] = None
    previous_land_use: Optional[str] = None
    programme_support: Optional[Any] = None
    verification_status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FarmCreate(BaseModel):
    """Schema for creating a farm - EUDR Compliant with Phase 2 fields"""
    farm_name: Optional[str] = None
    total_area_hectares: Optional[float] = None
    coffee_area_hectares: Optional[float] = None
    coffee_varieties: List[str] = []
    years_farming: Optional[int] = None
    average_annual_production_kg: Optional[float] = None
    land_use_type: Optional[str] = None
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    parcels: List[ParcelCreate] = []
    # Extra fields from the form (saved to parcel or user)
    farmer: Optional[Dict[str, Any]] = None
    land_parcel: Optional[Dict[str, Any]] = None
    sustainability: Optional[Dict[str, Any]] = None
    delivery: Optional[Dict[str, Any]] = None


class FarmResponse(BaseModel):
    """Farm response schema"""
    id: str
    owner_id: str
    farm_name: Optional[str] = None
    farm_code: Optional[str] = None
    total_area_hectares: Optional[float] = None
    coffee_area_hectares: Optional[float] = None
    coffee_varieties: List[str] = []
    land_use_type: Optional[LandUseTypeEnum] = None
    years_farming: Optional[int] = None
    average_annual_production_kg: Optional[float] = None
    deforestation_risk_score: Optional[float] = None
    compliance_status: Optional[str] = None
    verification_status: Optional[str] = None
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    parcels: List[ParcelResponse] = []
    created_at: datetime
    # Farmer identity (populated from owner in GET endpoints)
    farmer_name: Optional[str] = None
    farmer_phone: Optional[str] = None
    farmer_national_id: Optional[str] = None
    farmer_gender: Optional[str] = None
    farmer_location: Optional[str] = None
    coop_member_no: Optional[str] = None

    class Config:
        from_attributes = True


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
    id: str
    batch_number: str
    lot_number: Optional[str]
    cooperative_id: str
    crop_year: Optional[int]
    harvest_start_date: Optional[datetime]
    harvest_end_date: Optional[datetime]
    processing_method: str
    quality_grade: Optional[QualityGradeEnum]
    average_moisture: Optional[float]
    total_weight_kg: Optional[float]
    bag_count: Optional[int]
    warehouse_id: Optional[str]
    warehouse_location: Optional[str]
    origin_farms: Optional[dict]
    compliance_status: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    qr_code_path: Optional[str]
    traceability_hash: Optional[str]


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
    """Due Diligence Statement request with complete fields"""
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
    
    @field_validator('country_of_origin')
    def validate_country(cls, v):
        if v not in ['Kenya', 'Uganda', 'Ethiopia', 'Tanzania']:
            raise ValueError('Country of origin must be one of: Kenya, Uganda, Ethiopia, Tanzania')
        return v
    
    @field_validator('commodity_type')
    def validate_commodity(cls, v):
        if v not in ['Coffee', 'Tea', 'Cocoa', 'Palm Oil']:
            raise ValueError('Commodity type must be one of: Coffee, Tea, Cocoa, Palm Oil')
        return v
    
    @field_validator('unit')
    def validate_unit(cls, v):
        if v not in ['kg', 'tonnes', 'bags']:
            raise ValueError('Unit must be one of: kg, tonnes, bags')
        return v


class DDSResponse(BaseModel):
    """Due Diligence Statement response with detailed information"""
    id: int
    dds_number: str
    version: str
    operator_name: str
    operator_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_address: Optional[str] = None
    commodity_type: str
    hs_code: Optional[str] = None
    country_of_origin: str
    quantity: float
    unit: str
    supplier_name: Optional[str] = None
    supplier_country: Optional[str] = None
    first_placement_country: Optional[str] = None
    first_placement_date: Optional[datetime] = None
    risk_level: str
    submission_status: str
    dds_hash: Optional[str] = None
    signature: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


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


# ============== Cooperative Schemas ==============

class CooperativeUpdate(BaseModel):
    """Update cooperative request"""
    name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    county: Optional[str] = None
    district: Optional[str] = None
    subcounty: Optional[str] = None
    cooperative_type: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    establishment_date: Optional[datetime] = None
    contact_person: Optional[str] = None
    contact_person_phone: Optional[str] = None
    contact_person_email: Optional[str] = None
    legal_status: Optional[str] = None
    governing_document: Optional[str] = None
    is_active: Optional[bool] = None


class CooperativeMemberResponse(BaseModel):
    """Cooperative member response"""
    user_id: str
    cooperative_id: str
    membership_number: Optional[str]
    membership_type: str
    join_date: datetime
    is_active: bool
    is_primary: bool
    verification_status: str
    cooperative_role: Optional[str]


class CooperativeWithMembers(BaseModel):
    """Cooperative with members response"""
    id: str
    name: str
    code: Optional[str] = None
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: str = "Kenya"
    county: Optional[str] = None
    district: Optional[str] = None
    subcounty: Optional[str] = None
    ward: Optional[str] = None
    cooperative_type: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    establishment_date: Optional[datetime] = None
    member_count: int = 0
    farm_count: int = 0
    delivery_count: int = 0
    is_active: bool = True
    verification_status: str = "pending"
    members: List[CooperativeMemberResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    primary_officer_id: Optional[str] = None
    admin_name: Optional[str] = None
    verification_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON feature collection"""
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]


# ============== System Configuration Schemas ==============

class RequiredDocumentCreate(BaseModel):
    """Schema for creating a required document"""
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    document_type: Optional[str] = None
    is_required: bool = True
    sort_order: int = 0


class RequiredDocumentResponse(BaseModel):
    """Schema for required document response"""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    document_type: Optional[str] = None
    is_required: bool
    sort_order: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class SystemConfigResponse(BaseModel):
    """Schema for system config response"""
    id: str
    config_key: str
    config_value: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_public: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class SessionTimeoutUpdate(BaseModel):
    """Schema for updating session timeout"""
    timeout_minutes: int = Field(..., ge=5, le=1440, description="Session timeout in minutes (5 min to 24 hours)")


class EnvCredentialsUpdate(BaseModel):
    """Schema for updating environment credentials"""
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1)
    description: Optional[str] = None
    is_public: bool = False
