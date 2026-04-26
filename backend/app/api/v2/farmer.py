"""
Plotra Platform - Farmer API Endpoints (Tier 1)
GPS mapping, KYC, and farm management
"""
import json
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user, require_farmer
from app.models.user import User, VerificationStatus, CooperativeMember
from app.models.farm import Farm, LandParcel, LandDocument, DocumentType, OwnershipType
from app.models.traceability import Delivery
from app.models.payments import PaymentEscrow, PayoutStatus
from app.api.schemas import (
    UserCreate, UserResponse, UserUpdate,
    FarmCreate, FarmResponse, ParcelCreate, ParcelResponse,
    DocumentUpload, DocumentResponse, DeliveryResponse, MessageResponse
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


def _farm_to_dict(farm: Farm) -> dict:
    """Serialize a Farm ORM object to a dict including owner/farmer details."""
    owner = farm.owner
    farmer_name = None
    farmer_phone = None
    farmer_national_id = None
    farmer_gender = None
    farmer_location = None
    coop_member_no = None
    if owner:
        farmer_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip() or None
        farmer_phone = owner.phone or getattr(owner, 'phone_number', None)
        farmer_national_id = getattr(owner, 'national_id', None)
        farmer_gender = getattr(owner, 'gender', None)
        farmer_location = getattr(owner, 'subcounty', None) or getattr(owner, 'county', None) or getattr(owner, 'district', None)
        coop_member_no = getattr(owner, 'cooperative_member_no', None) or getattr(owner, 'membership_number', None)

    parcels = []
    for p in (farm.parcels or []):
        parcels.append({
            "id": p.id,
            "parcel_number": str(p.parcel_number) if p.parcel_number else None,
            "parcel_name": p.parcel_name,
            "area_hectares": p.area_hectares,
            "coffee_area_hectares": p.coffee_area_hectares,
            "boundary_geojson": p.boundary_geojson,
            "land_use_type": p.land_use_type.value if p.land_use_type else None,
            "ownership_type": p.ownership_type.value if p.ownership_type else None,
            "soil_type": p.soil_type.value if p.soil_type else None,
            "altitude_meters": p.altitude_meters,
            "slope_degrees": p.slope_degrees,
            "gps_accuracy_meters": p.gps_accuracy_meters,
            "mapping_date": p.mapping_date.isoformat() if p.mapping_date else None,
            "estimated_coffee_plants": p.estimated_coffee_plants,
            "canopy_cover": p.canopy_cover.value if p.canopy_cover else None,
            "irrigation_type": p.irrigation_type.value if p.irrigation_type else None,
            "planting_method": p.planting_method.value if p.planting_method else None,
            "practice_mixed_farming": p.practice_mixed_farming,
            "other_crops": p.other_crops,
            "ndvi_baseline": p.ndvi_baseline,
            "agroforestry_start_year": p.agroforestry_start_year,
            "previous_land_use": p.previous_land_use,
            "programme_support": p.programme_support,
            "verification_status": p.verification_status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return {
        "id": farm.id,
        "owner_id": farm.owner_id,
        "farm_name": farm.farm_name,
        "farm_code": farm.farm_code,
        "total_area_hectares": farm.total_area_hectares,
        "coffee_area_hectares": farm.coffee_area_hectares,
        "coffee_varieties": farm.coffee_varieties or [],
        "land_use_type": farm.land_use_type.value if farm.land_use_type else None,
        "years_farming": farm.years_farming,
        "average_annual_production_kg": farm.average_annual_production_kg,
        "deforestation_risk_score": farm.deforestation_risk_score,
        "compliance_status": farm.compliance_status,
        "verification_status": farm.verification_status,
        "centroid_lat": farm.centroid_lat,
        "centroid_lon": farm.centroid_lon,
        "parcels": parcels,
        "created_at": farm.created_at.isoformat() if farm.created_at else None,
        "farmer_name": farmer_name,
        "farmer_phone": farmer_phone,
        "farmer_national_id": farmer_national_id,
        "farmer_gender": farmer_gender,
        "farmer_location": farmer_location,
        "coop_member_no": coop_member_no,
    }


@router.post("/farm", status_code=status.HTTP_201_CREATED)
async def create_farm(
    farm_data: FarmCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Create a new farm with parcel boundaries."""
    if getattr(current_user, 'verification_status', None) != VerificationStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account must be fully verified by your Cooperative and Kipawa admin before you can register a farm."
        )
    has_polygon = bool(farm_data.parcels and any(p.boundary_geojson for p in farm_data.parcels))
    initial_status = "pending" if has_polygon else "draft"

    # Resolve land_use_type
    from app.models.farm import LandUseType
    land_use_type = None
    if farm_data.land_use_type:
        try:
            land_use_type = LandUseType(farm_data.land_use_type.lower())
        except ValueError:
            land_use_type = LandUseType.AGROFORESTRY

    farm = Farm(
        owner_id=current_user.id,
        farm_name=farm_data.farm_name,
        total_area_hectares=farm_data.total_area_hectares,
        coffee_area_hectares=farm_data.coffee_area_hectares,
        coffee_varieties=farm_data.coffee_varieties,
        years_farming=farm_data.years_farming,
        average_annual_production_kg=farm_data.average_annual_production_kg,
        land_use_type=land_use_type,
        compliance_status="Under Review",
        verification_status=initial_status,
        centroid_lat=farm_data.centroid_lat,
        centroid_lon=farm_data.centroid_lon,
    )
    db.add(farm)
    await db.flush()

    # Tag farm with cooperative_id from farmer's CooperativeMember record
    member_res = await db.execute(
        select(CooperativeMember).where(
            CooperativeMember.user_id == current_user.id,
            CooperativeMember.is_active == True
        )
    )
    membership = member_res.scalar_one_or_none()
    if membership:
        farm.cooperative_id = str(membership.cooperative_id)

    # Apply extra fields from form sub-objects
    sustainability = farm_data.sustainability or {}
    land_parcel_extra = farm_data.land_parcel or {}

    # Update user with any new farmer details
    farmer_info = farm_data.farmer or {}
    if farmer_info.get('cooperative_member_no') and hasattr(current_user, 'cooperative_member_no'):
        current_user.cooperative_member_no = farmer_info['cooperative_member_no']

    for parcel_data in farm_data.parcels:
        geojson_str = json.dumps(parcel_data.boundary_geojson)
        boundary_geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geojson_str), 4326)

        # Resolve ownership type
        ownership_raw = land_parcel_extra.get('ownership_type') or ''
        ownership = None
        if ownership_raw:
            try:
                ownership = OwnershipType(ownership_raw.lower())
            except ValueError:
                pass

        parcel = LandParcel(
            farm_id=farm.id,
            parcel_number=str(parcel_data.parcel_number),
            parcel_name=parcel_data.parcel_name or farm_data.farm_name,
            boundary_geojson=parcel_data.boundary_geojson,
            boundary_geometry=boundary_geom,
            area_hectares=parcel_data.area_hectares,
            gps_accuracy_meters=parcel_data.gps_accuracy_meters,
            mapping_device=parcel_data.mapping_device,
            land_use_type=parcel_data.land_use_type,
            coffee_area_hectares=parcel_data.coffee_area_hectares,
            ownership_type=ownership,
            agroforestry_start_year=sustainability.get('agroforestry_start_year'),
            previous_land_use=sustainability.get('previous_land_use'),
            programme_support=sustainability.get('programme_support'),
        )
        db.add(parcel)

    await db.commit()

    from sqlalchemy.orm import selectinload
    result2 = await db.execute(
        select(Farm).options(selectinload(Farm.parcels), selectinload(Farm.owner)).where(Farm.id == farm.id)
    )
    farm = result2.scalar_one()
    return _farm_to_dict(farm)


@router.get("/farm")
async def get_farms(
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get all farms belonging to the current farmer."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Farm)
        .options(selectinload(Farm.parcels), selectinload(Farm.owner))
        .where(Farm.owner_id == current_user.id, Farm.deleted_at == None)
        .order_by(Farm.created_at.desc())
    )
    farms = result.scalars().all()
    return [_farm_to_dict(f) for f in farms]


@router.get("/farm/{farm_id}")
async def get_farm_by_id(
    farm_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Farm).options(selectinload(Farm.parcels), selectinload(Farm.owner))
        .where(Farm.id == farm_id, Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return _farm_to_dict(farm)


@router.patch("/farm/{farm_id}", response_model=FarmResponse)
async def update_farm(
    farm_id: str,
    payload: dict,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Update farm fields and/or polygon boundary."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Farm).options(selectinload(Farm.parcels))
        .where(Farm.id == farm_id, Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    # Update simple farm fields
    editable_fields = [
        "farm_name", "total_area_hectares", "coffee_area_hectares",
        "coffee_varieties", "years_farming", "average_annual_production_kg",
        "land_use_type", "compliance_status", "notes",
    ]
    for field in editable_fields:
        if field in payload and payload[field] is not None:
            setattr(farm, field, payload[field])

    # Handle polygon update
    gps_points = payload.get("gps_points", [])
    boundary_geojson = payload.get("boundary_geojson")
    area_ha = payload.get("area_hectares") or payload.get("total_area_hectares")

    if not boundary_geojson and gps_points and len(gps_points) >= 3:
        coords = [[p["lon"], p["lat"]] for p in gps_points]
        # Ensure at least 4 points for closed polygon (first != last)
        if len(coords) < 4:
            coords.append(coords[0])
        elif coords[0][0] != coords[-1][0] or coords[0][1] != coords[-1][1]:
            coords.append(coords[0])
        boundary_geojson = {"type": "Polygon", "coordinates": [coords]}

    if boundary_geojson:
        if farm.parcels:
            parcel = farm.parcels[0]
            parcel.boundary_geojson = boundary_geojson
            if area_ha:
                parcel.area_hectares = area_ha
            parcel.verification_status = "pending"
        else:
            parcel = LandParcel(
                farm_id=farm.id,
                parcel_number=f"P-{farm_id[:8]}",
                boundary_geojson=boundary_geojson,
                area_hectares=area_ha,
                verification_status="pending"
            )
            db.add(parcel)
        farm.verification_status = "pending"
        if area_ha:
            farm.total_area_hectares = area_ha

    await db.commit()
    result2 = await db.execute(
        select(Farm).options(selectinload(Farm.parcels)).where(Farm.id == farm.id)
    )
    return result2.scalar_one()


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
        select(LandParcel).where(LandParcel.farm_id == farm.id)
    )
    existing_parcels = parcels_result.scalars().all()
    
    if len(existing_parcels) >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum number of parcels (10) reached"
        )
    
    # Create parcel
    parcel = LandParcel(
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


@router.get("/farm/{farm_id}/parcels", response_model=List[ParcelResponse])
async def get_farm_parcels(
    farm_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """List all parcels for a specific farm."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    parcels_result = await db.execute(
        select(LandParcel).where(LandParcel.farm_id == farm_id, LandParcel.deleted_at == None)
    )
    return parcels_result.scalars().all()


@router.post("/farm/{farm_id}/parcels", response_model=ParcelResponse, status_code=status.HTTP_201_CREATED)
async def add_parcel_to_farm(
    farm_id: str,
    parcel_data: ParcelCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Add a new parcel to a specific farm."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    parcels_result = await db.execute(
        select(func.count()).select_from(LandParcel).where(LandParcel.farm_id == farm_id)
    )
    if parcels_result.scalar() >= 10:
        raise HTTPException(status_code=400, detail="Maximum number of parcels (10) reached")

    parcel = LandParcel(
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
    farm_id: str,
    parcel_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Get a single parcel by ID."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Farm not found")

    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@router.put("/farm/{farm_id}/parcels/{parcel_id}", response_model=ParcelResponse)
async def update_parcel(
    farm_id: str,
    parcel_id: str,
    parcel_data: dict,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Update parcel with EUDR compliance fields."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    for field, value in parcel_data.items():
        if hasattr(parcel, field):
            setattr(parcel, field, value)

    await db.commit()
    await db.refresh(parcel)
    return parcel


@router.delete("/farm/{farm_id}/parcels/{parcel_id}")
async def delete_parcel(
    farm_id: str,
    parcel_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """Delete a parcel from the farm."""
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Farm not found")

    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    await db.delete(parcel)
    await db.commit()
    return {"message": "Parcel deleted successfully"}


@router.post("/farm/{farm_id}/satellite-analysis", response_model=dict)
async def request_satellite_analysis(
    farm_id: str,
    parcel_ids: Optional[List[str]] = None,
    acquisition_date: Optional[datetime] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Request satellite analysis for farm parcels.
    If no parcel_ids specified, analyzes all parcels in the farm.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Get parcels to analyze
    if parcel_ids:
        parcels_result = await db.execute(
            select(LandParcel).where(
                LandParcel.farm_id == farm_id,
                LandParcel.id.in_(parcel_ids)
            )
        )
    else:
        parcels_result = await db.execute(
            select(LandParcel).where(LandParcel.farm_id == farm_id)
        )

    parcels = parcels_result.scalars().all()

    if not parcels:
        raise HTTPException(status_code=404, detail="No parcels found")

    # Import satellite engine here to avoid circular imports
    from app.services.satellite_analysis import satellite_engine

    # Perform analysis
    analysis_results = await satellite_engine.analyze_parcels_batch(parcels, acquisition_date)

    # Store results in database
    from app.models.satellite import SatelliteObservation, AnalysisStatus

    successful_analyses = []
    for i, result in enumerate(analysis_results):
        if result.get('status') == 'completed':
            parcel = parcels[i]

            # Create satellite observation record
            observation = SatelliteObservation(
                parcel_id=parcel.id,
                observation_id=result['analysis_id'],
                satellite_source=result.get('satellite_source', 'SIMULATION'),
                acquisition_date=acquisition_date or datetime.utcnow(),
                processing_date=datetime.utcnow(),
                status=AnalysisStatus.COMPLETED,
                ndvi_mean=result.get('ndvi_mean'),
                ndvi_min=result.get('ndvi_min'),
                ndvi_max=result.get('ndvi_max'),
                ndvi_std_dev=result.get('ndvi_std_dev'),
                evi=result.get('evi'),
                savi=result.get('savi'),
                ndwi=result.get('ndwi'),
                lai=result.get('lai'),
                canopy_cover_percentage=result.get('canopy_cover_percentage'),
                tree_density=result.get('tree_density'),
                biomass_tons_hectare=result.get('biomass_tons_hectare'),
                land_cover_type=result.get('land_cover_type'),
                land_cover_confidence=result.get('land_cover_confidence')
            )

            db.add(observation)
            successful_analyses.append(result)

            # Update parcel with latest analysis data
            parcel.ndvi_baseline = result.get('ndvi_mean')
            parcel.canopy_density = result.get('canopy_cover_percentage')
            parcel.biomass_tons = result.get('biomass_tons_hectare')

    # Update farm's last analysis timestamp
    farm.last_satellite_analysis = datetime.utcnow()

    await db.commit()

    return {
        "message": f"Analysis completed for {len(successful_analyses)} parcels",
        "results": analysis_results,
        "farm_id": farm_id
    }


@router.get("/farm/{farm_id}/satellite-history")
async def get_satellite_history(
    farm_id: str,
    parcel_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical satellite analysis data for farm parcels.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.satellite import SatelliteObservation

    # Build query
    query = select(SatelliteObservation).join(LandParcel).where(LandParcel.farm_id == farm_id)

    if parcel_id:
        query = query.where(SatelliteObservation.parcel_id == parcel_id)

    query = query.order_by(SatelliteObservation.acquisition_date.desc()).limit(limit)

    observations_result = await db.execute(query)
    observations = observations_result.scalars().all()

    return [
        {
            "id": obs.id,
            "parcel_id": obs.parcel_id,
            "observation_id": obs.observation_id,
            "satellite_source": obs.satellite_source,
            "acquisition_date": obs.acquisition_date.isoformat(),
            "processing_date": obs.processing_date.isoformat(),
            "status": obs.status.value,
            "ndvi_mean": obs.ndvi_mean,
            "ndvi_min": obs.ndvi_min,
            "ndvi_max": obs.ndvi_max,
            "canopy_cover_percentage": obs.canopy_cover_percentage,
            "biomass_tons_hectare": obs.biomass_tons_hectare,
            "land_cover_type": obs.land_cover_type,
            "risk_score": getattr(obs, 'risk_score', None)
        }
        for obs in observations
    ]


@router.get("/farm/{farm_id}/satellite-imagery")
async def get_satellite_imagery_url(
    farm_id: str,
    parcel_id: Optional[int] = None,
    image_type: str = "ndvi",  # "ndvi", "true_color", "false_color"
    date: Optional[str] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get satellite imagery URL for visualization.
    Returns a URL that can be used to display satellite imagery on a map.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Get parcel boundary for the request
    if parcel_id:
        parcel_result = await db.execute(
            select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.farm_id == farm_id)
        )
        parcel = parcel_result.scalar_one_or_none()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        boundary = parcel.boundary_geojson
    else:
        # Use farm centroid or first parcel
        parcels_result = await db.execute(
            select(LandParcel).where(LandParcel.farm_id == farm_id).limit(1)
        )
        parcel = parcels_result.scalar_one_or_none()
        boundary = parcel.boundary_geojson if parcel else None

    if not boundary:
        raise HTTPException(status_code=400, detail="No boundary data available")

    # Parse date
    acquisition_date = None
    if date:
        try:
            acquisition_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
        except:
            acquisition_date = datetime.utcnow()

    # Generate imagery URL based on available APIs
    # For now, return a placeholder - in production this would integrate with
    # Sentinel Hub, Planet, or Google Earth Engine
    imagery_url = f"/api/v2/farmer/farm/{farm_id}/satellite-imagery/tile/{image_type}"

    if parcel_id:
        imagery_url += f"?parcel_id={parcel_id}"
    if acquisition_date:
        imagery_url += f"&date={acquisition_date.isoformat()}"

    return {
        "imagery_url": imagery_url,
        "image_type": image_type,
        "boundary": boundary,
        "acquisition_date": acquisition_date.isoformat() if acquisition_date else None,
        "note": "Imagery URL provided for map integration - actual implementation requires satellite API integration"
    }


@router.get("/farm/{farm_id}/calculations")
async def get_farm_calculations(
    farm_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get calculated metrics for the entire farm.
    Includes area totals, yield estimates, carbon calculations, etc.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Get all parcels
    parcels_result = await db.execute(
        select(LandParcel).where(LandParcel.farm_id == farm_id)
    )
    parcels = parcels_result.scalars().all()

    # Calculate farm-wide metrics
    total_area = sum(p.area_hectares or 0 for p in parcels)
    coffee_area = sum(p.coffee_area_hectares or 0 for p in parcels)

    # Average NDVI across all parcels
    ndvi_values = [p.ndvi_baseline for p in parcels if p.ndvi_baseline is not None]
    avg_ndvi = sum(ndvi_values) / len(ndvi_values) if ndvi_values else None

    # Biomass calculations
    biomass_values = [p.biomass_tons for p in parcels if p.biomass_tons is not None]
    total_biomass = sum(biomass_values) if biomass_values else None

    # Carbon calculations (rough estimate: biomass * 0.5 for carbon content)
    carbon_stored = total_biomass * 0.5 if total_biomass else None

    # Yield estimation (rough calculation based on NDVI and area)
    # Typical coffee yield is 0.5-2 tons/ha/year depending on conditions
    base_yield_per_ha = 1.0  # tons/ha/year
    yield_multiplier = (avg_ndvi - 0.3) / 0.4 if avg_ndvi else 1.0  # NDVI adjustment
    yield_multiplier = max(0.3, min(2.0, yield_multiplier))
    estimated_yearly_yield = coffee_area * base_yield_per_ha * yield_multiplier

    return {
        "farm_id": farm_id,
        "total_area_hectares": round(total_area, 2),
        "coffee_area_hectares": round(coffee_area, 2),
        "non_coffee_area_hectares": round(total_area - coffee_area, 2),
        "average_ndvi": round(avg_ndvi, 3) if avg_ndvi else None,
        "total_biomass_tons": round(total_biomass, 2) if total_biomass else None,
        "carbon_stored_tons": round(carbon_stored, 2) if carbon_stored else None,
        "estimated_yearly_yield_tons": round(estimated_yearly_yield, 2),
        "yield_per_hectare": round(estimated_yearly_yield / coffee_area, 2) if coffee_area > 0 else 0,
        "parcel_count": len(parcels),
        "last_analysis_date": farm.last_satellite_analysis.isoformat() if farm.last_satellite_analysis else None
    }


# Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()
    
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    
    # Find parcel
    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.farm_id == farm.id)
    )
    parcel = parcel_result.scalar_one_or_none()
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    # Map of allowed fields for EUDR compliance
    field_mapping = {
        'parcel_name': 'parcel_name',
        'land_registration_number': 'land_registration_number',
        'altitude_meters': 'altitude_meters',
        'soil_type': 'soil_type',
        'terrain_slope': 'terrain_slope',
        'year_coffee_first_planted': 'year_coffee_first_planted',
        'estimated_coffee_plants': 'estimated_coffee_plants',
        'farm_status': 'farm_status',
        'planting_method': 'planting_method',
        'irrigation_type': 'irrigation_type',
        'coffee_area_hectares': 'coffee_area_hectares',
        'practice_mixed_farming': 'practice_mixed_farming',
        'other_crops': 'other_crops',
        'livestock_on_parcel': 'livestock_on_parcel',
        'livestock_type': 'livestock_type',
        'coffee_percentage': 'coffee_percentage',
        'crop_rotation_practiced': 'crop_rotation_practiced',
        'trees_planted_last_5_years': 'trees_planted_last_5_years',
        'tree_species_planted': 'tree_species_planted',
        'trees_planted_count': 'trees_planted_count',
        'reason_for_planting': 'reason_for_planting',
        'trees_cleared_last_5_years': 'trees_cleared_last_5_years',
        'reason_for_clearing': 'reason_for_clearing',
        'canopy_cover': 'canopy_cover',
        'consent_satellite_monitoring': 'consent_satellite_monitoring',
        'consent_historical_imagery': 'consent_historical_imagery',
        'monitoring_frequency': 'monitoring_frequency',
        'certifications': 'certifications',
        'certificate_expiry_date': 'certificate_expiry_date',
        'previously_flagged': 'previously_flagged',
        'cooperative_registration_number': 'cooperative_registration_number',
        'ownership_type': 'ownership_type'
    }
    
    for api_field, model_field in field_mapping.items():
        if api_field in parcel_data and parcel_data[api_field] is not None:
            setattr(parcel, model_field, parcel_data[api_field])
    
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
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get farmer's investment and token statistics (MBT).

    The values are derived from payment escrow records in the database.
    """
    # Get farmer's farms (for compliance info — pick first one)
    farm_result = await db.execute(
        select(Farm).where(Farm.owner_id == current_user.id, Farm.deleted_at == None).limit(1)
    )
    farm = farm_result.scalars().first()

    compliance_status = getattr(farm, "compliance_status", None) if farm else None

    def map_compliance_score(status: Optional[str]) -> float:
        if not status:
            return 0.0
        mapping = {
            "compliant": 95.0,
            "under_review": 65.0,
            "pending_documents": 50.0,
            "requires_action": 30.0,
            "non_compliant": 10.0,
        }
        return mapping.get(status.lower(), 0.0)

    compliance_score = map_compliance_score(compliance_status)

    now = datetime.utcnow()
    last_30_days = now - timedelta(days=30)
    prev_30_days = now - timedelta(days=60)
    last_year = now - timedelta(days=365)
    prev_year = now - timedelta(days=730)

    # Wallet balance = total released payments
    released_total = (await db.execute(
        select(func.coalesce(func.sum(PaymentEscrow.amount), 0.0))
        .where(
            PaymentEscrow.payee_id == current_user.id,
            PaymentEscrow.status == PayoutStatus.RELEASED
        )
    )).scalar() or 0.0

    # Staked = pending/escrow/conditional
    staked_total = (await db.execute(
        select(func.coalesce(func.sum(PaymentEscrow.amount), 0.0))
        .where(
            PaymentEscrow.payee_id == current_user.id,
            PaymentEscrow.status.in_([PayoutStatus.PENDING, PayoutStatus.ESCROW, PayoutStatus.CONDITIONAL])
        )
    )).scalar() or 0.0

    # Annual interest: simple approximation based on last 12 months released payments
    released_last_year = (await db.execute(
        select(func.coalesce(func.sum(PaymentEscrow.amount), 0.0))
        .where(
            PaymentEscrow.payee_id == current_user.id,
            PaymentEscrow.status == PayoutStatus.RELEASED,
            PaymentEscrow.release_date >= last_year
        )
    )).scalar() or 0.0

    annual_interest = round(released_last_year * 0.05, 2)

    # Trends: compare last 30 days to previous 30 days
    released_last_30 = (await db.execute(
        select(func.coalesce(func.sum(PaymentEscrow.amount), 0.0))
        .where(
            PaymentEscrow.payee_id == current_user.id,
            PaymentEscrow.status == PayoutStatus.RELEASED,
            PaymentEscrow.release_date >= last_30_days
        )
    )).scalar() or 0.0

    released_prev_30 = (await db.execute(
        select(func.coalesce(func.sum(PaymentEscrow.amount), 0.0))
        .where(
            PaymentEscrow.payee_id == current_user.id,
            PaymentEscrow.status == PayoutStatus.RELEASED,
            PaymentEscrow.release_date >= prev_30_days,
            PaymentEscrow.release_date < last_30_days
        )
    )).scalar() or 0.0

    def pct_change(current: float, previous: float) -> str:
        if previous <= 0:
            return "+0%"
        return f"{(current - previous) / previous * 100:+.1f}%"

    returns_trend = pct_change(released_last_30, released_prev_30)

    prev_year_released = (await db.execute(
        select(func.coalesce(func.sum(PaymentEscrow.amount), 0.0))
        .where(
            PaymentEscrow.payee_id == current_user.id,
            PaymentEscrow.status == PayoutStatus.RELEASED,
            PaymentEscrow.release_date >= prev_year,
            PaymentEscrow.release_date < last_year
        )
    )).scalar() or 0.0

    prev_year_interest = round(prev_year_released * 0.05, 2)
    interest_trend = "+0%"
    if prev_year_interest > 0:
        interest_trend = pct_change(annual_interest, prev_year_interest)

    total_returns_5y = released_total
    tvl = released_total + staked_total

    return {
        "mbt_balance": f"{released_total:.2f}",
        "staked_mbt": f"{staked_total:.2f}",
        "annual_interest": f"{annual_interest:.2f}",
        "total_returns_5y": f"{total_returns_5y:.2f}",
        "tvl": f"{tvl:.2f}",
        "active_investments": 0,
        "staked_trend": "+0%",
        "interest_trend": interest_trend,
        "returns_trend": returns_trend,
        "compliance_score": compliance_score,
        "compliance_status": compliance_status
    }


@router.get("/notifications")
async def get_farmer_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notifications for the current user."""
    from app.models.notification import Notification
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifs = result.scalars().all()
    return [
        {
            "id": n.id, "title": n.title, "message": n.message,
            "type": n.type, "is_read": n.is_read,
            "reference_id": n.reference_id, "reference_type": n.reference_type,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]


@router.patch("/notifications/{notif_id}/read")
async def mark_notification_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models.notification import Notification
    result = await db.execute(
        select(Notification).where(Notification.id == notif_id, Notification.recipient_id == current_user.id)
    )
    n = result.scalar_one_or_none()
    if n:
        n.is_read = True
        await db.commit()
    return {"ok": True}


@router.get("/deliveries", response_model=List[DeliveryResponse])
async def get_farmer_deliveries(
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all coffee deliveries for the current farmer.
    """
    # Get all farmer's farms
    farms_result = await db.execute(
        select(Farm.id).where(Farm.owner_id == current_user.id, Farm.deleted_at == None)
    )
    farm_ids = [row[0] for row in farms_result.all()]

    if not farm_ids:
        return []

    # Get deliveries for all farms
    deliveries_result = await db.execute(
        select(Delivery).where(Delivery.farm_id.in_(farm_ids)).order_by(Delivery.created_at.desc())
    )
    return deliveries_result.scalars().all()


@router.post("/farm/{farm_id}/parcel/{parcel_id}/trees", response_model=dict)
async def add_tree(
    farm_id: str,
    parcel_id: str,
    tree_data: dict,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a tree to a parcel.
    Supports GPS capture and manual entry.
    """
    # Verify farm and parcel belong to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # Validate required fields
    if not tree_data.get('latitude') or not tree_data.get('longitude'):
        raise HTTPException(status_code=400, detail="GPS coordinates are required")

    from app.models.farm import Tree, TreeSpecies

    # Create tree
    tree = Tree(
        parcel_id=parcel_id,
        tree_number=tree_data.get('tree_number', f"T{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"),
        tree_type=TreeSpecies(tree_data.get('tree_type', 'other')),
        latitude=tree_data['latitude'],
        longitude=tree_data['longitude'],
        altitude_meters=tree_data.get('altitude_meters'),
        accuracy_meters=tree_data.get('accuracy_meters'),
        height_meters=tree_data.get('height_meters'),
        canopy_diameter_meters=tree_data.get('canopy_diameter_meters'),
        trunk_diameter_cm=tree_data.get('trunk_diameter_cm'),
        health_status=tree_data.get('health_status', 'healthy'),
        planted_date=datetime.fromisoformat(tree_data['planted_date']) if tree_data.get('planted_date') else None,
        economic_value_usd=tree_data.get('economic_value_usd'),
        timber_value_usd=tree_data.get('timber_value_usd'),
        fruit_yield_kg_year=tree_data.get('fruit_yield_kg_year'),
        carbon_sequestered_kg_year=tree_data.get('carbon_sequestered_kg_year'),
        biodiversity_score=tree_data.get('biodiversity_score'),
        notes=tree_data.get('notes'),
        is_native_species=tree_data.get('is_native_species', 0),
        provides_shade=tree_data.get('provides_shade', 0),
        is_fruit_bearing=tree_data.get('is_fruit_bearing', 0)
    )

    db.add(tree)
    await db.commit()
    await db.refresh(tree)

    return {
        "id": tree.id,
        "tree_number": tree.tree_number,
        "status": "created",
        "parcel_id": parcel_id
    }


@router.get("/farm/{farm_id}/parcel/{parcel_id}/trees")
async def get_parcel_trees(
    farm_id: str,
    parcel_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all trees in a parcel.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.farm import Tree

    trees_result = await db.execute(
        select(Tree).where(Tree.parcel_id == parcel_id)
    )
    trees = trees_result.scalars().all()

    return [
        {
            "id": tree.id,
            "tree_number": tree.tree_number,
            "tree_type": tree.tree_type.value if tree.tree_type else "other",
            "latitude": tree.latitude,
            "longitude": tree.longitude,
            "health_status": tree.health_status,
            "height_meters": tree.height_meters,
            "canopy_diameter_meters": tree.canopy_diameter_meters,
            "age_years": tree.get_age_years(),
            "economic_value_usd": tree.economic_value_usd,
            "carbon_sequestered_kg_year": tree.carbon_sequestered_kg_year,
            "provides_shade": bool(tree.provides_shade),
            "is_fruit_bearing": bool(tree.is_fruit_bearing),
            "planted_date": tree.planted_date.isoformat() if tree.planted_date else None
        }
        for tree in trees
    ]


@router.put("/farm/{farm_id}/parcel/{parcel_id}/trees/{tree_id}")
async def update_tree(
    farm_id: str,
    parcel_id: str,
    tree_id: str,
    tree_data: dict,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Update tree information.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.farm import Tree

    tree = await db.get(Tree, tree_id)
    if not tree or tree.parcel_id != parcel_id:
        raise HTTPException(status_code=404, detail="Tree not found")

    # Update tree fields
    for field, value in tree_data.items():
        if hasattr(tree, field):
            if field == 'planted_date' and value:
                value = datetime.fromisoformat(value)
            setattr(tree, field, value)

    tree.last_health_check = datetime.utcnow()
    await db.commit()
    await db.refresh(tree)

    return {"id": tree.id, "status": "updated"}


@router.delete("/farm/{farm_id}/parcel/{parcel_id}/trees/{tree_id}")
async def delete_tree(
    farm_id: str,
    parcel_id: str,
    tree_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a tree from a parcel.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.farm import Tree

    tree = await db.get(Tree, tree_id)
    if not tree or tree.parcel_id != parcel_id:
        raise HTTPException(status_code=404, detail="Tree not found")

    await db.delete(tree)
    await db.commit()

    return {"message": "Tree deleted successfully"}


@router.post("/farm/{farm_id}/parcel/{parcel_id}/crops", response_model=dict)
async def add_crop_area(
    farm_id: str,
    parcel_id: str,
    crop_data: dict,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a crop area to a parcel for differentiation from trees.
    """
    # Verify farm and parcel belong to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.farm_id == farm_id)
    )
    parcel = parcel_result.scalar_one_or_none()

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    from app.models.farm import ParcelCrop

    # Create crop area
    crop = ParcelCrop(
        parcel_id=parcel_id,
        crop_type_id=crop_data.get('crop_type_id'),
        area_hectares=crop_data.get('area_hectares'),
        boundary_geojson=crop_data.get('boundary_geojson'),
        centroid_lat=crop_data.get('centroid_lat'),
        centroid_lon=crop_data.get('centroid_lon'),
        planted_date=datetime.fromisoformat(crop_data['planted_date']) if crop_data.get('planted_date') else None,
        expected_harvest_date=datetime.fromisoformat(crop_data['expected_harvest_date']) if crop_data.get('expected_harvest_date') else None,
        planting_density_per_ha=crop_data.get('planting_density_per_ha'),
        growth_stage=crop_data.get('growth_stage'),
        health_status=crop_data.get('health_status', 'healthy'),
        expected_yield_kg_ha=crop_data.get('expected_yield_kg_ha')
    )

    db.add(crop)
    await db.commit()
    await db.refresh(crop)

    return {
        "id": crop.id,
        "status": "created",
        "parcel_id": parcel_id
    }


@router.get("/farm/{farm_id}/parcel/{parcel_id}/crops")
async def get_parcel_crops(
    farm_id: str,
    parcel_id: str,
    crop_category: Optional[str] = None,  # Filter by category
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all crop areas in a parcel with optional filtering.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.farm import ParcelCrop, CropType

    # Build query with optional filtering
    query = select(ParcelCrop).join(CropType).where(ParcelCrop.parcel_id == parcel_id)

    if crop_category:
        query = query.where(CropType.category == crop_category)

    crops_result = await db.execute(query)
    crops = crops_result.scalars().all()

    # Get crop type details
    crop_types = {}
    if crops:
        crop_type_ids = [crop.crop_type_id for crop in crops if crop.crop_type_id]
        if crop_type_ids:
            crop_types_result = await db.execute(
                select(CropType).where(CropType.id.in_(crop_type_ids))
            )
            for ct in crop_types_result.scalars().all():
                crop_types[ct.id] = {
                    "name": ct.name,
                    "category": ct.category.value if ct.category else "other",
                    "coffee_variety": ct.coffee_variety.value if ct.coffee_variety else None,
                    "display_color": ct.display_color
                }

    return [
        {
            "id": crop.id,
            "crop_type": crop_types.get(crop.crop_type_id, {}),
            "area_hectares": crop.area_hectares,
            "boundary_geojson": crop.boundary_geojson,
            "centroid_lat": crop.centroid_lat,
            "centroid_lon": crop.centroid_lon,
            "planted_date": crop.planted_date.isoformat() if crop.planted_date else None,
            "expected_harvest_date": crop.expected_harvest_date.isoformat() if crop.expected_harvest_date else None,
            "growth_stage": crop.growth_stage.value if crop.growth_stage else None,
            "health_status": crop.health_status.value if crop.health_status else None,
            "expected_yield_kg_ha": crop.expected_yield_kg_ha,
            "actual_yield_kg_ha": crop.actual_yield_kg_ha,
            "maturity_percentage": crop.maturity_percentage,
            "irrigation_method": crop.irrigation_method,
            "organic_certified": bool(crop.organic_certified),
            "fair_trade_certified": bool(crop.fair_trade_certified),
            "rain_forest_alliance_certified": bool(crop.rain_forest_alliance_certified),
            "last_satellite_analysis": crop.last_satellite_analysis.isoformat() if crop.last_satellite_analysis else None,
            "health_score": crop.health_score
        }
        for crop in crops
    ]


@router.post("/farm/{farm_id}/parcel/{parcel_id}/crop-analysis")
async def analyze_crop_health(
    farm_id: str,
    parcel_id: str,
    crop_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze specific crop health using satellite data.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.farm import ParcelCrop, CropType

    # Get crop details
    crop = await db.get(ParcelCrop, crop_id)
    if not crop or crop.parcel_id != parcel_id:
        raise HTTPException(status_code=404, detail="Crop not found")

    # Get crop type details
    crop_type = await db.get(CropType, crop.crop_type_id)

    # Run satellite analysis specific to this crop
    from app.services.satellite_analysis import satellite_engine

    # Get parcel for analysis
    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id)
    )
    parcel = parcel_result.scalar_one_or_none()

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # Analyze parcel
    analysis_result = await satellite_engine.analyze_parcel(parcel)

    # Enhance analysis with crop-specific insights
    crop_analysis = {
        **analysis_result,
        "crop_specific_insights": {
            "crop_type": crop_type.name if crop_type else "Unknown",
            "category": crop_type.category.value if crop_type and crop_type.category else "other",
            "coffee_variety": crop_type.coffee_variety.value if crop_type and crop_type.coffee_variety else None,
            "expected_ndvi_range": {
                "min": crop_type.ndvi_range_min if crop_type else 0.3,
                "max": crop_type.ndvi_range_max if crop_type else 0.8
            },
            "health_assessment": "healthy" if analysis_result.get('ndvi_mean', 0) > 0.6 else "stressed",
            "yield_potential": crop.expected_yield_kg_ha or 0,
            "growth_stage_alignment": crop.growth_stage.value if crop.growth_stage else "unknown"
        }
    }

    # Update crop with latest analysis
    crop.last_satellite_analysis = datetime.utcnow()
    crop.health_score = analysis_result.get('crop_health_score', 5.0)
    await db.commit()

    return crop_analysis


@router.get("/crop-types")
async def get_crop_types(
    category: Optional[str] = None,
    current_user: User = Depends(require_farmer)
):
    """
    Get available crop types with optional category filtering.
    """
    from app.models.farm import CropType, CropCategory

    # This would typically come from a database query
    # For now, return predefined crop types
    crop_types = [
        {
            "id": "coffee_sl28",
            "name": "SL28 Coffee",
            "category": "coffee",
            "coffee_variety": "SL28",
            "ndvi_range_min": 0.4,
            "ndvi_range_max": 0.8,
            "display_color": "#8B4513",
            "description": "High-yield Arabica coffee variety"
        },
        {
            "id": "coffee_sl34",
            "name": "SL34 Coffee",
            "category": "coffee",
            "coffee_variety": "SL34",
            "ndvi_range_min": 0.4,
            "ndvi_range_max": 0.8,
            "display_color": "#A0522D",
            "description": "Disease-resistant Arabica coffee variety"
        },
        {
            "id": "coffee_batian",
            "name": "Batian Coffee",
            "category": "coffee",
            "coffee_variety": "Batian",
            "ndvi_range_min": 0.4,
            "ndvi_range_max": 0.8,
            "display_color": "#CD853F",
            "description": "Modern high-yield coffee variety"
        },
        {
            "id": "grevillea",
            "name": "Grevillea",
            "category": "shade_tree",
            "ndvi_range_min": 0.6,
            "ndvi_range_max": 0.9,
            "display_color": "#228B22",
            "description": "Fast-growing shade tree for coffee"
        },
        {
            "id": "macadamia",
            "name": "Macadamia",
            "category": "fruit_tree",
            "ndvi_range_min": 0.5,
            "ndvi_range_max": 0.8,
            "display_color": "#32CD32",
            "description": "High-value nut tree"
        },
        {
            "id": "avocado",
            "name": "Avocado",
            "category": "fruit_tree",
            "ndvi_range_min": 0.5,
            "ndvi_range_max": 0.8,
            "display_color": "#9ACD32",
            "description": "Fruit tree with high market value"
        }
    ]

    # Filter by category if specified
    if category:
        crop_types = [ct for ct in crop_types if ct["category"] == category]

    return crop_types


@router.get("/farm/{farm_id}/historical-analysis")
async def get_historical_farm_analysis(
    farm_id: str,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    analysis_type: Optional[str] = None,  # "satellite", "yield", "carbon", "trees"
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical farm analysis data from years back.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.farm import HistoricalAnalysis

    # Build query
    query = select(HistoricalAnalysis).where(
        HistoricalAnalysis.entity_type == "farm",
        HistoricalAnalysis.entity_id == str(farm_id)
    )

    if start_year:
        query = query.where(HistoricalAnalysis.analysis_year >= start_year)
    if end_year:
        query = query.where(HistoricalAnalysis.analysis_year <= end_year)

    query = query.order_by(HistoricalAnalysis.analysis_year.desc(), HistoricalAnalysis.analysis_date.desc())

    # Limit to last 100 records to prevent huge responses
    historical_result = await db.execute(query.limit(100))
    historical_data = historical_result.scalars().all()

    # Group by year for easier frontend consumption
    yearly_data = {}
    for record in historical_data:
        year = record.analysis_year
        if year not in yearly_data:
            yearly_data[year] = []

        yearly_data[year].append({
            "id": record.id,
            "analysis_date": record.analysis_date.isoformat(),
            "period": record.analysis_period,
            "satellite_source": record.satellite_source,
            "ndvi_mean": record.ndvi_mean,
            "canopy_cover_percentage": record.canopy_cover_percentage,
            "tree_cover_percentage": record.tree_cover_percentage,
            "crop_cover_percentage": record.crop_cover_percentage,
            "biomass_tons_hectare": record.biomass_tons_hectare,
            "carbon_stored_tons": record.carbon_stored_tons,
            "deforestation_detected": bool(record.deforestation_detected),
            "risk_level": record.risk_level,
            "tree_count": record.tree_count,
            "tree_health_score": record.tree_health_score,
            "crop_health_score": record.crop_health_score,
            "seasonal_trend": record.get_seasonal_trend(),
            "satellite_imagery_url": record.satellite_imagery_url
        })

    # Calculate year-over-year trends
    years = sorted(yearly_data.keys(), reverse=True)
    trends = {}

    for i, year in enumerate(years):
        if i < len(years) - 1:
            current_year_data = yearly_data[year]
            previous_year_data = yearly_data[years[i + 1]]

            if current_year_data and previous_year_data:
                # Calculate average NDVI change
                current_ndvi = sum(r['ndvi_mean'] for r in current_year_data if r['ndvi_mean']) / len([r for r in current_year_data if r['ndvi_mean']]) if any(r['ndvi_mean'] for r in current_year_data) else 0
                previous_ndvi = sum(r['ndvi_mean'] for r in previous_year_data if r['ndvi_mean']) / len([r for r in previous_year_data if r['ndvi_mean']]) if any(r['ndvi_mean'] for r in previous_year_data) else 0

                trends[year] = {
                    "ndvi_change": round(current_ndvi - previous_ndvi, 3),
                    "canopy_trend": "increasing" if current_year_data[0]['canopy_cover_percentage'] > previous_year_data[0]['canopy_cover_percentage'] else "decreasing",
                    "biomass_trend": "increasing" if current_year_data[0]['biomass_tons_hectare'] > previous_year_data[0]['biomass_tons_hectare'] else "decreasing"
                }

    return {
        "farm_id": farm_id,
        "farm_name": farm.farm_name,
        "historical_data": yearly_data,
        "yearly_trends": trends,
        "available_years": years,
        "total_records": len(historical_data)
    }


@router.post("/farm/{farm_id}/store-historical-analysis")
async def store_historical_analysis(
    farm_id: str,
    analysis_data: dict,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Store historical farm analysis data for long-term tracking.
    Called after satellite analysis to preserve historical records.
    """
    # Verify farm belongs to user
    result = await db.execute(
        select(Farm).where(Farm.id == farm_id, Farm.owner_id == current_user.id)
    )
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    from app.models.farm import HistoricalAnalysis

    # Create historical record
    historical = HistoricalAnalysis(
        entity_type="farm",
        entity_id=str(farm_id),
        analysis_date=datetime.fromisoformat(analysis_data['analysis_date']) if analysis_data.get('analysis_date') else datetime.utcnow(),
        analysis_year=analysis_data.get('analysis_year', datetime.utcnow().year),
        analysis_period=analysis_data.get('analysis_period', 'annual'),
        satellite_source=analysis_data.get('satellite_source'),
        acquisition_date=datetime.fromisoformat(analysis_data['acquisition_date']) if analysis_data.get('acquisition_date') else None,
        cloud_cover_percentage=analysis_data.get('cloud_cover_percentage'),
        ndvi_mean=analysis_data.get('ndvi_mean'),
        ndvi_min=analysis_data.get('ndvi_min'),
        ndvi_max=analysis_data.get('ndvi_max'),
        evi_mean=analysis_data.get('evi_mean'),
        savi_mean=analysis_data.get('savi_mean'),
        lai_mean=analysis_data.get('lai_mean'),
        canopy_cover_percentage=analysis_data.get('canopy_cover_percentage'),
        tree_cover_percentage=analysis_data.get('tree_cover_percentage'),
        crop_cover_percentage=analysis_data.get('crop_cover_percentage'),
        bare_soil_percentage=analysis_data.get('bare_soil_percentage'),
        biomass_tons_hectare=analysis_data.get('biomass_tons_hectare'),
        carbon_stored_tons=analysis_data.get('carbon_stored_tons'),
        carbon_sequestered_kg_year=analysis_data.get('carbon_sequestered_kg_year'),
        deforestation_detected=1 if analysis_data.get('deforestation_detected') else 0,
        deforestation_area_ha=analysis_data.get('deforestation_area_ha'),
        risk_level=analysis_data.get('risk_level'),
        risk_score=analysis_data.get('risk_score'),
        tree_count=analysis_data.get('tree_count'),
        tree_health_score=analysis_data.get('tree_health_score'),
        crop_health_score=analysis_data.get('crop_health_score'),
        rainfall_mm=analysis_data.get('rainfall_mm'),
        temperature_celsius=analysis_data.get('temperature_celsius'),
        soil_moisture_percentage=analysis_data.get('soil_moisture_percentage'),
        analysis_metadata=analysis_data.get('analysis_metadata'),
        satellite_imagery_url=analysis_data.get('satellite_imagery_url')
    )

    db.add(historical)
    await db.commit()
    await db.refresh(historical)

    return {
        "id": historical.id,
        "status": "stored",
        "analysis_year": historical.analysis_year
    }
