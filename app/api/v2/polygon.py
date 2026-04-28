"""
Plotra Platform - Polygon Capture API (v1) — URS Compliant
Endpoints for Kenya cooperative pilot prototype.
Matches: POST /api/v1/parcels/polygon, GET /api/v1/farms/{id}, POST /api/v1/sync/batch
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.config import settings
from app.models.farm import Farm, LandParcel
from app.models.polygon import PolygonCapture, SyncStatus
from app.api.schemas import (
    PolygonCaptureCreate, PolygonCaptureResponse, PolygonSubmitResponse
)

router = APIRouter(tags=["Polygon Capture v1"])


# ============== Helper: API Key Auth (prototype) ==============
async def verify_api_key(request: Request) -> bool:
    """
    Verify static API key from header.
    URS: 'Authentication uses a static API key in the request header'
    """
    api_key = request.headers.get("X-API-Key")
    # In production, store hashed key in settings
    valid_keys = getattr(settings, "polygon_api_keys", ["plotra-prototype-key-2026"])
    return api_key in valid_keys


async def get_api_key_auth(request: Request = None):
    """
    Dependency to require API key.
    If request is None (called from within FastAPI), skip.
    """
    if request is None:
        return True  # Skip when called internally
    valid = await verify_api_key(request)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return True


# ============== URS Endpoint 1: POST /api/v1/parcels/polygon ==============
@router.post("/parcels/polygon", response_model=PolygonCaptureResponse, status_code=status.HTTP_201_CREATED)
async def submit_polygon(
    capture_data: PolygonCaptureCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a polygon boundary (URS v0.1 endpoint).
    POST /api/v1/parcels/polygon
    
    Accepts URS format: polygon_coordinates array of {lat, lng}.
    Converts to GeoJSON for storage.
    Returns capture record with record_id.
    """
    await verify_api_key(request)

    # Verify farm exists
    farm_result = await db.execute(select(Farm).where(Farm.id == capture_data.farm_id))
    farm = farm_result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Convert URS polygon_coordinates to GeoJSON
    # URS: [{lat, lng}, ...] → GeoJSON: {"type":"Polygon","coordinates":[[[lng,lat],...]]}
    if not capture_data.polygon_coordinates or len(capture_data.polygon_coordinates) < 4:
        raise HTTPException(
            status_code=400,
            detail="Polygon must have at least 4 coordinate points"
        )

    # Build GeoJSON polygon (closed ring)
    coords_geojson = [
        [p['lng'], p['lat']] for p in capture_data.polygon_coordinates
    ]
    # Ensure closed ring
    if coords_geojson[0] != coords_geojson[-1]:
        coords_geojson.append(coords_geojson[0])

    boundary_geojson = {
        "type": "Polygon",
        "coordinates": [coords_geojson]
    }

    # Create polygon capture record
    capture = PolygonCapture(
        farm_id=capture_data.farm_id,
        boundary_geojson=boundary_geojson,
        polygon_coordinates=capture_data.polygon_coordinates,  # Store original URS format
        area_ha=capture_data.area_ha,
        perimeter_meters=capture_data.perimeter_meters,
        parcel_name=capture_data.parcel_name,
        capture_method="phone_gps",
        device_id=capture_data.device_id,
        captured_at=capture_data.captured_at,
        uploaded_at=datetime.utcnow(),
        sync_status=SyncStatus.SYNCED,  # Direct submission → synced immediately
        points_count=capture_data.points_count or len(capture_data.polygon_coordinates),
        gps_accuracy_avg=capture_data.accuracy_m,
        agent_id=capture_data.agent_id,
        topology_validated=True,
    )

    db.add(capture)
    await db.flush()

    # Create LandParcel immediately (online submission)
    result = await db.execute(
        select(func.max(LandParcel.parcel_number)).where(LandParcel.farm_id == capture_data.farm_id)
    )
    max_num = result.scalar_one_or_none() or 0
    next_num = max_num + 1

    parcel = LandParcel(
        farm_id=capture_data.farm_id,
        parcel_number=next_num,
        parcel_name=capture_data.parcel_name,
        boundary_geojson=boundary_geojson,
        area_hectares=capture_data.area_ha,
        land_use_type="agroforestry",
        mapping_date=capture.captured_at,
    )

    db.add(parcel)
    await db.flush()

    # Link capture to parcel
    capture.external_id = str(parcel.id)

    await db.commit()
    await db.refresh(capture)

    return capture


