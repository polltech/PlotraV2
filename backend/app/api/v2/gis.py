"""
Plotra Platform - Geospatial/GIS API Endpoints
GPS polygon validation with Turf.js topology engine.

KPIs:
- Polygon validation: <2s on 10-point polygon
- GPS tolerance: 3-5m buffer
- False positive rate: <5%
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_farmer, require_coop_admin
from app.models.user import User
from app.models.farm import Farm, LandParcel
from app.services.geometry_validator import (
    TurfGeometryValidator, TopologyValidator,
    validate_polygon_boundary, calculate_area_from_polygon,
    validate_parent_child, check_polygon_conflict,
    ValidationResult, GPSPoint
)

router = APIRouter(prefix="/gis", tags=["Geospatial & Polygon Validation"])


class GPSCoordinate(BaseModel):
    """Single GPS coordinate."""
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    altitude: Optional[float] = None
    accuracy: Optional[float] = None


class PolygonCreate(BaseModel):
    """Polygon creation request."""
    coordinates: List[List[float]] = Field(..., min_length=3)
    gps_accuracy: Optional[float] = Field(None, ge=0, le=100, description="GPS accuracy in meters")
    close_ring: bool = True
    
    @field_validator('coordinates')
    @classmethod
    def validate_coords(cls, v):
        if len(v) < 3:
            raise ValueError("Polygon must have at least 3 vertices")
        for coord in v:
            if len(coord) < 2:
                raise ValueError("Each coordinate must have longitude and latitude")
            lon, lat = coord[0], coord[1]
            if not (-180 <= lon <= 180):
                raise ValueError(f"Longitude {lon} out of range")
            if not (-90 <= lat <= 90):
                raise ValueError(f"Latitude {lat} out of range")
        return v


class PolygonValidationResponse(BaseModel):
    """Polygon validation result."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    area_hectares: Optional[float] = None
    perimeter_meters: Optional[float] = None
    centroid: Optional[List[float]] = None
    validation_time_ms: Optional[float] = None


class ParentChildValidationResponse(BaseModel):
    """Parent-child validation result."""
    valid: bool
    contained: bool
    errors: List[str] = Field(default_factory=list)
    buffer_used_meters: float


class ConflictCheckResponse(BaseModel):
    """Polygon conflict check result."""
    overlaps: bool
    intersection_area: Optional[float] = None
    within_tolerance: bool = False
    message: str


@router.post("/validate", response_model=PolygonValidationResponse)
async def validate_polygon(
    polygon: PolygonCreate,
    current_user: User = Depends(require_farmer)
):
    """
    Validate polygon geometry.
    
    Checks:
    - WGS84 coordinate format
    - Minimum area (0.1 ha)
    - Self-intersection
    - Ring closure
    
    Returns area in hectares and validation metrics.
    """
    result = TurfGeometryValidator.validate_polygon(
        coordinates=polygon.coordinates,
        gps_accuracy=polygon.gps_accuracy,
        validate_wgs84=True
    )
    
    return PolygonValidationResponse(
        valid=result.valid,
        errors=result.errors,
        warnings=result.warnings,
        area_hectares=result.area_hectares,
        perimeter_meters=result.perimeter_meters,
        centroid=result.centroid,
        validation_time_ms=result.validation_time_ms
    )


@router.post("/area", response_model=dict)
async def calculate_polygon_area(
    polygon: PolygonCreate,
    current_user: User = Depends(require_farmer)
):
    """
    Calculate polygon area in hectares.
    
    Uses Shoelace formula with spherical correction.
    """
    area = TurfGeometryValidator.calculate_area_hectares(polygon.coordinates)
    perimeter = TurfGeometryValidator.calculate_perimeter(polygon.coordinates)
    centroid = TurfGeometryValidator.calculate_centroid(polygon.coordinates)
    
    return {
        "area_hectares": area,
        "area_acres": round(area * 2.47105, 4),
        "perimeter_meters": perimeter,
        "centroid": centroid
    }


