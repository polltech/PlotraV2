"""
Plotra Platform - GPS Capture & Analysis API (Tier 1 Mobile Capture)
Simplified endpoints for mobile app to capture GPS points and get instant EUDR analysis.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import text
import json

from app.core.database import get_db
from app.models.farm import Farm, LandParcel
from app.models.gps import GpsCapture, CaptureTypeEnum, CaptureMethodEnum
from app.models.user import User
from app.api.schemas import GpsCaptureCreate, GpsCaptureResponse, CaptureAnalysisResponse

# Optional: allow unauthenticated access for simple capture (configure via settings)
# from app.core.auth import get_current_user, require_farmer
# For now, we'll make endpoints optionally authenticated

router = APIRouter(tags=["GPS Capture & Analysis"])


@router.get("/farms", response_model=List[Dict[str, Any]])
async def list_farms(
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of all farms for selection in mobile app.
    Returns simplified farm info (id, name, area).
    """
    result = await db.execute(
        select(Farm.id, Farm.farm_name, Farm.total_area_hectares, Farm.centroid_lat, Farm.centroid_lon)
        .where(Farm.deleted_at == None)
        .order_by(Farm.farm_name)
    )
    farms = result.all()

    return [
        {
            "id": f.id,
            "name": f.farm_name or f"Farm {f.id}",
            "area_hectares": f.total_area_hectares,
            "centroid": {"lat": f.centroid_lat, "lon": f.centroid_lon} if f.centroid_lat and f.centroid_lon else None
        }
        for f in farms
    ]