# ============== URS Endpoint 2: GET /api/v1/farms/{farm_id} ==============
@router.get("/farms/{farm_id}", response_model=FarmDetailsResponse)
async def get_farm_details(
    farm_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get farm details for confirmation step.
    URS: GET /api/v1/farms/{farm_id}
    Returns farm name, cooperative, area if available.
    """
    await verify_api_key(request)

    # Try numeric ID first, then code string
    try:
        farm_id_int = int(farm_id)
        result = await db.execute(select(Farm).where(Farm.id == farm_id_int))
    except ValueError:
        # Search by farm_name or other code field
        result = await db.execute(select(Farm).where(Farm.farm_name.ilike(f"%{farm_id}%")))
    
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    return {
        "id": farm.id,
        "farm_id": farm_id,  # Original input string
        "farm_name": farm.farm_name,
        "cooperative_name": None,  # TODO: join cooperative if needed
        "total_area_hectares": farm.total_area_hectares,
    }


# ============== URS Endpoint 3: POST /api/v1/sync/batch ==============
@router.post("/sync/batch", response_model=BatchSyncResponse)
async def sync_batch(
    request: Request,
    captures: List[PolygonCaptureCreate],
    db: AsyncSession = Depends(get_db)
):
    """
    Batch sync multiple polygon captures.
    URS: POST /api/v1/sync/batch
    Used by offline queue to upload multiple records at once.
    Accepts URS format (polygon_coordinates array).
    """
    await verify_api_key(request)

    synced = 0
    failed = 0
    errors = []

    for capture_data in captures:
        try:
            # Verify farm exists
            farm_result = await db.execute(select(Farm).where(Farm.id == capture_data.farm_id))
            farm = farm_result.scalar_one_or_none()
            if not farm:
                failed += 1
                errors.append(f"Farm {capture_data.farm_id} not found")
                continue

            # Convert URS polygon_coordinates to GeoJSON
            coords_geojson = [
                [p['lng'], p['lat']] for p in capture_data.polygon_coordinates
            ]
            if coords_geojson[0] != coords_geojson[-1]:
                coords_geojson.append(coords_geojson[0])

            boundary_geojson = {
                "type": "Polygon",
                "coordinates": [coords_geojson]
            }

            # Create capture
            capture = PolygonCapture(
                farm_id=capture_data.farm_id,
                boundary_geojson=boundary_geojson,
                polygon_coordinates=capture_data.polygon_coordinates,
                area_ha=capture_data.area_ha,
                perimeter_meters=capture_data.perimeter_meters,
                parcel_name=capture_data.parcel_name,
                capture_method="phone_gps",
                device_id=capture_data.device_id,
                captured_at=capture_data.captured_at,
                uploaded_at=datetime.utcnow(),
                sync_status=SyncStatus.SYNCED,
                points_count=capture_data.points_count or len(capture_data.polygon_coordinates),
                gps_accuracy_avg=capture_data.accuracy_m,
                agent_id=capture_data.agent_id,
                topology_validated=True,
            )
            db.add(capture)
            await db.flush()

            # Create LandParcel
            result = await db.execute(
                select(func.max(LandParcel.parcel_number)).where(LandParcel.farm_id == capture_data.farm_id)
            )
            max_num = result.scalar_one_or_none() or 0
            next_num = max_num + 1

            parcel = LandParcel(
                farm_id=capture_data.farm_id,
                parcel_number=next_num,
                parcel_name=capture_data.parcel_name,
                boundary_geojson=boundary_geojson,
                area_hectares=capture_data.area_ha,
                land_use_type="agroforestry",
                mapping_date=capture.captured_at,
            )
            db.add(parcel)
            await db.flush()

            capture.external_id = str(parcel.id)
            synced += 1

        except Exception as e:
            failed += 1
            errors.append(str(e))

    await db.commit()

    return BatchSyncResponse(
        synced=synced,
        failed=failed,
        errors=errors[:10],
        message=f"Batch sync: {synced} OK, {failed} failed"
    )