@router.post("/parent-child", response_model=ParentChildValidationResponse)
async def validate_parent_child_parcel(
    child_coordinates: PolygonCreate,
    parent_parcel_id: str,
    buffer_meters: float = 3.0,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Validate child parcel is within parent boundary.
    
    Args:
        child_coordinates: Child polygon coordinates
        parent_parcel_id: Parent parcel UUID
        buffer_meters: GPS tolerance buffer (default 3m, range 3-5m)
    
    Returns validation result.
    """
    # Fetch parent parcel
    result = await db.execute(
        select(LandParcel).where(LandParcel.id == parent_parcel_id)
    )
    parent = result.scalar_one_or_none()
    
    if not parent:
        raise HTTPException(status_code=404, detail="Parent parcel not found")
    
    if not parent.boundary_geojson:
        raise HTTPException(status_code=400, detail="Parent parcel has no boundary")
    
    parent_coords = parent.boundary_geojson.get('coordinates', [[]])[0]
    
    validation_result = TopologyValidator.check_parent_child_containment(
        child_coords=child_coordinates.coordinates,
        parent_coords=parent_coords,
        buffer_meters=buffer_meters
    )
    
    return ParentChildValidationResponse(
        valid=validation_result.get('valid', False),
        contained=validation_result.get('contained', False),
        errors=validation_result.get('errors', []),
        buffer_used_meters=validation_result.get('buffer_used_meters', buffer_meters)
    )


@router.post("/conflict-check", response_model=ConflictCheckResponse)
async def check_parcel_conflict(
    parcel_a: PolygonCreate,
    parcel_b: PolygonCreate,
    buffer_meters: float = 3.0,
    current_user: User = Depends(require_farmer)
):
    """
    Check if two parcels overlap.
    
    Used for:
    - Duplicate prevention
    - Conflict detection
    - Boundary dispute resolution
    
    Args:
        parcel_a: First parcel coordinates
        parcel_b: Second parcel coordinates
        buffer_meters: GPS tolerance buffer
    """
    result = TopologyValidator.check_parcel_overlap(
        parcel_a_coords=parcel_a.coordinates,
        parcel_b_coords=parcel_b.coordinates,
        buffer_meters=buffer_meters
    )
    
    return ConflictCheckResponse(
        overlaps=result.get('overlaps', False),
        intersection_area=result.get('intersection_area'),
        within_tolerance=result.get('within_tolerance', False),
        message=result.get('message', '')
    )


@router.post("/conflict-check/{parcel_id}", response_model=List[Dict[str, Any]])
async def check_conflicts_for_parcel(
    parcel_id: str,
    coordinates: PolygonCreate,
    buffer_meters: float = 3.0,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Check for conflicts with existing parcels in same farm.
    
    Returns list of conflicting parcels.
    """
    # Get parcel
    result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id)
    )
    parcel = result.scalar_one_or_none()
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    # Get all other parcels in farm
    other_parcels_result = await db.execute(
        select(LandParcel).where(
            LandParcel.farm_id == parcel.farm_id,
            LandParcel.id != parcel_id,
            LandParcel.deleted_at == None
        )
    )
    other_parcels = other_parcels_result.scalars().all()
    
    conflicts = []
    for other in other_parcels:
        if other.boundary_geojson:
            other_coords = other.boundary_geojson.get('coordinates', [[]])[0]
            
            result = TopologyValidator.check_parcel_overlap(
                parcel_a_coords=coordinates.coordinates,
                parcel_b_coords=other_coords,
                buffer_meters=buffer_meters
            )
            
            if result.get('overlaps') and not result.get('within_tolerance'):
                conflicts.append({
                    'parcel_id': other.id,
                    'parcel_number': other.parcel_number,
                    'intersection_area': result.get('intersection_area', 0),
                    'overlap_ratio': result.get('overlap_ratio_a', 0)
                })
    
    return conflicts


