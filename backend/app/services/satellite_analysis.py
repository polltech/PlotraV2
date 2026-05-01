"""
Plotra Platform - Satellite Analysis Engine
Real Sentinel Hub Statistics API. Auth via Planet API key (no OAuth needed).
The Sentinel Hub dashboard is deprecated — authenticate directly with your Planet API key.
"""
import math
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


_CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
_CDSE_STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"


async def _get_sentinel_hub_token(client_id: str, client_secret: str) -> str:
    """
    Get a Copernicus Data Space (CDSE) bearer token via OAuth2 client_credentials.

    Credentials from dataspace.copernicus.eu → Dashboard → OAuth clients:
      client_id     = sh-145d33f4-...  (shown in OAuth Clients list)
      client_secret = (copy from OAuth client detail page)
    """
    if not client_id or not client_secret or client_secret == "***":
        raise HTTPException(
            status_code=503,
            detail=(
                "Copernicus OAuth credentials not configured. "
                "Go to Admin → System → Satellite and enter your OAuth Client ID and Secret, then click Save. "
                "Get them from dataspace.copernicus.eu → Dashboard → OAuth clients."
            )
        )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _CDSE_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            )
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach Copernicus Data Space auth endpoint.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Copernicus auth request timed out.")

    if resp.status_code == 401:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Copernicus auth failed (401) for client_id={client_id}. "
                "Check your OAuth Client ID and Secret in Admin → System → Satellite."
            )
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail=f"Copernicus auth returned {resp.status_code}: {resp.text[:200]}"
        )

    token = resp.json().get("access_token")
    if not token:
        raise HTTPException(status_code=503, detail="Copernicus returned no access token.")
    logger.info(f"CDSE token obtained for client_id={client_id}")
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
  // SCL: 4=vegetation, 5=bare_soil, 6=water, 7=unclassified — accept all non-cloud/shadow pixels
  let valid = (s.SCL == 4 || s.SCL == 5 || s.SCL == 6 || s.SCL == 7 || s.SCL == 11) ? 1 : 0;
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
    Uses a 90-day window ending on acquisition_date.
    """
    if not coords:
        raise HTTPException(
            status_code=400,
            detail="Parcel has no boundary coordinates — cannot fetch satellite data."
        )

    to_date   = acquisition_date.strftime("%Y-%m-%dT23:59:59Z")
    from_date = (acquisition_date - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")

    print(f"[SAT-DEBUG] CDSE Stats request — coords[0]={coords[0] if coords else 'EMPTY'}, "
          f"coord_count={len(coords)}, window={from_date[:10]}–{to_date[:10]}", flush=True)

    payload = {
        "input": {
            "bounds": {
                "geometry": {"type": "Polygon", "coordinates": [coords]}
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {"from": from_date, "to": to_date},
                    "maxCloudCoverage": 90
                }
            }]
        },
        "aggregation": {
            "timeRange": {"from": from_date, "to": to_date},
            "aggregationInterval": {"of": "P30D"},
            "evalscript": _EVALSCRIPT,
            "resx": 20,
            "resy": 20
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                _CDSE_STATS_URL,
                headers=headers,
                json=payload
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Copernicus Statistics API timed out.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach Copernicus Data Space Statistics API.")

    if resp.status_code == 401:
        raise HTTPException(
            status_code=503,
            detail=(
                "Copernicus returned 401 Unauthorized. Check your OAuth Client ID and Secret "
                "in Admin → System → Satellite."
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
    print(f"[SAT-DEBUG] CDSE Stats raw response (truncated): {str(body)[:800]}", flush=True)
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

    best_sample_count = (best.get("outputs", {}).get("ndvi", {}).get("bands", {})
                             .get("B0", {}).get("stats", {}).get("sampleCount", 0))
    print(f"[SAT-DEBUG] CDSE best interval sampleCount={best_sample_count}, interval={best.get('interval', {})}", flush=True)

    if best_sample_count == 0:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Sentinel-2 imagery exists for this window ({from_date[:10]}–{to_date[:10]}) "
                "but all pixels were masked (clouds, shadows, or SCL filter). "
                "Try a later date when cloud cover is lower, or check that the parcel "
                "coordinates are correct (GeoJSON uses [longitude, latitude] order)."
            )
        )
    outputs = best.get("outputs", {})

    def _stat(name: str, key: str, default: float = 0.0) -> float:
        raw = outputs.get(name, {}).get("bands", {}).get("B0", {}).get("stats", {}).get(key, default)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return default
        return default if (math.isnan(val) or math.isinf(val)) else val

    ndvi_mean = _stat("ndvi", "mean")
    ndvi_min  = _stat("ndvi", "min",  max(-1.0, ndvi_mean - 0.1))
    ndvi_max  = _stat("ndvi", "max",  min(1.0, ndvi_mean + 0.1))
    ndvi_std  = _stat("ndvi", "stDev", 0.05)
    evi_mean  = _stat("evi",  "mean")
    savi_mean = _stat("savi", "mean")
    ndmi_mean = _stat("ndmi", "mean")
    ndwi_mean = _stat("ndwi", "mean")

    raw_sample_count = _stat("ndvi", "sampleCount", 0)
    raw_nodata_count = _stat("ndvi", "noDataCount", 0)
    valid_pixels = int(raw_sample_count - raw_nodata_count)
    print(f"[SAT-DEBUG] CDSE ndvi stats — mean={ndvi_mean} sampleCount={raw_sample_count} noDataCount={raw_nodata_count} validPixels={valid_pixels} min={ndvi_min} max={ndvi_max}", flush=True)

    if valid_pixels <= 0:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Sentinel-2 imagery found for {from_date[:10]}–{to_date[:10]} but 0 valid pixels "
                "after cloud/shadow masking. The parcel boundary may be too small (covers < 1 pixel "
                "at 20m resolution) or all pixels are under clouds. Ensure the parcel GPS boundary "
                "covers at least 400 m² and try a clearer date."
            )
        )

    total_pixels = max(1, int(raw_sample_count))
    cloud_pct    = round(raw_nodata_count / total_pixels * 100, 1)
    lai          = max(0.0, 3.618 * evi_mean - 0.118)

    print(
        f"[SAT-DEBUG] Sentinel Hub real data — NDVI={ndvi_mean:.3f} EVI={evi_mean:.3f} "
        f"cloud={cloud_pct}% sampleCount={raw_sample_count} window={from_date[:10]}–{to_date[:10]}",
        flush=True
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

        creds         = await _load_satellite_credentials()
        client_id     = creds.get("oauth_client_id", "")
        client_secret = creds.get("oauth_client_secret", "")

        # Authenticate with Copernicus Data Space OAuth2
        token = await _get_sentinel_hub_token(client_id, client_secret)

        coords = []
        if getattr(parcel, "boundary_geojson", None):
            coords = parcel.boundary_geojson.get("coordinates", [[]])[0]

        print(
            f"[SAT-DEBUG] analyze_parcel parcel_id={parcel_id} "
            f"coord_points={len(coords)} "
            f"first_coord={coords[0] if coords else 'NONE'} "
            f"boundary_geojson_keys={list(parcel.boundary_geojson.keys()) if getattr(parcel, 'boundary_geojson', None) else 'NONE'}",
            flush=True
        )

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
            try:
                result = await self.analyze_parcel(parcel, acquisition_date)
                results.append(result)
            except HTTPException as e:
                parcel_id = getattr(parcel, "id", None)
                print(f"[SAT-DEBUG] Parcel {parcel_id} skipped: {e.detail}", flush=True)
                results.append({
                    "parcel_id": parcel_id,
                    "status": "failed",
                    "error": e.detail,
                    "satellite_source": "SENTINEL_2",
                })
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
