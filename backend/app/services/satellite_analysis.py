"""
Plotra Platform - Satellite Analysis Engine
Satellite data analysis with Sentinel Hub API integration and simulation fallback.
"""
import uuid
import asyncio
import random
import math
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import settings

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

# Mock logger if not available
try:
    from app.core.logging import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


async def _load_satellite_credentials() -> Dict[str, Any]:
    """Load satellite credentials from DB (cfg_satellite_* keys)."""
    try:
        from app.core.database import async_session_factory
        from app.models.system import SystemConfig
        from sqlalchemy import select
        async with async_session_factory() as session:
            result = await session.execute(
                select(SystemConfig).where(SystemConfig.config_key.like("cfg_satellite_%"))
            )
            rows = result.scalars().all()
            return {r.config_key.replace("cfg_satellite_", ""): r.config_value for r in rows}
    except Exception:
        return {}


async def _get_sentinel_hub_token(client_id: str, client_secret: str) -> Optional[str]:
    """Exchange OAuth2 credentials for a Sentinel Hub access token."""
    if not _HAS_HTTPX or not client_id or not client_secret:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
            logger.warning(f"Sentinel Hub auth failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Sentinel Hub token error: {e}")
    return None


async def _fetch_sentinel_hub_ndvi(token: str, coords: List, acquisition_date: datetime) -> Optional[Dict]:
    """Call Sentinel Hub Process API to compute real NDVI/EVI/NDMI for a polygon."""
    if not _HAS_HTTPX or not token or not coords:
        return None

    date_str = acquisition_date.strftime("%Y-%m-%d")
    # Use a ±15 day window around the acquisition date
    from_date = (acquisition_date - timedelta(days=15)).strftime("%Y-%m-%d")

    evalscript = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B02", "B03", "B04", "B08", "B8A", "B11", "B12", "CLM"] }],
    output: [{ id: "default", bands: 8, sampleType: "FLOAT32" }]
  };
}
function evaluatePixel(sample) {
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 0.0001);
  let evi  = 2.5 * (sample.B08 - sample.B04) / (sample.B08 + 6*sample.B04 - 7.5*sample.B02 + 1 + 0.0001);
  let savi = 1.5 * (sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 0.5 + 0.0001);
  let ndmi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11 + 0.0001);
  let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08 + 0.0001);
  let lai  = 3.618 * evi - 0.118;
  let cloud = sample.CLM;
  return [ndvi, evi, savi, ndmi, ndwi, lai, cloud, 1];
}
"""

    payload = {
        "input": {
            "bounds": {
                "geometry": {"type": "Polygon", "coordinates": [coords]}
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {"from": f"{from_date}T00:00:00Z", "to": f"{date_str}T23:59:59Z"},
                    "maxCloudCoverage": 80
                }
            }]
        },
        "output": {
            "width": 64, "height": 64,
            "responses": [{"identifier": "default", "format": {"type": "application/json"}}]
        },
        "evalscript": evalscript
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://services.sentinel-hub.com/api/v1/statistics",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "input": payload["input"],
                    "aggregation": {
                        "timeRange": {"from": f"{from_date}T00:00:00Z", "to": f"{date_str}T23:59:59Z"},
                        "aggregationInterval": {"of": "P30D"},
                        "evalscript": evalscript,
                        "resx": 10, "resy": 10
                    },
                    "calculations": {}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                # Parse statistics response
                intervals = data.get("data", [])
                if intervals:
                    stats = intervals[-1].get("outputs", {}).get("default", {}).get("bands", {})
                    b0 = stats.get("B0", {}).get("stats", {})  # ndvi
                    b1 = stats.get("B1", {}).get("stats", {})  # evi
                    b2 = stats.get("B2", {}).get("stats", {})  # savi
                    b3 = stats.get("B3", {}).get("stats", {})  # ndmi
                    b4 = stats.get("B4", {}).get("stats", {})  # ndwi
                    b5 = stats.get("B5", {}).get("stats", {})  # lai
                    b6 = stats.get("B6", {}).get("stats", {})  # cloud mask
                    ndvi_mean = b0.get("mean", 0)
                    cloud_pct = b6.get("mean", 0) * 100
                    return {
                        "ndvi_mean": round(float(ndvi_mean), 3),
                        "ndvi_min": round(float(b0.get("min", ndvi_mean - 0.1)), 3),
                        "ndvi_max": round(float(b0.get("max", ndvi_mean + 0.1)), 3),
                        "ndvi_std_dev": round(float(b0.get("stDev", 0.05)), 3),
                        "evi": round(float(b1.get("mean", 0)), 3),
                        "savi": round(float(b2.get("mean", 0)), 3),
                        "ndmi": round(float(b3.get("mean", 0)), 3),
                        "ndwi": round(float(b4.get("mean", 0)), 3),
                        "lai": round(float(b5.get("mean", 0)), 2),
                        "cloud_cover_percentage": round(float(cloud_pct), 1),
                        "satellite_source": "SENTINEL_2",
                        "real_data": True,
                    }
            logger.warning(f"Sentinel Hub stats API: {resp.status_code} {resp.text[:300]}")
    except Exception as e:
        logger.warning(f"Sentinel Hub stats call failed: {e}")
    return None


class SatelliteAnalysisEngine:
    """
    Satellite analysis engine — uses Sentinel Hub when credentials are configured,
    falls back to simulation otherwise.
    """

    def __init__(self, simulation_mode: Optional[bool] = None):
        self.simulation_mode = simulation_mode if simulation_mode is not None else True
        self.ndvi_threshold = 0.3
        self.baseline_year = 2020

    async def analyze_parcel(self, parcel: Any, acquisition_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Perform comprehensive satellite analysis on a parcel.
        Returns NDVI, vegetation indices, biomass estimation, and risk assessment.
        """
        if acquisition_date is None:
            acquisition_date = datetime.utcnow()

        parcel_id = getattr(parcel, 'id', None)
        analysis_id = f"SAT-{uuid.uuid4().hex[:12].upper()}"

        try:
            # Try real Sentinel Hub API if credentials are saved in DB
            real_data = None
            creds = await _load_satellite_credentials()
            use_simulation = creds.get("simulation_mode", True)
            if use_simulation is False or use_simulation == "false":
                use_simulation = False
            else:
                use_simulation = True

            if not use_simulation:
                client_id = creds.get("oauth_client_id", "")
                client_secret = creds.get("oauth_client_secret", "")
                if client_id and client_secret and client_secret != "***":
                    token = await _get_sentinel_hub_token(client_id, client_secret)
                    if token:
                        coords = []
                        if getattr(parcel, 'boundary_geojson', None):
                            coords = parcel.boundary_geojson.get('coordinates', [[]])[0]
                        real_data = await _fetch_sentinel_hub_ndvi(token, coords, acquisition_date)
                        if real_data:
                            logger.info(f"Real Sentinel Hub data for parcel {parcel_id}: NDVI={real_data.get('ndvi_mean')}")

            # Build base result — real data if available, simulation otherwise
            result = self._simulate_analysis(parcel, acquisition_date)
            if real_data:
                result.update(real_data)  # overwrite with real values

            # Get crop-specific analysis
            crop_analysis = await self._analyze_crop_types(parcel, result)

            # Calculate risk assessment
            risk_assessment = self._calculate_risk_score(result)

            # Derive canopy/biomass from real NDVI when available
            if real_data:
                ndvi = result["ndvi_mean"]
                canopy = min(95, max(10, ndvi * 80))
                tree_cover = canopy * 0.6
                crop_cover = canopy * 0.4
                bare_soil = max(0, 100 - canopy)
                biomass = tree_cover * 0.2 + crop_cover * 0.05
                carbon = tree_cover * 0.2 * 0.45 + crop_cover * 0.05 * 0.25
                result.update({
                    "canopy_cover_percentage": round(canopy, 1),
                    "tree_cover_percentage": round(tree_cover, 1),
                    "crop_cover_percentage": round(crop_cover, 1),
                    "bare_soil_percentage": round(bare_soil, 1),
                    "tree_density": round(tree_cover * 0.8, 1),
                    "biomass_tons_hectare": round(max(0, biomass), 2),
                    "tree_biomass_tons_hectare": round(tree_cover * 0.2, 2),
                    "crop_biomass_tons_hectare": round(crop_cover * 0.05, 2),
                    "carbon_stored_tons": round(carbon, 2),
                    "carbon_sequestered_kg_year": round(carbon * 1000 * 0.02, 0),
                    "tree_health_score": round(min(10, max(1, ndvi * 8 + canopy / 10)), 1),
                    "crop_health_score": round(min(10, max(1, ndvi * 7 + crop_cover / 10)), 1),
                    "land_cover_type": "dense_vegetation" if ndvi > 0.7 else "moderate_vegetation" if ndvi > 0.5 else "sparse_vegetation" if ndvi > 0.3 else "bare_soil",
                    "land_cover_confidence": 0.95,
                    "data_source": "SENTINEL_HUB_REAL",
                })

            return {
                "analysis_id": analysis_id,
                "parcel_id": parcel_id,
                "status": "completed",
                "satellite_source": "SENTINEL_2",
                "acquisition_date": acquisition_date.isoformat(),
                **result,
                **crop_analysis,
                **risk_assessment
            }

        except Exception as e:
            logger.error(f"Satellite analysis failed for parcel {parcel_id}: {str(e)}")
            return {
                "analysis_id": analysis_id,
                "parcel_id": parcel_id,
                "status": "failed",
                "error": str(e),
                "acquisition_date": acquisition_date.isoformat()
            }

    async def _analyze_crop_types(self, parcel: Any, base_analysis: Dict) -> Dict[str, Any]:
        """
        Analyze different crop types within a parcel.
        Provides crop-specific insights and differentiation.
        """
        # Get crops from parcel (if available)
        crops = getattr(parcel, 'crops', []) or []

        crop_insights = {
            "crop_differentiation": {},
            "dominant_crops": [],
            "crop_health_distribution": {},
            "agroforestry_score": 5.0  # Base score
        }

        if not crops:
            # No crop data available, provide general insights
            crop_insights["crop_differentiation"] = {
                "coffee": {
                    "estimated_area_percentage": 70,
                    "health_score": base_analysis.get('crop_health_score', 5.0),
                    "ndvi_range": [0.4, 0.8]
                },
                "trees": {
                    "estimated_area_percentage": 20,
                    "health_score": base_analysis.get('tree_health_score', 5.0),
                    "ndvi_range": [0.6, 0.9]
                },
                "other": {
                    "estimated_area_percentage": 10,
                    "health_score": 4.0,
                    "ndvi_range": [0.2, 0.6]
                }
            }
        else:
            # Analyze specific crops
            total_area = sum(crop.area_hectares or 0 for crop in crops)
            crop_analysis = {}

            for crop in crops:
                if not crop.crop_type:
                    continue

                crop_name = crop.crop_type.name or "Unknown"
                crop_category = crop.crop_type.category or "other"

                # Crop-specific NDVI analysis
                base_ndvi = base_analysis.get('ndvi_mean', 0.5)
                category_modifier = {
                    "coffee": 0.0,  # Coffee baseline
                    "shade_tree": 0.1,  # Trees typically higher NDVI
                    "fruit_tree": 0.05,  # Fruit trees moderate
                    "timber": 0.15,  # Timber trees high
                    "vegetable": -0.1,  # Vegetables lower
                    "legume": -0.05,  # Legumes moderate
                    "cereal": -0.15,  # Cereals lower
                    "other": 0.0
                }

                crop_ndvi = base_ndvi + category_modifier.get(crop_category, 0.0)
                crop_ndvi = max(0.1, min(0.95, crop_ndvi))

                # Health assessment based on crop type
                health_score = 5.0
                if crop.health_status:
                    status_modifier = {
                        "healthy": 0,
                        "stressed": -1,
                        "diseased": -2,
                        "pest_infested": -1.5,
                        "water_stressed": -1,
                        "nutrient_deficient": -1
                    }
                    health_score += status_modifier.get(crop.health_status.value, 0)

                health_score = max(1.0, min(10.0, health_score))

                crop_analysis[crop_name] = {
                    "category": crop_category,
                    "area_hectares": crop.area_hectares,
                    "area_percentage": (crop.area_hectares / total_area * 100) if total_area > 0 else 0,
                    "ndvi_estimated": round(crop_ndvi, 3),
                    "health_score": round(health_score, 1),
                    "growth_stage": crop.growth_stage.value if crop.growth_stage else "unknown",
                    "yield_potential_kg_ha": crop.expected_yield_kg_ha,
                    "certifications": {
                        "organic": bool(crop.organic_certified),
                        "fair_trade": bool(crop.fair_trade_certified),
                        "rain_forest_alliance": bool(crop.rain_forest_alliance_certified)
                    }
                }

            crop_insights["crop_differentiation"] = crop_analysis

            # Calculate agroforestry score
            tree_count = sum(1 for crop in crops if crop.crop_type and crop.crop_type.category in ["shade_tree", "fruit_tree", "timber"])
            coffee_count = sum(1 for crop in crops if crop.crop_type and crop.crop_type.category == "coffee")

            if tree_count > 0 and coffee_count > 0:
                agroforestry_ratio = tree_count / (tree_count + coffee_count)
                crop_insights["agroforestry_score"] = min(10.0, 5.0 + agroforestry_ratio * 3.0)
            elif tree_count > 0:
                crop_insights["agroforestry_score"] = 7.0  # Tree-focused
            else:
                crop_insights["agroforestry_score"] = 3.0  # Monocrop

        # Identify dominant crops
        if crop_insights["crop_differentiation"]:
            sorted_crops = sorted(
                crop_insights["crop_differentiation"].items(),
                key=lambda x: x[1].get("area_percentage", 0),
                reverse=True
            )
            crop_insights["dominant_crops"] = [crop[0] for crop in sorted_crops[:3]]

        return crop_insights

    async def analyze_parcels_batch(self, parcels: List[Any], acquisition_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Analyze multiple parcels."""
        if not parcels:
            return []

        results = []
        for parcel in parcels:
            result = await self.analyze_parcel(parcel, acquisition_date)
            results.append(result)

        return results

    def _simulate_analysis(self, parcel: Any, acquisition_date: datetime) -> Dict[str, Any]:
        """Generate realistic simulated satellite analysis data with EUDR compliance checks."""
        # Base values with some realistic variation
        base_ndvi = 0.65
        day_of_year = acquisition_date.timetuple().tm_yday
        seasonal_variation = math.sin(2 * math.pi * day_of_year / 365) * 0.1
        random_variation = (random.random() - 0.5) * 0.1

        ndvi_mean = max(0.1, min(0.9, base_ndvi + seasonal_variation + random_variation))

        # Calculate other indices based on NDVI
        evi = 2.5 * (ndvi_mean * 1.2)  # EVI is typically higher than NDVI
        savi = ndvi_mean * 1.1  # SAVI accounts for soil
        ndwi = 0.1 + random.random() * 0.3  # Water index (0.1-0.4)
        lai = ndvi_mean * 3.5  # LAI estimation

        # Canopy cover estimation
        canopy_cover = min(95, max(10, ndvi_mean * 80 + (random.random() - 0.5) * 10))

        # Biomass estimation (tons per hectare)
        biomass = canopy_cover * 0.15 + (random.random() - 0.5) * 4

        # Land cover classification
        if ndvi_mean > 0.7:
            land_cover = "dense_vegetation"
        elif ndvi_mean > 0.5:
            land_cover = "moderate_vegetation"
        elif ndvi_mean > 0.3:
            land_cover = "sparse_vegetation"
        else:
            land_cover = "bare_soil"

        # EUDR-specific checks
        deforestation_detected = False
        canopy_change = 0.0

        # Check if parcel was established after 2020 (potential deforestation)
        if parcel:
            year_planted = getattr(parcel, 'year_coffee_first_planted', None)
            if year_planted and year_planted > 2020:
                # Simulate potential deforestation for post-2020 parcels
                deforestation_detected = random.random() < 0.3  # 30% chance
                canopy_change = -15 - random.random() * 20 if deforestation_detected else 0

        # Enhanced analysis with tree/crop differentiation
        tree_cover = canopy_cover * 0.6  # Trees typically contribute more to canopy
        crop_cover = canopy_cover * 0.4  # Crops contribute less in agroforestry systems
        bare_soil = max(0, 100 - canopy_cover)

        # Tree health assessment
        tree_health_score = min(10, max(1, (ndvi_mean * 8) + (canopy_cover / 10)))
        crop_health_score = min(10, max(1, (ndvi_mean * 7) + (crop_cover / 10)))

        # Enhanced biomass calculation considering trees vs crops
        tree_biomass = tree_cover * 0.2  # Trees store more biomass per area
        crop_biomass = crop_cover * 0.05  # Crops store less
        total_biomass = tree_biomass + crop_biomass

        # Carbon sequestration (trees sequester more than crops)
        tree_carbon = tree_biomass * 0.45  # Trees: ~45% carbon content
        crop_carbon = crop_biomass * 0.25  # Crops: ~25% carbon content
        total_carbon = tree_carbon + crop_carbon

        return {
            "ndvi_mean": round(ndvi_mean, 3),
            "ndvi_min": round(max(0.1, ndvi_mean - 0.15), 3),
            "ndvi_max": round(min(0.95, ndvi_mean + 0.15), 3),
            "ndvi_std_dev": round(0.05 + random.random() * 0.07, 3),
            "evi": round(evi, 3),
            "savi": round(savi, 3),
            "ndwi": round(ndwi, 3),
            "lai": round(lai, 2),
            "canopy_cover_percentage": round(canopy_cover, 1),
            "tree_cover_percentage": round(tree_cover, 1),
            "crop_cover_percentage": round(crop_cover, 1),
            "bare_soil_percentage": round(bare_soil, 1),
            "tree_density": round(tree_cover * 0.8, 1),
            "biomass_tons_hectare": round(max(0, total_biomass), 2),
            "tree_biomass_tons_hectare": round(max(0, tree_biomass), 2),
            "crop_biomass_tons_hectare": round(max(0, crop_biomass), 2),
            "carbon_stored_tons": round(total_carbon, 2),
            "carbon_sequestered_kg_year": round(total_carbon * 1000 * 0.02, 0),  # 2% annual sequestration
            "land_cover_type": land_cover,
            "land_cover_confidence": round(0.7 + random.random() * 0.25, 3),
            # Tree/crop differentiation
            "tree_health_score": round(tree_health_score, 1),
            "crop_health_score": round(crop_health_score, 1),
            "tree_count": round(tree_cover * 50, 0),  # Estimated tree count per hectare
            # EUDR compliance fields
            "deforestation_detected": deforestation_detected,
            "canopy_change_percentage": canopy_change,
            "baseline_year": 2020,
            "post_2020_deforestation": deforestation_detected,
            # Enhanced metadata
            "analysis_type": "tree_crop_differentiated",
            "seasonal_adjustment_applied": True,
            "cloud_cover_percentage": round(random.uniform(0, 30), 1)
        }

    def _calculate_risk_score(self, analysis_result: Dict) -> Dict[str, Any]:
        """Calculate deforestation and compliance risk scores based on EUDR requirements."""
        ndvi = analysis_result.get('ndvi_mean', 0.5)
        canopy_cover = analysis_result.get('canopy_cover_percentage', 50)
        deforestation_detected = analysis_result.get('deforestation_detected', False)
        canopy_change = analysis_result.get('canopy_change_percentage', 0)

        # EUDR risk scoring - prioritize deforestation detection
        risk_score = 0

        # Deforestation is the highest risk factor
        if deforestation_detected:
            risk_score += 80
            risk_level = "critical"
        elif canopy_change < -20:  # Significant canopy loss
            risk_score += 60
            risk_level = "high"
        elif ndvi < 0.3:
            risk_score += 40
            risk_level = "high"
        elif ndvi < 0.5:
            risk_score += 25
            risk_level = "medium"
        elif canopy_cover < 30:  # Low canopy cover
            risk_score += 15
            risk_level = "medium"
        else:
            risk_score += 5
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "risk_score": round(max(0, min(100, risk_score)), 1),
            "deforestation_detected": deforestation_detected,
            "canopy_change_percentage": canopy_change,
            "eudr_compliant": not deforestation_detected and risk_score < 50
        }

    def _prepare_geometry(self, boundary_geojson: Dict) -> Dict:
        """Prepare geometry for API requests."""
        return boundary_geojson

    def _geometry_to_bbox(self, geometry: Dict) -> List[float]:
        """Convert GeoJSON geometry to bounding box [min_lon, min_lat, max_lon, max_lat]."""
        # Simplified bbox calculation - in production use proper geospatial library
        return [0, 0, 0, 0]  # Placeholder


class SimulationNDVIGenerator:
    """Generate historical NDVI time series for trend analysis."""

    def generate_historical_ndvi(self, parcel_id: int, start_date: datetime, end_date: datetime, base_ndvi: float = 0.65) -> List[Dict]:
        """Generate realistic historical NDVI records."""
        records = []
        current_date = start_date

        while current_date <= end_date:
            # Seasonal variation
            day_of_year = current_date.timetuple().tm_yday
            seasonal_factor = 0.15 * math.sin(2 * math.pi * day_of_year / 365)

            # Long-term trend (slight decline to simulate degradation)
            years_elapsed = (current_date - start_date).days / 365
            trend_factor = -0.02 * years_elapsed

            # Random variation
            noise = (random.random() - 0.5) * 0.16  # Approximate normal distribution

            ndvi = max(0.1, min(0.95, base_ndvi + seasonal_factor + trend_factor + noise))

            records.append({
                "date": current_date.isoformat(),
                "ndvi": round(ndvi, 3),
                "parcel_id": parcel_id
            })

            # Next observation (every 10-15 days for satellite revisit)
            current_date += timedelta(days=random.randint(10, 16))

        return records


# Engine instance
satellite_engine = SatelliteAnalysisEngine()
ndvi_generator = SimulationNDVIGenerator()