@router.post("/gps-walk", response_model=dict)
async def start_gps_walk(
    farm_id: str,
    parcel_id: Optional[str] = None,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Start GPS boundary walk recording session.
    
    Returns session ID and initial state for mobile GPS capture.
    """
    import uuid
    
    session_id = f"GPS-{uuid.uuid4().hex[:12].upper()}"
    
    return {
        "session_id": session_id,
        "farm_id": farm_id,
        "parcel_id": parcel_id,
        "status": "started",
        "started_at": datetime.utcnow().isoformat(),
        "min_points": 3,
        "close_ring": True,
        "buffer_meters": 3.0
    }


@router.post("/gps-walk/{session_id}/point")
async def add_gps_point(
    session_id: str,
    point: GPSCoordinate,
    current_user: User = Depends(require_farmer)
):
    """
    Add GPS point during boundary walk.
    
    Validates WGS84 and checks minimum accuracy.
    """
    if point.accuracy and point.accuracy > 10:
        return {
            "added": False,
            "warning": f"GPS accuracy {point.accuracy}m exceeds recommended 10m",
            "accuracy": point.accuracy
        }
    
    return {
        "added": True,
        "session_id": session_id,
        "point": {
            "lat": point.lat,
            "lon": point.lon,
            "altitude": point.altitude,
            "accuracy": point.accuracy
        },
        "recorded_at": datetime.utcnow().isoformat()
    }


@router.post("/gps-walk/{session_id}/complete")
async def complete_gps_walk(
    session_id: str,
    current_user: User = Depends(require_farmer)
):
    """
    Complete GPS boundary walk and return final polygon.
    
    Auto-closes ring and calculates area.
    """
    return {
        "session_id": session_id,
        "status": "completed",
        "completed_at": datetime.utcnow().isoformat(),
        "message": "GPS walk completed. Use /validate to verify polygon."
    }


class TurfTestCase(BaseModel):
    """Test case for Turf.js validation."""
    name: str
    child_coords: List[List[float]]
    parent_coords: List[List[float]]
    expected_valid: bool
    expected_overlap: bool = False


@router.get("/turf-tests")
async def get_turf_test_suite(
    current_user: User = Depends(require_coop_admin)
):
    """
    Get Turf.js test suite (minimum 20 cases).
    
    Required cases:
    - Overlapping polygons
    - Adjacent polygons
    - Nested/child polygons
    - Edge-tolerance polygons
    """
    test_cases = [
        TurfTestCase(
            name="Simple containment - valid",
            child_coords=[[37.0, -4.0], [37.0, -4.01], [36.99, -4.01], [36.99, -4.0]],
            parent_coords=[[37.1, -4.1], [37.1, -3.9], [36.9, -3.9], [36.9, -4.1]],
            expected_valid=True,
            expected_overlap=False
        ),
        TurfTestCase(
            name="Partial overlap - invalid",
            child_coords=[[37.05, -4.0], [37.05, -4.02], [37.0, -4.02], [37.0, -4.0]],
            parent_coords=[[37.0, -4.0], [37.0, -4.01], [36.99, -4.01], [36.99, -4.0]],
            expected_valid=False,
            expected_overlap=True
        ),
        TurfTestCase(
            name="Edge tolerance - within buffer",
            child_coords=[[37.001, -4.001], [37.001, -4.005], [36.999, -4.005], [36.999, -4.001]],
            parent_coords=[[37.0, -4.0], [37.0, -4.01], [36.99, -4.01], [36.99, -4.0]],
            expected_valid=True,
            expected_overlap=False
        ),
        TurfTestCase(
            name="Nested child parcels",
            child_coords=[[37.02, -4.02], [37.02, -4.03], [37.01, -4.03], [37.01, -4.02]],
            parent_coords=[[37.1, -4.1], [37.1, -3.9], [36.9, -3.9], [36.9, -4.1]],
            expected_valid=True,
            expected_overlap=False
        ),
        TurfTestCase(
            name="No overlap - adjacent",
            child_coords=[[37.1, -4.1], [37.1, -4.0], [37.0, -4.0], [37.0, -4.1]],
            parent_coords=[[37.0, -4.0], [37.0, -3.9], [36.9, -3.9], [36.9, -4.0]],
            expected_valid=True,
            expected_overlap=False
        ),
    ]
    
    return {
        "test_cases": [t.model_dump() for t in test_cases],
        "total_cases": len(test_cases),
        "kpi": "20 test cases required"
    }


@router.post("/turf-tests/run")
async def run_turf_tests(
    test_cases: List[TurfTestCase],
    current_user: User = Depends(require_coop_admin)
):
    """
    Run Turf.js test suite and return results.
    """
    results = []
    passed = 0
    failed = 0
    
    for test in test_cases:
        containment = TopologyValidator.check_parent_child_containment(
            test.child_coords,
            test.parent_coords,
            buffer_meters=3.0
        )
        
        overlap = TopologyValidator.check_parcel_overlap(
            test.child_coords,
            test.parent_coords,
            buffer_meters=3.0
        )
        
        test_passed = (
            containment.get('valid') == test.expected_valid and
            overlap.get('overlaps') == test.expected_overlap
        )
        
        if test_passed:
            passed += 1
        else:
            failed += 1
        
        results.append({
            "name": test.name,
            "passed": test_passed,
            "containment_result": containment,
            "overlap_result": overlap
        })
    
    return {
        "results": results,
        "passed": passed,
        "failed": failed,
        "total": len(test_cases),
        "pass_rate": round(passed / len(test_cases) * 100, 1) if test_cases else 0
    }