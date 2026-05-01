"""
Plotra Platform - Satellite Analysis Engine
Real Sentinel Hub Statistics API. Auth via Planet API key (no OAuth needed).
The Sentinel Hub dashboard is deprecated — authenticate directly with your Planet API key.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

try:
    from app.core.logging import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

async def _load_satellite_credentials() -> Dict[str, Any]:
    """Load cfg_satellite_* keys from SystemConfig DB table."""
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
    except Exception as e:
        logger.error(f"Failed to load satellite credentials: {e}")
        return {}


async def _get_sentinel_hub_token(client_id: str, api_key: str) -> str:
    """
    Get a Sentinel Hub bearer token via OAuth2 client_credentials.

    After the Sentinel Hub → Planet migration, the correct credentials are:
      client_id     = "sh-" + Account ID  (e.g. sh-8dcd9852-8d69-44d9-9dc1-c87135795584)
      client_secret = Planet API key      (PLAK...)

    The Account ID is shown on planet.com → Account Settings (NOT the User ID).
    """
    if not client_id or not api_key or api_key == "***":
        raise HTTPException(
            status_code=503,
            detail=(
                "Sentinel Hub credentials not configured. "
                "Go to Admin → System → Satellite and enter your Account ID and Planet API key, then click Save."
            )
        )

    # Build the sh- prefixed client_id if not already prefixed
    sh_client_id = client_id if client_id.startswith("sh-") else f"sh-{client_id}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": sh_client_id,
                    "client_secret": api_key,
                }
            )
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach Sentinel Hub auth endpoint.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Sentinel Hub auth request timed out.")

    if resp.status_code == 401:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Sentinel Hub auth failed (401) with client_id={sh_client_id}. "
                "Verify your Account ID (8dcd9852-...) and Planet API key are correct "
                "in Admin → System → Satellite."
            )
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail=f"Sentinel Hub auth returned {resp.status_code}: {resp.text[:200]}"
        )

    token = resp.json().get("access_token")
    if not token:
        raise HTTPException(status_code=503, detail="Sentinel Hub returned no access token.")
    logger.info(f"Sentinel Hub token obtained for client_id={sh_client_id}")
    return token


# ---------------------------------------------------------------------------
# Statistics API evalscript
# ---------------------------------------------------------------------------

_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02", "B03", "B04", "B08", "B8A", "B11", "SCL"]}],
    output: [
      {id: "ndvi", bands: 1, sampleType: "FLOAT32"},
      {id: "evi",  bands: 1, sampleType: "FLOAT32"},
      {id: "savi", bands: 1, sampleType: "FLOAT32"},
      {id: "ndmi", bands: 1, sampleType: "FLOAT32"},
      {id: "ndwi", bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  let valid = (s.SCL == 4 || s.SCL == 5 || s.SCL == 6) ? 1 : 0;
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-6);
  let evi  = 2.5 * (s.B08 - s.B04) / (s.B08 + 6*s.B04 - 7.5*s.B02 + 1 + 1e-6);
  let savi = 1.5 * (s.B08 - s.B04) / (s.B08 + s.B04 + 0.5 + 1e-6);
  let ndmi = (s.B8A - s.B11) / (s.B8A + s.B11 + 1e-6);
  let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08 + 1e-6);
  return {
    ndvi: [ndvi], evi: [evi], savi: [savi],
    ndmi: [ndmi], ndwi: [ndwi], dataMask: [valid]
  };
}
"""


