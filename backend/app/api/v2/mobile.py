"""
Mobile App API — API-key authenticated endpoints for field agents.
Handles farm lookup, farm creation, polygon capture submission,
and auto-provisioning of the default Polygon Cooperative + Farmer.

Security:
  - All endpoints require X-API-Key header (enforced at router level via dependencies=[])
  - API key is read from PLOTRA_MOBILE__API_KEY env var, not hardcoded
  - Simple per-IP rate limiting (PLOTRA_MOBILE__RATE_LIMIT_PER_MINUTE, default 60/min)
"""
import math
import random
import string
import time
import uuid
from collections import defaultdict
from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash, get_current_user_optional
from app.core.config import settings
from app.core.database import get_db
from app.models.farm import Farm, LandParcel, LandUseType
from app.models.user import (
    Cooperative, CooperativeMember, User, UserRole, UserStatus, VerificationStatus
)

# ── Default Polygon accounts ───────────────────────────────────────────────────

DEFAULT_COOP_CODE    = "POLYCOOP"
DEFAULT_COOP_NAME    = "Polygon Cooperative"
DEFAULT_OFFICER_EMAIL    = "officer@polygoncoop.eu"
DEFAULT_OFFICER_PASSWORD = "PolyOfficer2024!"
DEFAULT_OFFICER_PHONE    = "+254700000003"
DEFAULT_OFFICER_FIRST    = "Polygon"
DEFAULT_OFFICER_LAST     = "Officer"

DEFAULT_FARMER_EMAIL    = "farmer@polygoncoop.eu"
DEFAULT_FARMER_PASSWORD = "PolyFarmer2024!"
DEFAULT_FARMER_PHONE    = "+254700000002"
DEFAULT_FARMER_FIRST    = "Polygon"
DEFAULT_FARMER_LAST     = "Farmer"

# ── Geometry helpers ──────────────────────────────────────────────────────────

def _polygon_area_ha(coords: list) -> float:
    """Shoelace formula area for a [lon, lat] polygon, in hectares."""
    if len(coords) < 3:
        return 0.0
    mean_lat = sum(c[1] for c in coords) / len(coords)
    lat_m = 111320.0
    lon_m = 111320.0 * math.cos(math.radians(mean_lat))
    area = 0.0
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * lon_m * coords[j][1] * lat_m
        area -= coords[j][0] * lon_m * coords[i][1] * lat_m
    return abs(area) / 2.0 / 10_000.0


async def _refresh_farm_area(db, farm):
    """Sum parcel areas and write total back to farm.total_area_hectares."""
    from sqlalchemy import select as _select
    res = await db.execute(_select(LandParcel).where(LandParcel.farm_id == farm.id))
    total = sum(p.area_hectares or 0.0 for p in res.scalars().all())
    farm.total_area_hectares = round(total, 4)


# ── Auth & rate-limit helpers ──────────────────────────────────────────────────

_rate_store: dict = defaultdict(list)


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if x_api_key != settings.mobile.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = now - 60  # 1-minute sliding window
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window]
    if len(_rate_store[ip]) >= settings.mobile.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Too many requests — slow down.")
    _rate_store[ip].append(now)


# Router: both dependencies applied to every endpoint automatically
router = APIRouter(
    tags=["Mobile App"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit)],
)


# ── Default account provisioning ──────────────────────────────────────────────

