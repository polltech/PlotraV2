"""
Plotra Platform - GPS Polygon Validation Engine
Turf.js-based topology validation for parcel boundaries.

KPIs:
- GPS tolerance: 3-5m buffer to prevent false overlap flags
- Polygon validation: <2s on minimum-spec Android (10-point polygon)
- False positive rate: <5%

Features:
- WGS84 coordinate validation
- Parent-child parcel containment check
- GPS tolerance buffer for cooperatives with dense plots
- Area calculation in hectares
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import math

logger = logging.getLogger(__name__)


@dataclass
class GPSPoint:
    """GPS coordinate point."""
    lat: float
    lon: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    
    def to_coord(self) -> List[float]:
        """Convert to GeoJSON coordinate [lon, lat]."""
        return [self.lon, self.lat]


@dataclass
class ValidationResult:
    """Result of polygon validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    area_hectares: Optional[float] = None
    perimeter_meters: Optional[float] = None
    centroid: Optional[List[float]] = None
    validation_time_ms: Optional[float] = None


class TurfGeometryValidator:
    """
    Turf.js-style geometry validation for GPS polygon boundaries.
    Implements the same logic as the mobile Turf.js library.
    """
    
    WGS84_SRID = 4326
    GPS_TOLERANCE_METERS = 3.0  # Default GPS accuracy buffer
    MIN_AREA_HECTARES = 0.1
    MAX_AREA_HECTARES = 100.0
    MIN_VERTICES = 3
    
    EARTH_RADIUS_METERS = 6371000
    
    @classmethod
    def validate_wgs84(cls, coordinates: List[List[float]]) -> ValidationResult:
        """
        Validate that coordinates are in WGS84 format.
        
        Args:
            coordinates: GeoJSON polygon coordinates
            
        Returns:
            ValidationResult with any errors
        """
        errors = []
        warnings = []
        
        if not coordinates:
            return ValidationResult(False, ["No coordinates provided"], warnings)
        
        # Check coordinate order and range
        for i, coord in enumerate(coordinates):
            if len(coord) < 2:
                errors.append(f"Coordinate {i} missing longitude/latitude")
                continue
            
            lon, lat = coord[0], coord[1]
            
            # WGS84 bounds
            if not -180 <= lon <= 180:
                errors.append(f"Coordinate {i}: longitude {lon} out of WGS84 range [-180, 180]")
            if not -90 <= lat <= 90:
                errors.append(f"Coordinate {i}: latitude {lat} out of WGS84 range [-90, 90]")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    @classmethod
    def calculate_area_hectares(cls, coordinates: List[List[float]]) -> float:
        """
        Calculate polygon area in hectares using Shoelace formula with lat/lon correction.
        
        Args:
            coordinates: GeoJSON polygon coordinates (closed ring)
            
        Returns:
            Area in hectares
        """
        if len(coordinates) < 3:
            return 0.0
        
        # Ensure closed ring
        coords = coordinates.copy()
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        
        # Shoelace formula with spherical correction
        total_area = 0.0
        n = len(coords) - 1
        
        for i in range(n):
            j = (i + 1) % n
            lon1, lat1 = coords[i][0], coords[i][1]
            lon2, lat2 = coords[j][0], coords[j][1]
            
            # Convert to radians
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            lon_diff = math.radians(lon2 - lon1)
            
            # Spherical excess formula
            total_area += lon_diff * (2 + math.sin(lat1_rad) + math.sin(lat2_rad))
        
        # Final area calculation (absolute value / 2 * R^2)
        area_sq_meters = abs(total_area) / 2 * cls.EARTH_RADIUS_METERS ** 2
        area_hectares = area_sq_meters / 10000
        
        return round(area_hectares, 4)
    
    @classmethod
    def calculate_perimeter(cls, coordinates: List[List[float]]) -> float:
        """
        Calculate polygon perimeter in meters.
        
        Args:
            coordinates: GeoJSON polygon coordinates
            
        Returns:
            Perimeter in meters
        """
        if len(coordinates) < 2:
            return 0.0
        
        total_meters = 0.0
        
        for i in range(len(coordinates) - 1):
            total_meters += cls.haversine_distance(
                coordinates[i][1], coordinates[i][0],
                coordinates[i + 1][1], coordinates[i + 1][0]
            )
        
        return round(total_meters, 2)
    
    @classmethod
    def haversine_distance(
        cls,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two GPS points using Haversine formula.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return cls.EARTH_RADIUS_METERS * c
    
    @classmethod
    def calculate_centroid(cls, coordinates: List[List[float]]) -> List[float]:
        """Calculate polygon centroid."""
        if len(coordinates) < 3:
            return coordinates[0][:2] if coordinates else [0, 0]
        
        n = len(coordinates) - 1  # Exclude closing point
        sum_lon = sum(c[0] for c in coordinates[:n])
        sum_lat = sum(c[1] for c in coordinates[:n])
        
        return [sum_lon / n, sum_lat / n]
    
    @classmethod
    def validate_polygon(
        cls,
        coordinates: List[List[float]],
        gps_accuracy: Optional[float] = None,
        validate_wgs84: bool = True,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None
    ) -> ValidationResult:
        """
        Full polygon validation with GPS tolerance and area checks.
        
        Args:
            coordinates: GeoJSON polygon coordinates
            gps_accuracy: Reported GPS accuracy in meters
            validate_wgs84: Whether to validate WGS84 format
            min_area: Minimum allowed area in hectares
            max_area: Maximum allowed area in hectares
            
        Returns:
            ValidationResult with all checks
        """
        start_time = datetime.utcnow()
        
        errors = []
        warnings = []
        
        # 1. WGS84 validation
        if validate_wgs84:
            wgs84_result = cls.validate_wgs84(coordinates)
            if not wgs84_result.valid:
                errors.extend(wgs84_result.errors)
        
        # 2. Minimum vertices check
        if len(coordinates) < cls.MIN_VERTICES:
            errors.append(f"Polygon must have at least {cls.MIN_VERTICES} vertices")
        
        # 3. Close ring check
        if coordinates[0] != coordinates[-1]:
            warnings.append("Polygon ring is not closed - will auto-close")
            coordinates.append(coordinates[0])
        
        # 4. Self-intersection check
        if cls._check_self_intersection(coordinates):
            errors.append("Polygon has self-intersections")
        
        # 5. Calculate area
        area_hectares = cls.calculate_area_hectares(coordinates)
        
        min_allowed = min_area or cls.MIN_AREA_HECTARES
        max_allowed = max_area or cls.MAX_AREA_HECTARES
        
        if area_hectares < min_allowed:
            errors.append(f"Polygon area {area_hectares}ha below minimum {min_allowed}ha")
        if area_hectares > max_allowed:
            errors.append(f"Polygon area {area_hectares}ha above maximum {max_allowed}ha")
        
        # 6. GPS accuracy check
        tolerance = gps_accuracy or cls.GPS_TOLERANCE_METERS
        if tolerance > 10:
            warnings.append(f"GPS accuracy {tolerance}m is below optimal (>10m)")
        
        # 7. Calculate perimeter and centroid
        perimeter_meters = cls.calculate_perimeter(coordinates)
        centroid = cls.calculate_centroid(coordinates)
        
        # Calculate validation time
        validation_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            area_hectares=area_hectares,
            perimeter_meters=perimeter_meters,
            centroid=centroid,
            validation_time_ms=round(validation_time_ms, 2)
        )
    
    @classmethod
    def _check_self_intersection(cls, coordinates: List[List[float]]) -> bool:
        """Check if polygon edges intersect (excluding adjacent edges)."""
        n = len(coordinates)
        
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue  # Skip closing edge
                if abs(i - j) <= 1:
                    continue  # Skip adjacent edges
                
                if cls._segments_intersect(
                    coordinates[i], coordinates[i + 1],
                    coordinates[j], coordinates[(j + 1) % n]
                ):
                    return True
        
        return False
    
    @staticmethod
    def _segments_intersect(
        p1: List[float], p2: List[float],
        p3: List[float], p4: List[float]
    ) -> bool:
        """Check if two line segments intersect."""
        def ccw(a: List[float], b: List[float], c: List[float]) -> bool:
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
        
        return (ccw(p1, p3, p4) != ccw(p2, p3, p4) and
                ccw(p1, p2, p3) != ccw(p1, p2, p4))