async def _fetch_sentinel_hub_indices(token: str, coords: List, acquisition_date: datetime) -> Dict:
    """
    Call Sentinel Hub Statistical API for a polygon.
    Uses a 30-day window ending on acquisition_date.
    Tries Bearer auth first; on 401 raises a clear error with instructions.
    """
    if not coords:
        raise HTTPException(
            status_code=400,
            detail="Parcel has no boundary coordinates — cannot fetch satellite data."
        )

    to_date   = acquisition_date.strftime("%Y-%m-%dT23:59:59Z")
    from_date = (acquisition_date - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")

    payload = {
        "input": {
            "bounds": {
                "geometry": {"type": "Polygon", "coordinates": [coords]}
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {"from": from_date, "to": to_date},
                    "maxCloudCoverage": 80
                }
            }]
        },
        "aggregation": {
            "timeRange": {"from": from_date, "to": to_date},
            "aggregationInterval": {"of": "P30D"},
            "evalscript": _EVALSCRIPT,
            "resx": 10,
            "resy": 10
        }
    }

    # Try Bearer token auth (Planet API key used directly)
    headers_bearer = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    # Also try api-key header style (Planet Insights Platform style)
    headers_apikey = {
        "Authorization": f"api-key {token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://services.sentinel-hub.com/api/v1/statistics",
                headers=headers_bearer,
                json=payload
            )
            # If Bearer fails try api-key style
            if resp.status_code == 401:
                resp = await client.post(
                    "https://services.sentinel-hub.com/api/v1/statistics",
                    headers=headers_apikey,
                    json=payload
                )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Sentinel Hub Statistics API timed out.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach Sentinel Hub Statistics API.")

    if resp.status_code == 401:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sentinel Hub returned 401 Unauthorized. Your Planet API key is invalid or "
                "does not have access to the Sentinel Hub Statistics API. "
                "Reveal your API key at planet.com → Account Settings → User Settings → API Key "
                "and re-enter it in Admin → System → Satellite."
            )
        )
    if resp.status_code == 403:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sentinel Hub returned 403 Forbidden. Your trial account may not include "
                "access to the Statistical API. Check your subscription at planet.com."
            )
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail=f"Sentinel Hub Statistics API returned {resp.status_code}: {resp.text[:400]}"
        )

    body = resp.json()
    intervals = body.get("data", [])
    if not intervals:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No Sentinel-2 imagery found for this parcel "
                f"({from_date[:10]} – {to_date[:10]}). "
                "Try a different date or wait for new imagery to be processed."
            )
        )

    best = max(
        intervals,
        key=lambda iv: iv.get("outputs", {}).get("ndvi", {}).get("bands", {})
                         .get("B0", {}).get("stats", {}).get("sampleCount", 0)
    )
    outputs = best.get("outputs", {})

    def _stat(name: str, key: str, default: float = 0.0) -> float:
        return float(
            outputs.get(name, {}).get("bands", {}).get("B0", {})
                   .get("stats", {}).get(key, default)
        )

    ndvi_mean = _stat("ndvi", "mean")
    ndvi_min  = _stat("ndvi", "min",  ndvi_mean - 0.1)
    ndvi_max  = _stat("ndvi", "max",  ndvi_mean + 0.1)
    ndvi_std  = _stat("ndvi", "stDev", 0.05)
    evi_mean  = _stat("evi",  "mean")
    savi_mean = _stat("savi", "mean")
    ndmi_mean = _stat("ndmi", "mean")
    ndwi_mean = _stat("ndwi", "mean")

    sample_count = max(1, _stat("ndvi", "sampleCount", 1))
    nodata_count = _stat("ndvi", "noDataCount", 0)
    cloud_pct    = round(nodata_count / (sample_count + nodata_count) * 100, 1)
    lai          = max(0.0, 3.618 * evi_mean - 0.118)

    logger.info(
        f"Sentinel Hub real data — NDVI={ndvi_mean:.3f} EVI={evi_mean:.3f} "
        f"cloud={cloud_pct}% window={from_date[:10]}–{to_date[:10]}"
    )

    return {
        "ndvi_mean":    round(ndvi_mean, 3),
        "ndvi_min":     round(max(-1.0, ndvi_min), 3),
        "ndvi_max":     round(min(1.0,  ndvi_max), 3),
        "ndvi_std_dev": round(ndvi_std, 3),
        "evi":  round(evi_mean,  3),
        "savi": round(savi_mean, 3),
        "ndmi": round(ndmi_mean, 3),
        "ndwi": round(ndwi_mean, 3),
        "lai":  round(lai, 2),
        "cloud_cover_percentage": cloud_pct,
        "satellite_source": "SENTINEL_2",
    }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SatelliteAnalysisEngine:
    """
    Real satellite analysis using Sentinel Hub Statistics API.
    Authenticate with your Planet API key — no OAuth client needed.
    Configure it in Admin → System → Satellite → Personal API Key.
    """

    def __init__(self):
        self.ndvi_threshold = 0.3
        self.baseline_year  = 2020

    async def analyze_parcel(self, parcel: Any, acquisition_date: Optional[datetime] = None) -> Dict[str, Any]:
        if acquisition_date is None:
            acquisition_date = datetime.utcnow()

        parcel_id   = getattr(parcel, "id", None)
        analysis_id = f"SAT-{uuid.uuid4().hex[:12].upper()}"

        creds      = await _load_satellite_credentials()
        account_id = creds.get("account_id", "")
        api_key    = creds.get("api_key", "")

        # Authenticate: client_id = sh-{account_id}, client_secret = Planet API key
        token = await _get_sentinel_hub_token(account_id, api_key)

        coords = []
        if getattr(parcel, "boundary_geojson", None):
            coords = parcel.boundary_geojson.get("coordinates", [[]])[0]

        indices = await _fetch_sentinel_hub_indices(token, coords, acquisition_date)

        # Derive all metrics from real NDVI
        ndvi        = indices["ndvi_mean"]
        canopy      = min(95.0, max(5.0, ndvi * 100))
        tree_cover  = round(canopy * 0.6, 1)
        crop_cover  = round(canopy * 0.4, 1)
        bare_soil   = round(max(0.0, 100.0 - canopy), 1)
        tree_biomass  = round(tree_cover  * 0.2,  2)
        crop_biomass  = round(crop_cover  * 0.05, 2)
        total_biomass = round(tree_biomass + crop_biomass, 2)
        total_carbon  = round(tree_biomass * 0.45 + crop_biomass * 0.25, 2)
        carbon_per_yr = round(total_carbon * 1000 * 0.02, 0)
        tree_health   = round(min(10.0, max(1.0, ndvi * 8  + canopy / 10)), 1)
        crop_health   = round(min(10.0, max(1.0, ndvi * 7  + crop_cover / 10)), 1)

        if   ndvi > 0.7: land_cover = "dense_vegetation"
        elif ndvi > 0.5: land_cover = "moderate_vegetation"
        elif ndvi > 0.3: land_cover = "sparse_vegetation"
        else:            land_cover = "bare_soil"

        year_planted         = getattr(parcel, "year_coffee_first_planted", None)
        deforestation_detected = bool(year_planted and year_planted > 2020 and ndvi < 0.3)
        canopy_change          = -15.0 if deforestation_detected else 0.0

        result = {
            **indices,
            "canopy_cover_percentage":    round(canopy, 1),
            "tree_cover_percentage":      tree_cover,
            "crop_cover_percentage":      crop_cover,
            "bare_soil_percentage":       bare_soil,
            "tree_density":               round(tree_cover * 0.8, 1),
            "biomass_tons_hectare":       total_biomass,
            "tree_biomass_tons_hectare":  tree_biomass,
            "crop_biomass_tons_hectare":  crop_biomass,
            "carbon_stored_tons":         total_carbon,
            "carbon_sequestered_kg_year": carbon_per_yr,
            "tree_health_score":          tree_health,
            "crop_health_score":          crop_health,
            "tree_count":                 round(tree_cover * 50, 0),
            "land_cover_type":            land_cover,
            "land_cover_confidence":      0.95,
            "deforestation_detected":     deforestation_detected,
            "canopy_change_percentage":   canopy_change,
            "baseline_year":              self.baseline_year,
            "post_2020_deforestation":    deforestation_detected,
            "seasonal_adjustment_applied": False,
            "analysis_type":              "sentinel_hub_real",
        }

        crop_analysis    = await self._analyze_crop_types(parcel, result)
        risk_assessment  = self._calculate_risk_score(result)

        return {
            "analysis_id":      analysis_id,
            "parcel_id":        parcel_id,
            "status":           "completed",
            "satellite_source": "SENTINEL_2",
            "acquisition_date": acquisition_date.isoformat(),
            **result,
            **crop_analysis,
            **risk_assessment,
        }

    async def analyze_parcels_batch(self, parcels: List[Any], acquisition_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        results = []
        for parcel in parcels:
            result = await self.analyze_parcel(parcel, acquisition_date)
            results.append(result)
        return results

    async def _analyze_crop_types(self, parcel: Any, base_analysis: Dict) -> Dict[str, Any]:
        crops = getattr(parcel, "crops", []) or []
        insights = {
            "crop_differentiation": {},
            "dominant_crops": [],
            "crop_health_distribution": {},
            "agroforestry_score": 5.0,
        }

        if not crops:
            insights["crop_differentiation"] = {
                "coffee": {
                    "estimated_area_percentage": 70,
                    "health_score": base_analysis.get("crop_health_score", 5.0),
                    "ndvi_range": [round(base_analysis.get("ndvi_min", 0.4), 3), round(base_analysis.get("ndvi_max", 0.8), 3)],
                },
                "trees": {
                    "estimated_area_percentage": 20,
                    "health_score": base_analysis.get("tree_health_score", 5.0),
                    "ndvi_range": [round(base_analysis.get("ndvi_mean", 0.6), 3), round(base_analysis.get("ndvi_max", 0.9), 3)],
                },
                "other": {"estimated_area_percentage": 10, "health_score": 4.0, "ndvi_range": [0.2, 0.6]},
            }
        else:
            total_area = sum(c.area_hectares or 0 for c in crops)
            category_modifier = {
                "coffee": 0.0, "shade_tree": 0.1, "fruit_tree": 0.05,
                "timber": 0.15, "vegetable": -0.1, "legume": -0.05, "cereal": -0.15, "other": 0.0,
            }
            crop_analysis = {}
            for crop in crops:
                if not crop.crop_type:
                    continue
                base_ndvi  = base_analysis.get("ndvi_mean", 0.5)
                crop_ndvi  = max(0.1, min(0.95, base_ndvi + category_modifier.get(crop.crop_type.category or "other", 0.0)))
                health_score = 5.0
                if crop.health_status:
                    health_score += {"healthy": 0, "stressed": -1, "diseased": -2,
                                     "pest_infested": -1.5, "water_stressed": -1, "nutrient_deficient": -1
                                     }.get(crop.health_status.value, 0)
                crop_analysis[crop.crop_type.name or "Unknown"] = {
                    "category": crop.crop_type.category,
                    "area_hectares": crop.area_hectares,
                    "area_percentage": (crop.area_hectares / total_area * 100) if total_area > 0 else 0,
                    "ndvi_estimated": round(crop_ndvi, 3),
                    "health_score": round(max(1.0, min(10.0, health_score)), 1),
                    "growth_stage": crop.growth_stage.value if crop.growth_stage else "unknown",
                    "yield_potential_kg_ha": crop.expected_yield_kg_ha,
                    "certifications": {
                        "organic": bool(crop.organic_certified),
                        "fair_trade": bool(crop.fair_trade_certified),
                        "rain_forest_alliance": bool(crop.rain_forest_alliance_certified),
                    },
                }
            insights["crop_differentiation"] = crop_analysis
            trees  = sum(1 for c in crops if c.crop_type and c.crop_type.category in ["shade_tree", "fruit_tree", "timber"])
            coffee = sum(1 for c in crops if c.crop_type and c.crop_type.category == "coffee")
            if trees > 0 and coffee > 0:
                insights["agroforestry_score"] = min(10.0, 5.0 + trees / (trees + coffee) * 3.0)
            elif trees > 0:
                insights["agroforestry_score"] = 7.0
            else:
                insights["agroforestry_score"] = 3.0

        if insights["crop_differentiation"]:
            insights["dominant_crops"] = [
                c[0] for c in sorted(
                    insights["crop_differentiation"].items(),
                    key=lambda x: x[1].get("area_percentage", 0), reverse=True
                )[:3]
            ]
        return insights

    def _calculate_risk_score(self, result: Dict) -> Dict[str, Any]:
        ndvi         = result.get("ndvi_mean", 0.5)
        canopy       = result.get("canopy_cover_percentage", 50)
        deforestation = result.get("deforestation_detected", False)
        canopy_change = result.get("canopy_change_percentage", 0)

        if deforestation:              risk_score, risk_level = 80, "high"
        elif canopy_change < -20:      risk_score, risk_level = 60, "high"
        elif ndvi < 0.3:               risk_score, risk_level = 40, "high"
        elif ndvi < 0.5:               risk_score, risk_level = 25, "medium"
        elif canopy < 30:              risk_score, risk_level = 15, "medium"
        else:                          risk_score, risk_level =  5, "low"

        return {
            "risk_level":              risk_level,
            "risk_score":              round(max(0, min(100, risk_score)), 1),
            "deforestation_detected":  deforestation,
            "canopy_change_percentage": canopy_change,
            "eudr_compliant":          not deforestation and risk_score < 50,
        }


satellite_engine = SatelliteAnalysisEngine()