@router.post("/mobile/setup")
async def setup_defaults(db: AsyncSession = Depends(get_db)):
    """
    Idempotent — safe to call every time the app opens.
    Creates Polygon Cooperative, Cooperative Officer, and Polygon Farmer
    if they don't already exist. Returns IDs and login credentials.
    """

    # 1. Cooperative
    coop_result = await db.execute(
        select(Cooperative).where(Cooperative.code == DEFAULT_COOP_CODE)
    )
    coop = coop_result.scalar_one_or_none()
    if not coop:
        coop = Cooperative(
            id=str(uuid.uuid4()),
            name=DEFAULT_COOP_NAME,
            code=DEFAULT_COOP_CODE,
            email=DEFAULT_OFFICER_EMAIL,
            country="Kenya",
            is_active=True,
            verification_status="admin_approved",
        )
        db.add(coop)
        await db.flush()

    # 2. Cooperative officer
    officer_result = await db.execute(
        select(User).where(User.email == DEFAULT_OFFICER_EMAIL)
    )
    officer = officer_result.scalar_one_or_none()
    if not officer:
        officer = User(
            id=str(uuid.uuid4()),
            email=DEFAULT_OFFICER_EMAIL,
            phone=DEFAULT_OFFICER_PHONE,
            password_hash=get_password_hash(DEFAULT_OFFICER_PASSWORD),
            first_name=DEFAULT_OFFICER_FIRST,
            last_name=DEFAULT_OFFICER_LAST,
            role=UserRole.COOPERATIVE_OFFICER,
            status=UserStatus.ACTIVE,
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            cooperative_id=coop.id,
            data_consent=True,
        )
        db.add(officer)
        await db.flush()
        # Link as primary officer
        if not coop.primary_officer_id:
            coop.primary_officer_id = officer.id

    # 3. Farmer
    farmer_result = await db.execute(
        select(User).where(User.email == DEFAULT_FARMER_EMAIL)
    )
    farmer = farmer_result.scalar_one_or_none()
    if not farmer:
        farmer = User(
            id=str(uuid.uuid4()),
            email=DEFAULT_FARMER_EMAIL,
            phone=DEFAULT_FARMER_PHONE,
            password_hash=get_password_hash(DEFAULT_FARMER_PASSWORD),
            first_name=DEFAULT_FARMER_FIRST,
            last_name=DEFAULT_FARMER_LAST,
            role=UserRole.FARMER,
            status=UserStatus.ACTIVE,
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            cooperative_id=coop.id,
            data_consent=True,
        )
        db.add(farmer)
        await db.flush()

        # Cooperative membership
        membership = CooperativeMember(
            id=str(uuid.uuid4()),
            user_id=farmer.id,
            cooperative_id=coop.id,
            membership_number="PF-001",
            membership_type="regular",
            is_active=True,
        )
        db.add(membership)

    await db.commit()

    return {
        "cooperative": {
            "id": coop.id,
            "name": DEFAULT_COOP_NAME,
            "code": DEFAULT_COOP_CODE,
        },
        "officer": {
            "id": officer.id,
            "name": f"{DEFAULT_OFFICER_FIRST} {DEFAULT_OFFICER_LAST}",
            "email": DEFAULT_OFFICER_EMAIL,
            "phone": DEFAULT_OFFICER_PHONE,
            "password": DEFAULT_OFFICER_PASSWORD,
        },
        "farmer": {
            "id": farmer.id,
            "name": f"{DEFAULT_FARMER_FIRST} {DEFAULT_FARMER_LAST}",
            "email": DEFAULT_FARMER_EMAIL,
            "phone": DEFAULT_FARMER_PHONE,
            "password": DEFAULT_FARMER_PASSWORD,
        },
    }


# ── Create farm (mobile add-farm flow) ────────────────────────────────────────

class FarmCreateMobile(BaseModel):
    # ── Required ──────────────────────────────────────────────────────────────
    farm_name: str = Field(..., min_length=1)
    county: str = Field(..., min_length=1)

    # ── Farm basics (stored in Farm model columns) ─────────────────────────────
    sub_county: Optional[str] = None
    ward: Optional[str] = None
    farm_code: Optional[str] = None
    land_use_type: Optional[str] = "agroforestry"
    total_area_hectares: Optional[float] = None
    coffee_area_hectares: Optional[float] = None
    coffee_varieties: Optional[List[str]] = None
    years_farming: Optional[int] = None
    average_annual_production_kg: Optional[float] = None

    # ── Land & parcel details (stored in admin_notes JSON) ─────────────────────
    farm_type: Optional[str] = None          # owned/leased/communal/inherited
    land_reg_number: Optional[str] = None
    altitude_m: Optional[float] = None
    soil_type: Optional[str] = None
    terrain: Optional[str] = None

    # ── Coffee farming details (stored in admin_notes JSON) ────────────────────
    coffee_trees: Optional[int] = None
    year_coffee_planted: Optional[int] = None
    farm_status: Optional[str] = None        # active/rehabilitating/abandoned
    planting_method: Optional[str] = None
    irrigation_used: Optional[bool] = None
    irrigation_type: Optional[str] = None

    # ── Farmer info (stored in admin_notes JSON) ───────────────────────────────
    farmer_first_name: Optional[str] = None
    farmer_last_name: Optional[str] = None
    farmer_phone: Optional[str] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    cooperative_name: Optional[str] = None

    # ── EUDR declarations (stored in admin_notes JSON) ─────────────────────────
    mixed_farming: Optional[bool] = None
    other_crops: Optional[List[str]] = None
    livestock: Optional[bool] = None
    livestock_types: Optional[List[str]] = None
    crop_rotation: Optional[bool] = None

    trees_planted_last_5y: Optional[bool] = None
    tree_species: Optional[List[str]] = None
    trees_planted_count: Optional[int] = None
    tree_planting_reasons: Optional[List[str]] = None

    trees_cleared_last_5y: Optional[bool] = None
    reason_for_clearing: Optional[str] = None
    current_canopy_cover: Optional[str] = None

    # ── Consent & certifications (stored in admin_notes JSON) ─────────────────
    satellite_consent: Optional[bool] = None
    historical_imagery_consent: Optional[bool] = None
    certifications: Optional[List[str]] = None
    previous_violations: Optional[bool] = None
    violation_details: Optional[str] = None

    notes: Optional[str] = None

    # ── Advanced / Tab-2 fields (stored in admin_notes JSON) ──────────────────
    cooperative_member_no: Optional[str] = None
    data_consent: Optional[bool] = None
    intercropped_species: Optional[List[str]] = None
    shade_trees: Optional[bool] = None
    shade_canopy_percent: Optional[int] = None
    agroforestry_start_year: Optional[int] = None
    last_pruning_date: Optional[str] = None
    last_harvesting_date: Optional[str] = None
    recent_planting: Optional[str] = None
    farm_established_year: Optional[int] = None
    previous_land_use: Optional[str] = None
    ngo_support: Optional[str] = None


