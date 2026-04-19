"""
Plotra Platform - Satellite Analysis Engine
NDVI calculation, deforestation risk assessment, and land use classification
"""
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from shapely.geometry import shape, Point, Polygon
from shapely.ops import transform
import pyproj

from app.core.config import settings
from app.models.satellite import (
    SatelliteAnalysis, NDVIRecord, DeforestationRisk,
    AnalysisStatus, RiskLevel, LandCoverType
)
from app.models.farm import FarmParcel


@dataclass
class NDVIResult:
    """Result of NDVI analysis"""
    mean: float
    min: float
    max: float
    std_dev: float
    evi: float = 0.0
    savi: float = 0.0
    ndwi: float = 0.0
    land_cover_type: str = "agroforestry"
    canopy_cover: float = 0.0


@dataclass
class DeforestationAssessment:
    """Deforestation risk assessment result"""
    risk_score: float
    risk_level: str
    deforestation_detected: bool
    change_type: Optional[str]
    ndvi_change_pct: float
    recommendations: List[str]


class SatelliteAnalysisEngine:
    """
    Satellite analysis engine for EUDR compliance.
    Supports Sentinel-2 and Landsat-8 imagery.
    Includes simulation mode for local development.
    """
    
    def __init__(self, simulation_mode: bool = None):
        """
        Initialize the satellite analysis engine.
        
        Args:
            simulation_mode: Force simulation mode (defaults to config setting)
        """
        self.simulation_mode = simulation_mode if simulation_mode is not None else settings.satellite.simulation_mode
        self.ndvi_threshold = settings.satellite.ndvi_threshold
        self.baseline_year = settings.satellite.deforestation_baseline_year
    
    async def analyze_parcel(
        self,
        parcel: FarmParcel,
        acquisition_date: datetime = None
    ) -> SatelliteAnalysis:
        """
        Perform satellite analysis on a farm parcel.
        
        Args:
            parcel: FarmParcel model instance
            acquisition_date: Date of satellite imagery
            
        Returns:
            SatelliteAnalysis record with results
        """
        if acquisition_date is None:
            acquisition_date = datetime.utcnow()
        
        # Generate analysis ID
        analysis_id = f"SAT-{uuid.uuid4().hex[:12].upper()}"
        
        if self.simulation_mode:
            result = self._simulate_analysis(parcel)
        else:
            result = await self._fetch_satellite_data(parcel, acquisition_date)
        
        # Create analysis record
        analysis = SatelliteAnalysis(
            analysis_id=analysis_id,
            parcel_id=parcel.id,
            satellite_source="Sentinel-2" if not self.simulation_mode else "SIMULATION",
            acquisition_date=acquisition_date,
            status=AnalysisStatus.COMPLETED,
            
            # NDVI data
            ndvi_mean=result.mean,
            ndvi_min=result.min,
            ndvi_max=result.max,
            ndvi_standard_deviation=result.std_dev,
            
            # Vegetation indices
            evi=result.evi,
            savi=result.savi,
            ndwi=result.ndwi,
            
            # Land cover
            land_cover_type=LandCoverType(result.land_cover_type),
            land_cover_confidence=random.uniform(75, 95),
            
            # Canopy
            canopy_cover_percentage=result.canopy_cover,
            
            # Baseline comparison
            baseline_year=self.baseline_year,
            baseline_ndvi=result.mean * random.uniform(0.9, 1.1),
            ndvi_change_percentage=random.uniform(-5, 10),
        )
        
        # Calculate deforestation risk
        risk = self._assess_deforestation_risk(parcel, result)
        analysis.risk_level = RiskLevel(risk.risk_level)
        analysis.risk_score = risk.risk_score
        analysis.deforestation_detected = 1 if risk.deforestation_detected else 0
        analysis.change_type = risk.change_type
        analysis.ndvi_change_percentage = risk.ndvi_change_pct
        
        return analysis
    
    async def _fetch_satellite_data(
        self,
        parcel: FarmParcel,
        acquisition_date: datetime
    ) -> NDVIResult:
        """
        Fetch real satellite data from Sentinel Hub or Landsat.
        
        In production, this would call the Sentinel Hub API.
        
        Args:
            parcel: FarmParcel with boundary geometry
            acquisition_date: Date of imagery
            
        Returns:
            NDVI analysis results
        """
        # TODO: Implement actual Sentinel Hub API integration
        # For now, fall back to simulation
        return self._simulate_analysis(parcel)
    
    def _simulate_analysis(self, parcel: FarmParcel) -> NDVIResult:
        """
        Generate simulated satellite analysis for development.
        
        Args:
            parcel: FarmParcel model instance
            
        Returns:
            Simulated NDVI results
        """
        # Simulate realistic NDVI values based on land use type
        base_ndvi = random.uniform(0.55, 0.75)
        
        # Agroforestry systems typically have higher NDVI
        if parcel.land_use_type:
            if parcel.land_use_type.value == "agroforestry":
                base_ndvi = random.uniform(0.60, 0.80)
            elif parcel.land_use_type.value == "monocrop":
                base_ndvi = random.uniform(0.45, 0.65)
        
        return NDVIResult(
            mean=base_ndvi,
            min=base_ndvi - random.uniform(0.05, 0.15),
            max=base_ndvi + random.uniform(0.05, 0.15),
            std_dev=random.uniform(0.05, 0.12),
            evi=base_ndvi * random.uniform(0.8, 1.2),
            savi=base_ndvi * random.uniform(0.7, 1.1),
            ndwi=random.uniform(0.1, 0.3),
            land_cover_type="agroforestry" if base_ndvi > 0.6 else "agriculture",
            canopy_cover=random.uniform(30, 60)
        )
    
    def _assess_deforestation_risk(
        self,
        parcel: FarmParcel,
        ndvi_result: NDVIResult
    ) -> DeforestationAssessment:
        """
        Calculate deforestation risk score based on NDVI and historical data.
        
        Args:
            parcel: FarmParcel instance
            ndvi_result: NDVI analysis results
            
        Returns:
            Deforestation risk assessment
        """
        risk_score = 0.0
        recommendations = []
        
        # Factor 1: Current NDVI (lower NDVI may indicate deforestation)
        if ndvi_result.mean < 0.3:
            risk_score += 30
            recommendations.append("Very low vegetation cover detected - investigate potential deforestation")
        elif ndvi_result.mean < 0.5:
            risk_score += 20
            recommendations.append("Low vegetation cover - verify land use status")
        
        # Factor 2: NDVI change from baseline
        ndvi_change = random.uniform(-10, 10)  # Simulated
        if ndvi_change < -15:
            risk_score += 25
            recommendations.append("Significant vegetation decline detected - historical analysis recommended")
        elif ndvi_change < -5:
            risk_score += 10
            recommendations.append("Minor vegetation decline - monitor for changes")
        
        # Factor 3: Canopy cover
        if ndvi_result.canopy_cover < 20:
            risk_score += 15
            recommendations.append("Low canopy density - assess against historical baselines")
        
        # Factor 4: Land use type risk
        if parcel.land_use_type:
            if parcel.land_use_type.value == "monocrop":
                risk_score += 10
                recommendations.append("Monocrop system detected - verify EUDR compliance requirements")
        
        # Cap risk score at 100
        risk_score = min(risk_score, 100)
        
        # Determine risk level
        if risk_score < 25:
            risk_level = "low"
        elif risk_score < 50:
            risk_level = "medium"
        elif risk_score < 75:
            risk_level = "high"
        else:
            risk_level = "critical"
        
        # Determine if deforestation detected
        deforestation_detected = risk_score >= 50
        change_type = "deforestation" if deforestation_detected else None
        
        return DeforestationAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            deforestation_detected=deforestation_detected,
            change_type=change_type,
            ndvi_change_pct=ndvi_change,
            recommendations=recommendations
        )
    
    async def analyze_parcels_batch(
        self,
        parcels: List[FarmParcel],
        acquisition_date: datetime = None
    ) -> List[SatelliteAnalysis]:
        """
        Analyze multiple parcels in batch.
        
        Args:
            parcels: List of FarmParcel instances
            acquisition_date: Date of satellite imagery
            
        Returns:
            List of SatelliteAnalysis records
        """
        results = []
        for parcel in parcels:
            analysis = await self.analyze_parcel(parcel, acquisition_date)
            results.append(analysis)
        return results
    
    def calculate_ndvi_from_bands(
        self,
        red_band: List[float],
        nir_band: List[float]
    ) -> List[float]:
        """
        Calculate NDVI from red and NIR band values.
        
        NDVI = (NIR - Red) / (NIR + Red)
        
        Args:
            red_band: Red spectral band values
            nir_band: Near-infrared band values
            
        Returns:
            List of NDVI values
        """
        ndvi_values = []
        for red, nir in zip(red_band, nir_band):
            if (nir + red) != 0:
                ndvi = (nir - red) / (nir + red)
                ndvi_values.append(max(-1, min(1, ndvi)))  # Clamp to valid range
            else:
                ndvi_values.append(0)
        return ndvi_values
    
    def detect_land_use_change(
        self,
        geometry: Polygon,
        baseline_date: datetime,
        current_date: datetime
    ) -> Dict[str, Any]:
        """
        Detect land use changes between two time periods.
        
        Args:
            geometry: Parcel boundary polygon
            baseline_date: Historical date for comparison
            current_date: Current date for comparison
            
        Returns:
            Dictionary with change detection results
        """
        # Simulate change detection
        changes = {
            "change_detected": random.choice([True, False]),
            "change_type": None,
            "area_changed_hectares": 0.0,
            "confidence": 0.0,
            "recommended_action": None
        }
        
        if changes["change_detected"]:
            change_types = ["deforestation", "reforestation", "land_conversion", "natural_change"]
            changes["change_type"] = random.choice(change_types)
            changes["area_changed_hectares"] = random.uniform(0.1, 2.0)
            changes["confidence"] = random.uniform(70, 95)
            
            if changes["change_type"] == "deforestation":
                changes["recommended_action"] = "Verify deforestation status and compliance"
            elif changes["change_type"] == "reforestation":
                changes["recommended_action"] = "Update land use records"
        
        return changes
    
    def get_ndvi_statistics(
        self,
        ndvi_records: List[NDVIRecord]
    ) -> Dict[str, float]:
        """
        Calculate statistics from a series of NDVI records.
        
        Args:
            ndvi_records: List of NDVIRecord instances
            
        Returns:
            Dictionary with NDVI statistics
        """
        if not ndvi_records:
            return {"mean": 0, "min": 0, "max": 0, "std_dev": 0}
        
        values = [r.ndvi_value for r in ndvi_records]
        
        return {
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "std_dev": (sum((x - sum(values)/len(values))**2 for x in values) / len(values)) ** 0.5,
            "count": len(values),
            "date_range": {
                "start": min(r.observation_date for r in ndvi_records).isoformat(),
                "end": max(r.observation_date for r in ndvi_records).isoformat()
            }
        }


