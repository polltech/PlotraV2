"""
Mobile App API — API-key authenticated endpoints for field agents.
Handles farm lookup by farm_code and polygon capture submission.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.farm import Farm, LandParcel

router = APIRouter(tags=["Mobile App"])

MOBILE_API_KEY = "plotra-prototype-key-2026"


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if x_api_key != MOBILE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Farm lookup ────────────────────────────────────────────────────────────────

@router.get("/farms/{identifier}")
async def get_farm_by_code(
    identifier: str,
    _: str = Depends(verify_api_key),
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
    _: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Submit a polygon boundary captured by a field agent."""
    # Verify the farm exists
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

    # Auto-generate parcel number (keep under varchar(50))
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
    await db.commit()
    await db.refresh(parcel)

    return {
        "record_id": parcel.id,
        "farm_id": farm.id,
        "parcel_number": parcel_number,
        "area_ha": payload.area_ha,
        "status": "saved",
    }


# ── Batch sync ─────────────────────────────────────────────────────────────────

class BatchSyncRequest(BaseModel):
    captures: List[PolygonCaptureCreate]


@router.post("/sync/batch")
async def batch_sync(
    payload: BatchSyncRequest,
    _: str = Depends(verify_api_key),
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