def _random_suffix(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


@router.post("/mobile/farms/create", status_code=201)
async def create_farm_mobile(
    payload: FarmCreateMobile,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Create a new farm. If a valid Bearer token is present the farm is linked
    to the authenticated user; otherwise it falls back to the default Polygon Farmer.
    Farm is auto-approved so polygon capture works immediately.
    Returns farm_id and farm_code.
    """
    # Resolve farmer: use logged-in user if available, else default polygon farmer
    if current_user:
        farmer = current_user
    else:
        farmer_result = await db.execute(
            select(User).where(User.email == DEFAULT_FARMER_EMAIL)
        )
        farmer = farmer_result.scalar_one_or_none()
    if not farmer:
        raise HTTPException(
            status_code=409,
            detail="Default Polygon Farmer not found. Call /mobile/setup first.",
        )

    # Resolve cooperative: use the logged-in farmer's cooperative first,
    # only fall back to the default cooperative if the user has none.
    coop = None
    if current_user and current_user.cooperative_id:
        coop_result = await db.execute(
            select(Cooperative).where(Cooperative.id == current_user.cooperative_id)
        )
        coop = coop_result.scalar_one_or_none()
    if not coop:
        coop_result = await db.execute(
            select(Cooperative).where(Cooperative.code == DEFAULT_COOP_CODE)
        )
        coop = coop_result.scalar_one_or_none()

    # Parse land use type
    land_use_map = {
        "agroforestry": LandUseType.AGROFORESTRY,
        "monocrop": LandUseType.MONOCROP,
        "mixed_cropping": LandUseType.MIXED_CROPPING,
        "forest_reserve": LandUseType.FOREST_RESERVE,
        "buffer_zone": LandUseType.BUFFER_ZONE,
    }
    lut = land_use_map.get((payload.land_use_type or "agroforestry").lower(), LandUseType.AGROFORESTRY)

    # Resolve farm_code: use provided one or auto-generate
    if payload.farm_code:
        clean_code = payload.farm_code.strip().upper()
        dup = await db.execute(select(Farm).where(Farm.farm_code == clean_code))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Farm code '{clean_code}' already exists.")
        farm_code = clean_code
    else:
        date_str = datetime.utcnow().strftime("%Y%m%d")
        for _ in range(10):
            candidate = f"APP-{date_str}-{_random_suffix()}"
            existing = await db.execute(select(Farm).where(Farm.farm_code == candidate))
            if not existing.scalar_one_or_none():
                farm_code = candidate
                break
        else:
            farm_code = f"APP-{uuid.uuid4().hex[:10].upper()}"

    # Build admin_notes JSON with all extra fields
    meta: Dict[str, Any] = {
        "county": payload.county,
        "sub_county": payload.sub_county,
        "ward": payload.ward,
        # Land details
        "farm_type": payload.farm_type,
        "land_reg_number": payload.land_reg_number,
        "altitude_m": payload.altitude_m,
        "soil_type": payload.soil_type,
        "terrain": payload.terrain,
        # Coffee details
        "coffee_trees": payload.coffee_trees,
        "year_coffee_planted": payload.year_coffee_planted,
        "farm_status": payload.farm_status,
        "planting_method": payload.planting_method,
        "irrigation_used": payload.irrigation_used,
        "irrigation_type": payload.irrigation_type,
        # Farmer info
        "farmer_first_name": payload.farmer_first_name,
        "farmer_last_name": payload.farmer_last_name,
        "farmer_phone": payload.farmer_phone,
        "national_id": payload.national_id,
        "gender": payload.gender,
        "date_of_birth": payload.date_of_birth,
        "cooperative_name": payload.cooperative_name,
        # EUDR declarations
        "mixed_farming": payload.mixed_farming,
        "other_crops": payload.other_crops,
        "livestock": payload.livestock,
        "livestock_types": payload.livestock_types,
        "crop_rotation": payload.crop_rotation,
        "trees_planted_last_5y": payload.trees_planted_last_5y,
        "tree_species": payload.tree_species,
        "trees_planted_count": payload.trees_planted_count,
        "tree_planting_reasons": payload.tree_planting_reasons,
        "trees_cleared_last_5y": payload.trees_cleared_last_5y,
        "reason_for_clearing": payload.reason_for_clearing,
        "current_canopy_cover": payload.current_canopy_cover,
        # Consent & certifications
        "satellite_consent": payload.satellite_consent,
        "historical_imagery_consent": payload.historical_imagery_consent,
        "certifications": payload.certifications,
        "previous_violations": payload.previous_violations,
        "violation_details": payload.violation_details,
        "notes": payload.notes,
        "source": "mobile_app",
        # Advanced / Tab-2
        "cooperative_member_no": payload.cooperative_member_no,
        "data_consent": payload.data_consent,
        "intercropped_species": payload.intercropped_species,
        "shade_trees": payload.shade_trees,
        "shade_canopy_percent": payload.shade_canopy_percent,
        "agroforestry_start_year": payload.agroforestry_start_year,
        "last_pruning_date": payload.last_pruning_date,
        "last_harvesting_date": payload.last_harvesting_date,
        "recent_planting": payload.recent_planting,
        "farm_established_year": payload.farm_established_year,
        "previous_land_use": payload.previous_land_use,
        "ngo_support": payload.ngo_support,
    }

    farm = Farm(
        id=str(uuid.uuid4()),
        owner_id=farmer.id,
        cooperative_id=coop.id if coop else None,
        farm_name=payload.farm_name,
        farm_code=farm_code,
        land_use_type=lut,
        verification_status="admin_approved",
        coop_status="coop_approved",
        compliance_status="Under Review",
        # Store in Farm columns where available
        total_area_hectares=payload.total_area_hectares,
        coffee_area_hectares=payload.coffee_area_hectares,
        coffee_varieties=payload.coffee_varieties or [],
        years_farming=payload.years_farming,
        average_annual_production_kg=payload.average_annual_production_kg,
        admin_notes=json.dumps(meta),
    )

    db.add(farm)
    await db.commit()
    await db.refresh(farm)

    # Prefer real user data over payload placeholders
    farmer_name = " ".join(filter(None, [
        payload.farmer_first_name or (current_user.first_name if current_user else None),
        payload.farmer_last_name  or (current_user.last_name  if current_user else None),
    ])) or f"{DEFAULT_FARMER_FIRST} {DEFAULT_FARMER_LAST}"
    farmer_phone = payload.farmer_phone or (current_user.phone if current_user else None) or DEFAULT_FARMER_PHONE
    coop_display = coop.name if coop else (payload.cooperative_name or DEFAULT_COOP_NAME)

    return {
        "farm_id": farm.id,
        "farm_code": farm.farm_code,
        "farm_name": farm.farm_name,
        "county": payload.county,
        "sub_county": payload.sub_county,
        "ward": payload.ward,
        "land_use_type": (payload.land_use_type or "agroforestry"),
        "total_area_hectares": payload.total_area_hectares,
        "coffee_varieties": payload.coffee_varieties,
        "soil_type": payload.soil_type,
        "terrain": payload.terrain,
        "coffee_trees": payload.coffee_trees,
        "farmer_first_name": payload.farmer_first_name,
        "farmer_last_name": payload.farmer_last_name,
        "farmer_phone": farmer_phone,
        "national_id": payload.national_id,
        "cooperative_name": coop_display,
        "certifications": payload.certifications,
        "satellite_consent": payload.satellite_consent,
        "trees_cleared_last_5y": payload.trees_cleared_last_5y,
        "status": "admin_approved",
        "farmer": farmer_name,
        "cooperative": coop_display,
        "cooperative_phone": DEFAULT_OFFICER_PHONE,
    }


# ── Farm lookup ────────────────────────────────────────────────────────────────

@router.get("/farms/{identifier}")
async def get_farm_by_code(
    identifier: str,
    db: AsyncSession = Depends(get_db),
):
    """Look up a farm by farm_code (what the field agent types in the app)."""
    result = await db.execute(
        select(Farm).where(Farm.farm_code == identifier, Farm.is_deleted == 0)
    )
    farm = result.scalar_one_or_none()

    # Fallback: try matching by UUID id
    if not farm:
        result = await db.execute(
            select(Farm).where(Farm.id == identifier, Farm.is_deleted == 0)
        )
        farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(status_code=404, detail=f"Farm '{identifier}' not found")

    return {
        "id": farm.id,
        "farm_code": farm.farm_code,
        "farm_name": farm.farm_name,
        "area_hectares": farm.total_area_hectares,
        "status": farm.status,
        "compliance_status": getattr(farm, "compliance_status", None),
        "coffee_varieties": getattr(farm, "coffee_varieties", None),
        "land_use_type": getattr(farm, "land_use_type", None),
        "average_annual_production_kg": getattr(farm, "average_annual_production_kg", None),
        "farm_type": getattr(farm, "farm_type", None),
    }


# ── Polygon capture submission ─────────────────────────────────────────────────

class PolygonPoint(BaseModel):
    lat: float
    lng: float


class PolygonCaptureCreate(BaseModel):
    farm_id: str = Field(..., description="Farm UUID from /farms/{identifier} response")
    parcel_name: Optional[str] = None
    polygon_coordinates: List[PolygonPoint] = Field(..., min_length=3)
    area_ha: float
    perimeter_meters: Optional[float] = None
    points_count: int
    captured_at: str
    device_id: str
    agent_id: Optional[str] = None
    accuracy_m: Optional[float] = None
    notes: Optional[str] = None


@router.post("/parcels/polygon", status_code=201)
async def submit_polygon_capture(
    payload: PolygonCaptureCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit a polygon boundary captured by a field agent."""
    result = await db.execute(
        select(Farm).where(Farm.id == payload.farm_id, Farm.is_deleted == 0)
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail=f"Farm '{payload.farm_id}' not found")

    # Build GeoJSON polygon
    coords = [[p.lng, p.lat] for p in payload.polygon_coordinates]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    boundary_geojson = {"type": "Polygon", "coordinates": [coords]}

    # Build WKT for PostGIS
    wkt_coords = ", ".join(f"{p[0]} {p[1]}" for p in coords)
    wkt = f"POLYGON(({wkt_coords}))"

    try:
        from geoalchemy2.elements import WKTElement
        boundary_geometry = WKTElement(wkt, srid=4326)
    except Exception:
        boundary_geometry = None

    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    centroid_lon = sum(lons) / len(lons)
    centroid_lat = sum(lats) / len(lats)

    # Upsert: replace existing parcel if one exists, else create
    existing_result = await db.execute(
        select(LandParcel).where(LandParcel.farm_id == farm.id)
        .order_by(LandParcel.created_at)
        .limit(1)
    )
    existing_parcel = existing_result.scalar_one_or_none()

    from sqlalchemy.orm.attributes import flag_modified

    if existing_parcel:
        existing_parcel.boundary_geojson = boundary_geojson
        flag_modified(existing_parcel, "boundary_geojson")
        existing_parcel.boundary_geometry = boundary_geometry
        existing_parcel.area_hectares = payload.area_ha
        existing_parcel.perimeter_meters = payload.perimeter_meters
        existing_parcel.gps_accuracy_meters = payload.accuracy_m
        existing_parcel.mapping_method = "gps"
        existing_parcel.mapping_device = payload.device_id
        existing_parcel.mapping_date = datetime.utcnow()
        existing_parcel.verification_status = "pending"
        parcel = existing_parcel
    else:
        code_prefix = (farm.farm_code or farm.id)[:12]
        parcel_number = f"{code_prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        parcel = LandParcel(
            id=str(uuid.uuid4()),
            farm_id=farm.id,
            parcel_number=parcel_number,
            parcel_name=payload.parcel_name or parcel_number,
            boundary_geojson=boundary_geojson,
            boundary_geometry=boundary_geometry,
            area_hectares=payload.area_ha,
            perimeter_meters=payload.perimeter_meters,
            gps_accuracy_meters=payload.accuracy_m,
            mapping_method="gps",
            mapping_device=payload.device_id,
            mapping_date=datetime.utcnow(),
            consent_satellite_monitoring=1,
        )
        db.add(parcel)

    # Use calculated area as fallback if app sent 0
    saved_area = payload.area_ha or _polygon_area_ha(coords)
    if existing_parcel:
        existing_parcel.area_hectares = saved_area
    else:
        parcel.area_hectares = saved_area

    farm.centroid_lat = centroid_lat
    farm.centroid_lon = centroid_lon
    farm.verification_status = "pending"
    await _refresh_farm_area(db, farm)

    await db.commit()
    await db.refresh(parcel)

    return {
        "record_id": parcel.id,
        "farm_id": farm.id,
        "parcel_number": getattr(parcel, "parcel_number", ""),
        "area_ha": saved_area,
        "status": "updated" if existing_parcel else "created",
    }


# ── Batch sync ─────────────────────────────────────────────────────────────────

class BatchSyncRequest(BaseModel):
    captures: List[PolygonCaptureCreate]


@router.post("/sync/batch")
async def batch_sync(
    payload: BatchSyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sync multiple offline polygon captures in one request."""
    synced = 0
    failed = []

    for capture in payload.captures:
        try:
            result = await db.execute(
                select(Farm).where(Farm.id == capture.farm_id, Farm.is_deleted == 0)
            )
            farm = result.scalar_one_or_none()
            if not farm:
                failed.append({"farm_id": capture.farm_id, "error": "Farm not found"})
                continue

            coords = [[p.lng, p.lat] for p in capture.polygon_coordinates]
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            boundary_geojson = {"type": "Polygon", "coordinates": [coords]}
            wkt_coords = ", ".join(f"{p[0]} {p[1]}" for p in coords)
            wkt = f"POLYGON(({wkt_coords}))"

            try:
                from geoalchemy2.elements import WKTElement
                boundary_geometry = WKTElement(wkt, srid=4326)
            except Exception:
                boundary_geometry = None

            lons = [p[0] for p in coords]
            lats = [p[1] for p in coords]
            farm.centroid_lon = sum(lons) / len(lons)
            farm.centroid_lat = sum(lats) / len(lats)
            farm.verification_status = "pending"

            saved_area = capture.area_ha or _polygon_area_ha(coords)

            from sqlalchemy.orm.attributes import flag_modified

            ex_result = await db.execute(
                select(LandParcel).where(LandParcel.farm_id == farm.id)
                .order_by(LandParcel.created_at).limit(1)
            )
            existing = ex_result.scalar_one_or_none()

            if existing:
                existing.boundary_geojson = boundary_geojson
                flag_modified(existing, "boundary_geojson")
                existing.boundary_geometry = boundary_geometry
                existing.area_hectares = saved_area
                existing.perimeter_meters = capture.perimeter_meters
                existing.gps_accuracy_meters = capture.accuracy_m
                existing.mapping_method = "gps"
                existing.mapping_device = capture.device_id
                existing.mapping_date = datetime.utcnow()
                existing.verification_status = "pending"
            else:
                code_prefix = (farm.farm_code or farm.id)[:12]
                parcel_number = f"{code_prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{synced}"
                parcel = LandParcel(
                    id=str(uuid.uuid4()),
                    farm_id=farm.id,
                    parcel_number=parcel_number,
                    parcel_name=capture.parcel_name or parcel_number,
                    boundary_geojson=boundary_geojson,
                    boundary_geometry=boundary_geometry,
                    area_hectares=saved_area,
                    perimeter_meters=capture.perimeter_meters,
                    gps_accuracy_meters=capture.accuracy_m,
                    mapping_method="gps",
                    mapping_device=capture.device_id,
                    mapping_date=datetime.utcnow(),
                    consent_satellite_monitoring=1,
                )
                db.add(parcel)
            await _refresh_farm_area(db, farm)
            synced += 1
        except Exception as e:
            failed.append({"farm_id": capture.farm_id, "error": str(e)})

    if synced > 0:
        await db.commit()

    return {"synced": synced, "failed": failed, "total": len(payload.captures)}