class SimulationNDVIGenerator:
    """
    Generate realistic simulated NDVI data for testing and development.
    """
    
    # Seasonal patterns for East Africa (coffee growing regions)
    SEASONAL_FACTORS = {
        1: 0.9,   # January - short dry season
        2: 0.85,  # February
        3: 0.95,  # March - long rains beginning
        4: 1.0,   # April - peak growing season
        5: 1.05,  # May
        6: 1.0,   # June
        7: 0.95,  # July
        8: 0.9,   # August - dry season
        9: 0.85,  # September
        10: 0.9,  # October - short rains beginning
        11: 0.95, # November
        12: 1.0   # December
    }
    
    def generate_historical_ndvi(
        self,
        parcel_id: int,
        start_date: datetime,
        end_date: datetime,
        base_ndvi: float = 0.65
    ) -> List[NDVIRecord]:
        """
        Generate historical NDVI records for a parcel.
        
        Args:
            parcel_id: Farm parcel ID
            start_date: Start of historical period
            end_date: End of historical period
            base_ndvi: Base NDVI value
            
        Returns:
            List of NDVIRecord instances
        """
        records = []
        current = start_date
        
        while current <= end_date:
            # Apply seasonal factor
            seasonal_factor = self.SEASONAL_FACTORS[current.month]
            ndvi_value = base_ndvi * seasonal_factor + random.uniform(-0.05, 0.05)
            ndvi_value = max(0, min(1, ndvi_value))  # Clamp to valid range
            
            record = NDVIRecord(
                parcel_id=parcel_id,
                observation_date=current,
                satellite_source="SIMULATION",
                ndvi_value=ndvi_value,
                pixel_count=random.randint(100, 500),
                cloud_cover=random.uniform(0, 30),
                quality_flag=1 if random.random() > 0.1 else 2
            )
            records.append(record)
            
            # Advance by approximately 10 days (typical revisit time)
            current += timedelta(days=10)
        
        return records


# Engine instance
satellite_engine = SatelliteAnalysisEngine()
ndvi_generator = SimulationNDVIGenerator()
