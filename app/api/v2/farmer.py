"""
Plotra Platform - Farmer API Endpoints (Tier 1)
GPS mapping, KYC, and farm management
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import get_current_user, require_farmer
from app.models.user import User, VerificationStatus
from app.models.farm import Farm, LandParcel, LandDocument, DocumentType, OwnershipType
FarmParcel = LandParcel
from app.api.schemas import (
    UserCreate, UserResponse, UserUpdate,
    FarmCreate, FarmResponse, ParcelCreate, ParcelResponse,
    DocumentUpload, DocumentResponse, MessageResponse,
    FarmerProfileSubmit
)

router = APIRouter(tags=["Tier 1: Farmer APIs"])


@router.get("/profile", response_model=UserResponse)
async def get_farmer_profile(
    current_user: User = Depends(require_farmer)
):
    """
    Get current farmer's profile.
    """
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_farmer_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Update farmer's profile information.
    """
    update_data = profile_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.post("/profile/submit", response_model=MessageResponse)
async def submit_farmer_profile(
    profile_data: FarmerProfileSubmit,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit the complete farmer profile (personal + farm + EUDR compliance).
    Creates or updates the farmer's farm record with all profile fields.
    Flags high-risk profiles for mandatory satellite review.
    """
    p = profile_data.personal
    f = profile_data.farm
    risks = profile_data.eudr_risks

    # Update user personal details from Section 1
    if p.first_name:
        current_user.first_name = p.first_name
    if p.last_name:
        current_user.last_name = p.last_name
    if p.phone:
        current_user.phone = p.phone
    if p.county:
        current_user.county = p.county
    if p.district:
        current_user.district = p.district
    if p.ward:
        current_user.ward = p.ward
    if p.address:
        current_user.address = p.address
    if p.national_id:
        current_user.national_id = p.national_id
    if p.dob:
        from datetime import datetime as dt
        try:
            current_user.date_of_birth = dt.fromisoformat(p.dob)
        except ValueError:
            pass

    # Get or create farm record
    result = await db.execute(
        select(Farm).where(Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        farm = Farm(owner_id=current_user.id)
        db.add(farm)
        await db.flush()

    # Section 2A — Land & parcel
    if f.farm_name:
        farm.farm_name = f.farm_name
    if f.farm_type:
        farm.farm_type = f.farm_type
    if f.land_reg_number:
        farm.land_registration_number = f.land_reg_number
    if f.total_area is not None:
        farm.total_area_hectares = f.total_area
    if f.soil_type:
        farm.soil_type = f.soil_type
    if f.terrain:
        farm.terrain = f.terrain

    # Section 2B — Coffee farming
    if f.coffee_variety:
        farm.coffee_varieties = f.coffee_variety
    if f.year_coffee_planted:
        farm.year_coffee_planted = f.year_coffee_planted
    if f.coffee_tree_count:
        farm.coffee_tree_count = f.coffee_tree_count
    if f.farm_status:
        farm.farm_status = f.farm_status
    if f.planting_method:
        farm.planting_method = f.planting_method
    farm.irrigation_used = f.irrigation_used == "yes" if f.irrigation_used else None
    if f.irrigation_type:
        farm.irrigation_type = f.irrigation_type
    if f.estimated_yield is not None:
        farm.average_annual_production_kg = f.estimated_yield

    # Section 2C — Mixed farming
    farm.mixed_farming = f.mixed_farming == "yes" if f.mixed_farming else None
    if f.coffee_percent is not None:
        try:
            farm.coffee_percent = float(f.coffee_percent)
        except (TypeError, ValueError):
            pass
    if f.other_crops:
        farm.other_crops = f.other_crops
    farm.livestock = f.livestock == "yes" if f.livestock else None
    if f.livestock_type:
        farm.livestock_type = f.livestock_type
    farm.crop_rotation = f.crop_rotation == "yes" if f.crop_rotation else None

    # Section 2D — Tree cover & deforestation
    farm.trees_planted_last5 = f.trees_planted_last5 == "yes" if f.trees_planted_last5 else None
    if f.tree_species:
        farm.tree_species = f.tree_species
    if f.tree_count:
        farm.tree_count = f.tree_count
    if f.tree_planting_reason:
        farm.tree_planting_reason = f.tree_planting_reason
    farm.trees_cleared = f.trees_cleared == "yes" if f.trees_cleared else None
    if f.reason_for_clearing:
        farm.reason_for_clearing = f.reason_for_clearing
    if f.current_canopy_cover:
        farm.current_canopy_cover = f.current_canopy_cover

    # Section 2E — Satellite consent
    if f.satellite_consent is not None:
        farm.satellite_consent = f.satellite_consent
    if f.historical_imagery_consent is not None:
        farm.historical_imagery_consent = f.historical_imagery_consent
    if f.monitoring_frequency:
        farm.monitoring_frequency = f.monitoring_frequency

    # Section 2F — Certifications
    if f.certifications:
        farm.certifications = f.certifications
    if f.cert_expiry_date:
        from datetime import datetime as dt
        try:
            farm.cert_expiry_date = dt.fromisoformat(f.cert_expiry_date)
        except ValueError:
            pass
    farm.previous_violations = f.previous_violations == "yes" if f.previous_violations else None
    if f.violation_details:
        farm.violation_details = f.violation_details

    # EUDR risk tracking
    risk_flags = risks.high_risk_flags if risks else []
    if farm.trees_cleared:
        if "trees_cleared" not in risk_flags:
            risk_flags.append("trees_cleared")
        farm.deforestation_risk_score = max(farm.deforestation_risk_score or 0, 80.0)
        farm.compliance_status = "High Risk - Satellite Review Required"
    farm.eudr_risk_flags = risk_flags

    # Mark profile as submitted
    farm.profile_submitted = True
    farm.profile_submitted_at = datetime.utcnow()

    await db.commit()
    return {"message": "Farmer profile submitted successfully", "success": True}


@router.post("/farm", response_model=FarmResponse, status_code=status.HTTP_201_CREATED)
async def create_farm(
    farm_data: FarmCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new farm with parcel boundaries.
    Farmers can create multiple parcels with GPS coordinates.
    """
    # Check if user already has a farm
    result = await db.execute(
        select(Farm).where(Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    existing_farm = result.scalar_one_or_none()
    
    if existing_farm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Farmer already has a farm. Please update existing farm."
        )
    
    # Create farm
    farm = Farm(
        owner_id=current_user.id,
        farm_name=farm_data.farm_name,
        total_area_hectares=farm_data.total_area_hectares,
        centroid_lat=farm_data.centroid_lat,
        centroid_lon=farm_data.centroid_lon,
        coffee_varieties=farm_data.coffee_varieties,
        years_farming=farm_data.years_farming,
        average_annual_production_kg=farm_data.average_annual_production_kg,
        compliance_status="Under Review"
    )
    
    db.add(farm)
    await db.flush()
    
    # Create parcels
    for parcel_data in farm_data.parcels:
        parcel = FarmParcel(
            farm_id=farm.id,
            parcel_number=parcel_data.parcel_number,
            parcel_name=parcel_data.parcel_name,
            boundary_geojson=parcel_data.boundary_geojson,
            area_hectares=parcel_data.area_hectares,
            gps_accuracy_meters=parcel_data.gps_accuracy_meters,
            mapping_device=parcel_data.mapping_device,
            land_use_type=parcel_data.land_use_type,
            coffee_area_hectares=parcel_data.coffee_area_hectares
        )
        db.add(parcel)
    
    await db.commit()
    await db.refresh(farm)
    
    return farm


@router.get("/farm", response_model=FarmResponse)
async def get_farm(
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current farmer's farm with all parcels.
    """
    result = await db.execute(
        select(Farm)
        .where(Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found"
        )
    
    return farm


@router.post("/farm/parcel", response_model=ParcelResponse, status_code=status.HTTP_201_CREATED)
async def add_parcel(
    parcel_data: ParcelCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new parcel to existing farm.
    """
    # Get farmer's farm
    result = await db.execute(
        select(Farm).where(Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found. Please create a farm first."
        )
    
    # Check parcel limit
    parcels_result = await db.execute(
        select(FarmParcel).where(FarmParcel.farm_id == farm.id)
    )
    existing_parcels = parcels_result.scalars().all()
    
    if len(existing_parcels) >= settings.geospatial.max_farm_polygons_per_farmer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum number of parcels ({settings.geospatial.max_farm_polygons_per_farmer}) reached"
        )
    
    # Create parcel
    parcel = FarmParcel(
        farm_id=farm.id,
        parcel_number=parcel_data.parcel_number,
        parcel_name=parcel_data.parcel_name,
        boundary_geojson=parcel_data.boundary_geojson,
        area_hectares=parcel_data.area_hectares,
        gps_accuracy_meters=parcel_data.gps_accuracy_meters,
        mapping_device=parcel_data.mapping_device,
        land_use_type=parcel_data.land_use_type,
        coffee_area_hectares=parcel_data.coffee_area_hectares
    )
    
    db.add(parcel)
    await db.commit()
    await db.refresh(parcel)
    
    return parcel


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_land_document(
    farm_id: int = Form(...),
    document_type: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    ownership_type: str = Form("customary"),
    issuing_authority: Optional[str] = Form(None),
    reference_number: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload land ownership document.
    Supports title deeds, lease agreements, and customary rights documents.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found"
        )
    
    # Read file content
    file_content = await file.read()

    # Check file size
    max_size_bytes = settings.storage.max_file_size_mb * 1024 * 1024
    if len(file_content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.storage.max_file_size_mb}MB"
        )

    # Generate checksum
    import hashlib
    checksum = hashlib.sha256(file_content).hexdigest()
    
    # TODO: Save file to storage and get path
    
    # Create document record
    document = LandDocument(
        farm_id=farm_id,
        document_type=DocumentType(document_type),
        title=title,
        description=description,
        file_name=file.filename,
        file_size_bytes=len(file_content),
        mime_type=file.content_type,
        checksum_sha256=checksum,
        ownership_type=OwnershipType(ownership_type),
        issuing_authority=issuing_authority,
        reference_number=reference_number,
        verification_status="pending"
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    return document


@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    farm_id: Optional[int] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all documents for farmer's farm(s).
    """
    query = select(LandDocument).join(Farm).where(Farm.owner_id == current_user.id)
    
    if farm_id:
        query = query.where(LandDocument.farm_id == farm_id)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return documents


@router.get("/stats")
async def get_farmer_stats(
    current_user: User = Depends(require_farmer)
):
    """
    Get farmer's investment and token statistics (MBT).
    """
    # In a real implementation, this would query the blockchain or a dedicated investment service
    return {
        "mbt_balance": "1,250.00",
        "staked_mbt": "1,000.00",
        "annual_interest": "75.00",
        "total_returns_5y": "450.00",
        "tvl": "12,500.00",
        "active_investments": 3,
        "staked_trend": "+12.5%",
        "interest_trend": "+8.2%",
        "returns_trend": "+15.0%"
    }


@router.get("/deliveries")
async def get_farmer_deliveries(
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all coffee deliveries for the current farmer.
    """
    from app.models.traceability import Delivery

    result = await db.execute(
        select(Farm).where(Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        return []

    deliveries_result = await db.execute(
        select(Delivery).where(Delivery.farm_id == farm.id).order_by(Delivery.created_at.desc())
    )
    return deliveries_result.scalars().all()


# ============== Parcel CRUD with farmId in path ==============

@router.get("/farm/{farm_id}/parcels", response_model=List[ParcelResponse])
async def get_parcels(
    farm_id: int,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get all parcels for a specific farm."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    parcels_result = await db.execute(
        select(FarmParcel).where(FarmParcel.farm_id == farm_id)
    )
    return parcels_result.scalars().all()


@router.post("/farm/{farm_id}/parcels", response_model=ParcelResponse, status_code=status.HTTP_201_CREATED)
async def add_parcel_to_farm(
    farm_id: int,
    parcel_data: ParcelCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Add a new parcel to a farm (path-based version)."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    existing = await db.execute(select(FarmParcel).where(FarmParcel.farm_id == farm_id))
    existing_count = len(existing.scalars().all())
    if existing_count >= settings.geospatial.max_farm_polygons_per_farmer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Maximum parcels ({settings.geospatial.max_farm_polygons_per_farmer}) reached")

    parcel = FarmParcel(
        farm_id=farm_id,
        parcel_number=parcel_data.parcel_number,
        parcel_name=parcel_data.parcel_name,
        boundary_geojson=parcel_data.boundary_geojson,
        area_hectares=parcel_data.area_hectares,
        gps_accuracy_meters=parcel_data.gps_accuracy_meters,
        mapping_device=parcel_data.mapping_device,
        land_use_type=parcel_data.land_use_type,
        coffee_area_hectares=parcel_data.coffee_area_hectares
    )
    db.add(parcel)
    await db.commit()
    await db.refresh(parcel)
    return parcel


@router.get("/farm/{farm_id}/parcels/{parcel_id}", response_model=ParcelResponse)
async def get_parcel(
    farm_id: int,
    parcel_id: int,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific parcel."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    parcel_result = await db.execute(
        select(FarmParcel).where(FarmParcel.id == parcel_id, FarmParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    if not parcel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
    return parcel


@router.put("/farm/{farm_id}/parcels/{parcel_id}", response_model=ParcelResponse)
async def update_parcel(
    farm_id: int,
    parcel_id: int,
    parcel_data: ParcelCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Update a parcel."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    parcel_result = await db.execute(
        select(FarmParcel).where(FarmParcel.id == parcel_id, FarmParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    if not parcel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    update_data = parcel_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(parcel, field):
            setattr(parcel, field, value)
    await db.commit()
    await db.refresh(parcel)
    return parcel


@router.delete("/farm/{farm_id}/parcels/{parcel_id}", response_model=MessageResponse)
async def delete_parcel(
    farm_id: int,
    parcel_id: int,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Delete a parcel."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    parcel_result = await db.execute(
        select(FarmParcel).where(FarmParcel.id == parcel_id, FarmParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    if not parcel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    await db.delete(parcel)
    await db.commit()
    return {"message": "Parcel deleted successfully"}