class TopologyValidator:
    """
    Parent-child parcel topology validation.
    Validates that child parcels are contained within parent boundaries.
    Implements GPS tolerance buffer for dense plot areas.
    """
    
    GPS_BUFFER_METERS = 3.0  # 3-5m buffer per spec
    OVERLAP_TOLERANCE = 0.01  # 1% overlap tolerance
    
    @classmethod
    def check_parent_child_containment(
        cls,
        child_coords: List[List[float]],
        parent_coords: List[List[float]],
        buffer_meters: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Check if child polygon is contained within parent.
        
        Args:
            child_coords: Child polygon coordinates
            parent_coords: Parent polygon coordinates
            buffer_meters: GPS tolerance buffer (default 3m)
            
        Returns:
            Dictionary with containment result
        """
        buffer = buffer_meters or cls.GPS_BUFFER_METERS
        
        # Apply buffer to parent (shrink parent boundary)
        buffered_parent = cls._apply_buffer(parent_coords, -buffer)
        
        # Check containment
        child_centroid = TurfGeometryValidator.calculate_centroid(child_coords)
        
        if not cls._point_in_polygon(child_centroid, buffered_parent):
            return {
                "valid": False,
                "contained": False,
                "errors": ["Child centroid not within parent boundary"],
                "buffer_used_meters": buffer
            }
        
        # Check all child vertices
        vertices_outside = []
        for i, coord in enumerate(child_coords):
            if not cls._point_in_polygon(coord, buffered_parent):
                vertices_outside.append(i)
        
        if vertices_outside:
            return {
                "valid": False,
                "contained": False,
                "errors": [f"Child vertices {vertices_outside} outside parent"],
                "buffer_used_meters": buffer
            }
        
        return {
            "valid": True,
            "contained": True,
            "message": "Child parcel is within parent boundary",
            "buffer_used_meters": buffer
        }
    
    @classmethod
    def check_parcel_overlap(
        cls,
        parcel_a_coords: List[List[float]],
        parcel_b_coords: List[List[float]],
        buffer_meters: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Check if two parcels overlap.
        Used for conflict detection and duplicate prevention.
        
        Args:
            parcel_a_coords: First parcel coordinates
            parcel_b_coords: Second parcel coordinates
            buffer_meters: GPS tolerance buffer
            
        Returns:
            Dictionary with overlap result
        """
        buffer = buffer_meters or cls.GPS_BUFFER_METERS
        
        # Calculate intersection area
        intersection = cls._polygon_intersection(parcel_a_coords, parcel_b_coords)
        
        if intersection is None:
            return {
                "overlaps": False,
                "intersection_area": 0,
                "message": "No overlap detected"
            }
        
        # Apply tolerance check
        area_a = TurfGeometryValidator.calculate_area_hectares(parcel_a_coords)
        area_b = TurfGeometryValidator.calculate_area_hectares(parcel_b_coords)
        intersection_area = TurfGeometryValidator.calculate_area_hectares(intersection)
        
        overlap_ratio_a = intersection_area / area_a if area_a > 0 else 0
        overlap_ratio_b = intersection_area / area_b if area_b > 0 else 0
        
        # Within tolerance is not considered overlap
        if overlap_ratio_a < cls.OVERLAP_TOLERANCE and overlap_ratio_b < cls.OVERLAP_TOLERANCE:
            return {
                "overlaps": False,
                "intersection_area": intersection_area,
                "within_tolerance": True,
                "message": "Intersection within GPS tolerance"
            }
        
        return {
            "overlaps": True,
            "intersection_area": intersection_area,
            "overlap_ratio_a": round(overlap_ratio_a, 4),
            "overlap_ratio_b": round(overlap_ratio_b, 4),
            "conflict_parcels": True,
            "message": "Parcel overlap detected - requires resolution"
        }
    
    @classmethod
    def _apply_buffer(
        cls,
        coordinates: List[List[float]],
        buffer_meters: float
    ) -> List[List[float]]:
        """Apply buffer (positive = expand, negative = shrink)."""
        if buffer_meters == 0:
            return coordinates
        
        if abs(buffer_meters) < 10:
            factor = 0.0001 * abs(buffer_meters)
            sign = 1 if buffer_meters < 0 else -1
            
            buffered = []
            for coord in coordinates:
                lat, lon = coord[1], coord[0]
                buffered.append([
                    lon + sign * factor,
                    lat + sign * factor * 0.5
                ])
            
            if buffer_meters < 0:
                return buffered[:-1] if buffered[0] == buffered[-1] else buffered
            return buffered
        
        return coordinates
    
    @classmethod
    def _point_in_polygon(
        cls,
        point: List[float],
        polygon: List[List[float]]
    ) -> bool:
        """Ray casting point-in-polygon test."""
        x, y = point[0], point[1]
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0][0], polygon[0][1]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n][0], polygon[i % n][1]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    @staticmethod
    def _polygon_intersection(
        poly_a: List[List[float]],
        poly_b: List[List[float]]
    ) -> Optional[List[List[float]]]:
        """Calculate polygon intersection (simplified)."""
        intersection = []
        
        for coord_a in poly_a:
            if TopologyValidator._point_in_polygon(coord_a, poly_b):
                intersection.append(coord_a)
        
        for coord_b in poly_b:
            if TopologyValidator._point_in_polygon(coord_b, poly_a):
                intersection.append(coord_b)
        
        return intersection if len(intersection) >= 3 else None