@router.get("/farms/{farm_id}/parcels", response_model=List[Dict[str, Any]])
async def list_parcels(
    farm_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all parcels for a specific farm.
    Used after farm selection to show parcel options.
    """
    # Verify farm exists
    farm_result = await db.execute(select(Farm).where(Farm.id == farm_id, Farm.deleted_at == None))
    farm = farm_result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    parcels_result = await db.execute(
        select(LandParcel.id, LandParcel.parcel_number, LandParcel.parcel_name,
               LandParcel.area_hectares, LandParcel.boundary_geojson)
        .where(LandParcel.farm_id == farm_id)
    )
    parcels = parcels_result.all()

    return [
        {
            "id": p.id,
            "parcel_number": p.parcel_number,
            "name": p.parcel_name or f"Parcel {p.parcel_number}",
            "area_hectares": p.area_hectares,
            "has_boundary": p.boundary_geojson is not None
        }
        for p in parcels
    ]


@router.post("/capture", response_model=CaptureAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_capture(
    capture_data: GpsCaptureCreate,
    db: AsyncSession = Depends(get_db)
    # current_user: Optional[User] = Depends(get_current_user)  # Optional auth
):
    """
    Capture GPS point and run instant analysis.

    This is the main endpoint for the mobile app:
    1. Receives GPS coordinates + farm selection
    2. Finds which parcel the point falls in (if any)
    3. Calculates risk score (inside parcel = compliant, outside = high risk)
    4. Returns analysis with recommendations

    No authentication required for simplicity (can be added later).
    """
    # Verify farm exists
    farm_result = await db.execute(select(Farm).where(Farm.id == capture_data.farm_id, Farm.deleted_at == None))
    farm = farm_result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Verify parcel if provided
    parcel = None
    if capture_data.parcel_id:
        parcel_result = await db.execute(
            select(LandParcel).where(
                LandParcel.id == capture_data.parcel_id,
                LandParcel.farm_id == capture_data.farm_id
            )
        )
        parcel = parcel_result.scalar_one_or_none()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found for this farm")

    # Create GPS capture record
    capture = GpsCapture(
        farm_id=capture_data.farm_id,
        parcel_id=capture_data.parcel_id,
        latitude=capture_data.latitude,
        longitude=capture_data.longitude,
        altitude=capture_data.altitude,
        accuracy_meters=capture_data.accuracy_meters,
        capture_type=capture_data.capture_type.value,
        capture_method=capture_data.capture_method.value,
        device_id=capture_data.device_id,
        device_model=capture_data.device_model,
        app_version=capture_data.app_version,
        notes=capture_data.notes,
        captured_at=capture_data.captured_at or datetime.utcnow(),
        uploaded_at=datetime.utcnow(),
        # captured_by_id=current_user.id if current_user else None
    )

    db.add(capture)
    await db.flush()  # Get capture ID without committing yet
    await db.refresh(capture)

    # Run analysis
    analysis_result = await _analyze_capture(db, capture, farm, parcel)

    # Update capture with analysis results
    capture.analysis_completed = True
    capture.analysis_timestamp = datetime.utcnow()
    capture.is_outside_parcel = analysis_result["is_outside_parcel"]

    await db.commit()
    await db.refresh(capture)

    # Build response
    response = CaptureAnalysisResponse(
        capture=GpsCaptureResponse.model_validate(capture),
        analysis=analysis_result["analysis"],
        parcel_info=analysis_result.get("parcel_info"),
        farm_info={
            "id": farm.id,
            "name": farm.farm_name or f"Farm {farm.id}",
            "compliance_status": farm.compliance_status,
            "deforestation_risk_score": farm.deforestation_risk_score
        },
        recommendations=analysis_result.get("recommendations", [])
    )

    return response


@router.get("/capture/{capture_id}", response_model=CaptureAnalysisResponse)
async def get_capture_analysis(
    capture_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a previous capture with its analysis results.
    """
    result = await db.execute(
        select(GpsCapture).where(GpsCapture.id == capture_id)
    )
    capture = result.scalar_one_or_none()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    # Get related farm
    farm_result = await db.execute(select(Farm).where(Farm.id == capture.farm_id))
    farm = farm_result.scalar_one_or_none()

    # Get parcel if exists
    parcel = None
    if capture.parcel_id:
        parcel_result = await db.execute(select(LandParcel).where(LandParcel.id == capture.parcel_id))
        parcel = parcel_result.scalar_one_or_none()

    # Re-run analysis (or load from stored results if we add that later)
    analysis_result = await _analyze_capture(db, capture, farm, parcel)

    return CaptureAnalysisResponse(
        capture=GpsCaptureResponse.model_validate(capture),
        analysis=analysis_result["analysis"],
        parcel_info=analysis_result.get("parcel_info"),
        farm_info={
            "id": farm.id,
            "name": farm.farm_name or f"Farm {farm.id}",
            "compliance_status": farm.compliance_status,
            "deforestation_risk_score": farm.deforestation_risk_score
        } if farm else None,
        recommendations=analysis_result.get("recommendations", [])
    )


# ============== Analysis Logic ==============

async def _analyze_capture(
    db: AsyncSession,
    capture: GpsCapture,
    farm: Farm,
    parcel: Optional[LandParcel] = None
) -> Dict[str, Any]:
    """
    Internal analysis function:
    - Checks if point falls within parcel boundary
    - Calculates risk score
    - Generates recommendations
    """

    analysis = {
        "point_in_parcel": None,
        "distance_to_boundary_meters": None,
        "risk_level": "unknown",
        "risk_score": 50.0,  # Default medium
        "compliance_status": "unknown"
    }

    recommendations = []

    if not parcel:
        # No specific parcel selected - try to find which parcel this point falls in
        found_parcel = await _find_parcel_for_point(db, capture.farm_id, capture.latitude, capture.longitude)
        parcel = found_parcel
        analysis["parcel_auto_detected"] = found_parcel is not None

    parcel_info = None
    if parcel:
        # Point is within (or near) a known parcel
        parcel_info = {
            "id": parcel.id,
            "parcel_number": parcel.parcel_number,
            "name": parcel.parcel_name or f"Parcel {parcel.parcel_number}",
            "area_hectares": parcel.area_hectares
        }

        # Check if point is inside parcel using PostGIS ST_Contains
        inside = await _is_point_in_parcel(db, parcel.id, capture.latitude, capture.longitude)

        if inside:
            analysis["point_in_parcel"] = True
            analysis["risk_level"] = "low"
            analysis["risk_score"] = 10.0
            analysis["compliance_status"] = "Compliant"
            recommendations.append("GPS point verified inside registered parcel boundary.")
            recommendations.append("Location complies with EUDR boundary requirements.")
        else:
            analysis["point_in_parcel"] = False
            # Point is outside - calculate distance to boundary
            distance = await _distance_to_parcel_boundary(db, parcel.id, capture.latitude, capture.longitude)
            analysis["distance_to_boundary_meters"] = distance

            if distance is not None and distance < 50:
                # Within 50m of boundary - could be boundary drift or mapping error
                analysis["risk_level"] = "medium"
                analysis["risk_score"] = 45.0
                analysis["compliance_status"] = "Needs Verification"
                recommendations.append(f"Point is {distance:.1f}m outside parcel boundary. Verify boundary accuracy.")
                recommendations.append("Consider updating parcel boundary if this represents actual cultivated area.")
            else:
                # Far outside parcel - potential deforestation or unregistered land
                analysis["risk_level"] = "high"
                analysis["risk_score"] = 85.0
                analysis["compliance_status"] = "Non-Compliant"
                recommendations.append("WARNING: Point is far outside registered parcel boundary.")
                recommendations.append("This may indicate deforestation or unregistered land use.")
                recommendations.append("Satellite analysis recommended to verify land use change.")
    else:
        # No parcel found for this farm
        analysis["point_in_parcel"] = False
        analysis["risk_level"] = "high"
        analysis["risk_score"] = 90.0
        analysis["compliance_status"] = "Non-Compliant"
        recommendations.append("No parcel boundary found for this farm.")
        recommendations.append("Register farm boundaries first to enable compliance verification.")
        recommendations.append("Capture should be associated with an existing parcel.")

    # Adjust risk score based on GPS accuracy
    if capture.accuracy_meters:
        if capture.accuracy_meters > 10:
            analysis["risk_score"] = min(analysis["risk_score"] + 10, 100)
            recommendations.append(f"GPS accuracy is {capture.accuracy_meters:.1f}m (lower precision). Re-capture for higher accuracy if needed.")

    # Adjust based on capture method
    if capture.capture_method == CaptureMethodEnum.RTK:
        analysis["risk_score"] = max(analysis["risk_score"] - 15, 0)  # High precision reduces risk
        recommendations.append("High-precision RTK capture increases confidence in boundary verification.")

    return {
        "analysis": analysis,
        "parcel_info": parcel_info,
        "recommendations": recommendations
    }


async def _find_parcel_for_point(db: AsyncSession, farm_id: int, lat: float, lon: float) -> Optional[LandParcel]:
    """
    Find which parcel (if any) contains the given point.
    Uses PostGIS ST_Contains for spatial query.
    """
    # Create WKT point from lat/lon
    point_wkt = f"POINT({lon} {lat})"  # GeoJSON uses (lon, lat) order

    # Query using ST_Contains
    # Note: boundary_geometry column contains PostGIS geometry (SRID 4326)
    stmt = select(LandParcel).where(
        LandParcel.farm_id == farm_id,
        func.ST_Contains(LandParcel.boundary_geometry, func.ST_GeomFromText(point_wkt, 4326))
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _is_point_in_parcel(db: AsyncSession, parcel_id: int, lat: float, lon: float) -> bool:
    """
    Check if a point falls within a specific parcel boundary.
    """
    point_wkt = f"POINT({lon} {lat})"
    stmt = select(func.ST_Contains(
        LandParcel.boundary_geometry,
        func.ST_GeomFromText(point_wkt, 4326)
    )).where(LandParcel.id == parcel_id)

    result = await db.execute(stmt)
    return result.scalar_one_or_none() or False


async def _distance_to_parcel_boundary(db: AsyncSession, parcel_id: int, lat: float, lon: float) -> Optional[float]:
    """
    Calculate minimum distance from point to parcel boundary in meters.
    Uses PostGIS ST_Distance with geography type for accurate meter calculation.
    Returns None if parcel has no boundary or calculation fails.
    """
    point_wkt = f"POINT({lon} {lat})"

    # Cast geometry to geography for meter calculations on WGS84
    stmt = select(func.ST_Distance(
        func.ST_GeogFromWKB(func.ST_AsBinary(LandParcel.boundary_geometry)),
        func.ST_GeogFromText(point_wkt)
    )).where(LandParcel.id == parcel_id)

    result = await db.execute(stmt)
    distance = result.scalar_one_or_none()
    return distance  # in meters
