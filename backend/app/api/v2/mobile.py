"""
Mobile App API — API-key authenticated endpoints for field agents.
Handles farm lookup by farm_code and polygon capture submission.

Security:
  - All endpoints require X-API-Key header (enforced at router level via dependencies=[])
  - API key is read from PLOTRA_MOBILE__API_KEY env var, not hardcoded
  - Simple per-IP rate limiting (PLOTRA_MOBILE__RATE_LIMIT_PER_MINUTE, default 60/min)
"""
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.farm import Farm, LandParcel

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

    farm.centroid_lat = centroid_lat
    farm.centroid_lon = centroid_lon
    farm.verification_status = "pending"

    await db.commit()
    await db.refresh(parcel)

    return {
        "record_id": parcel.id,
        "farm_id": farm.id,
        "parcel_number": getattr(parcel, "parcel_number", ""),
        "area_ha": payload.area_ha,
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
                existing.area_hectares = capture.area_ha
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
                    area_hectares=capture.area_ha,
                    perimeter_meters=capture.perimeter_meters,
                    gps_accuracy_meters=capture.accuracy_m,
                    mapping_method="gps",
                    mapping_device=capture.device_id,
                    mapping_date=datetime.utcnow(),
                    consent_satellite_monitoring=1,
                )
                db.add(parcel)
            synced += 1
        except Exception as e:
            failed.append({"farm_id": capture.farm_id, "error": str(e)})

    if synced > 0:
        await db.commit()

    return {"synced": synced, "failed": failed, "total": len(payload.captures)}