def validate_polygon_boundary(
    coordinates: List[List[float]],
    gps_accuracy: Optional[float] = None,
    check_wgs84: bool = True
) -> ValidationResult:
    """
    Convenience function for polygon validation.
    
    Args:
        coordinates: GeoJSON polygon coordinates
        gps_accuracy: GPS accuracy in meters
        check_wgs84: Whether to validate WGS84 format
        
    Returns:
        ValidationResult
    """
    return TurfGeometryValidator.validate_polygon(
        coordinates=coordinates,
        gps_accuracy=gps_accuracy,
        validate_wgs84=check_wgs84
    )


def calculate_area_from_polygon(coordinates: List[List[float]]) -> float:
    """
    Calculate area in hectares from polygon coordinates.
    
    Args:
        coordinates: GeoJSON polygon coordinates
        
    Returns:
        Area in hectares
    """
    return TurfGeometryValidator.calculate_area_hectares(coordinates)


def validate_parent_child(
    child_coords: List[List[float]],
    parent_coords: List[List[float]],
    buffer_meters: float = 3.0
) -> Dict[str, Any]:
    """
    Validate child parcel is within parent boundary.
    
    Args:
        child_coords: Child polygon coordinates
        parent_coords: Parent polygon coordinates
        buffer_meters: GPS tolerance buffer (3-5m)
        
    Returns:
        Validation result dictionary
    """
    return TopologyValidator.check_parent_child_containment(
        child_coords=child_coords,
        parent_coords=parent_coords,
        buffer_meters=buffer_meters
    )


def check_polygon_conflict(
    parcel_a_coords: List[List[float]],
    parcel_b_coords: List[List[float]],
    buffer_meters: float = 3.0
) -> Dict[str, Any]:
    """
    Check if two parcels have a conflict (overlap).
    
    Args:
        parcel_a_coords: First parcel coordinates
        parcel_b_coords: Second parcel coordinates
        buffer_meters: GPS tolerance buffer
        
    Returns:
        Conflict result dictionary
    """
    return TopologyValidator.check_parcel_overlap(
        parcel_a_coords=parcel_a_coords,
        parcel_b_coords=parcel_b_coords,
        buffer_meters=buffer_meters
    )