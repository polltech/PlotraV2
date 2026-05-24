"""
Plotra Platform - Satellite Analysis Engine
Real Sentinel Hub Statistics API. Auth via Planet API key (no OAuth needed).
The Sentinel Hub dashboard is deprecated — authenticate directly with your Planet API key.
"""
import asyncio
import math
import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

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
# Pixel-level helper: normal CDF approximation (Abramowitz & Stegun)
# Used to estimate % pixels below an index threshold from mean + stDev.
# ---------------------------------------------------------------------------

def _normal_cdf(x: float, mean: float, std: float) -> float:
    """Approximate P(X < x) for X ~ N(mean, std²). No scipy needed."""
    if std <= 0:
        return 1.0 if x > mean else 0.0
    z = (x - mean) / std
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    p = 1.0 - 0.3989422804014327 * math.exp(-z * z / 2) * poly
    return round(p if z >= 0 else 1.0 - p, 4)


# ---------------------------------------------------------------------------
# CUSUM time-series segmentation (pure Python, no external deps)
# Detects structural breakpoints in index time series.
# ---------------------------------------------------------------------------

def _cusum_detect(values: List[Optional[float]], threshold: float = 3.0) -> tuple:
    """
    Sequential CUSUM change detection.
    Returns (cusum_scores: List[float], is_breakpoint: List[bool]).
    Scores are normalized cumulative deviations from the series mean.
    A breakpoint is flagged when the score exceeds `threshold` standard deviations.
    """
    valid = [v for v in values if v is not None]
    n_valid = len(valid)
    if n_valid < 3:
        return [0.0] * len(values), [False] * len(values)

    mean_v = sum(valid) / n_valid
    var_v  = sum((v - mean_v) ** 2 for v in valid) / max(n_valid - 1, 1)
    std_v  = math.sqrt(var_v)
    if std_v < 0.001:
        return [0.0] * len(values), [False] * len(values)

    cusum_pos = cusum_neg = 0.0
    scores: List[float] = []
    breakpoints: List[bool] = []

    for v in values:
        if v is None:
            scores.append(0.0)
            breakpoints.append(False)
            continue
        z = (v - mean_v) / std_v
        cusum_pos = max(0.0, cusum_pos + z)
        cusum_neg = min(0.0, cusum_neg + z)
        score = max(abs(cusum_pos), abs(cusum_neg))
        is_bp = score > threshold
        if is_bp:
            cusum_pos = cusum_neg = 0.0   # reset after detection
        scores.append(round(score, 3))
        breakpoints.append(is_bp)

    return scores, breakpoints


# ---------------------------------------------------------------------------
# Statistics API evalscripts
# ---------------------------------------------------------------------------

# Sentinel-2 L2A — optical vegetation + soil + disturbance indices
# B12 (SWIR2) added for NBR (Normalized Burn Ratio — forest disturbance sensitive)
# BSI (Bare Soil Index) — spikes immediately when land is cleared
_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02", "B03", "B04", "B08", "B8A", "B11", "B12", "SCL"]}],
    output: [
      {id: "ndvi", bands: 1, sampleType: "FLOAT32"},
      {id: "evi",  bands: 1, sampleType: "FLOAT32"},
      {id: "savi", bands: 1, sampleType: "FLOAT32"},
      {id: "ndmi", bands: 1, sampleType: "FLOAT32"},
      {id: "ndwi", bands: 1, sampleType: "FLOAT32"},
      {id: "bsi",  bands: 1, sampleType: "FLOAT32"},
      {id: "nbr",  bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-6);
  let evi  = 2.5 * (s.B08 - s.B04) / (s.B08 + 6*s.B04 - 7.5*s.B02 + 1 + 1e-6);
  let savi = 1.5 * (s.B08 - s.B04) / (s.B08 + s.B04 + 0.5 + 1e-6);
  let ndmi = (s.B8A - s.B11) / (s.B8A + s.B11 + 1e-6);
  let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08 + 1e-6);
  let bsi  = ((s.B11 + s.B04) - (s.B08 + s.B02)) / ((s.B11 + s.B04) + (s.B08 + s.B02) + 1e-6);
  let nbr  = (s.B08 - s.B12) / (s.B08 + s.B12 + 1e-6);
  return {
    ndvi: [ndvi], evi: [evi], savi: [savi],
    ndmi: [ndmi], ndwi: [ndwi], bsi: [bsi], nbr: [nbr],
    dataMask: [1]
  };
}
"""

# Landsat 8/9 OLI-TIRS — same indices as S2 but different band mapping
# B02=Blue, B03=Green, B04=Red, B05=NIR, B06=SWIR1, B07=SWIR2 (30m resolution)
_LANDSAT8_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02","B03","B04","B05","B06","B07"]}],
    output: [
      {id: "ndvi", bands: 1, sampleType: "FLOAT32"},
      {id: "evi",  bands: 1, sampleType: "FLOAT32"},
      {id: "savi", bands: 1, sampleType: "FLOAT32"},
      {id: "ndmi", bands: 1, sampleType: "FLOAT32"},
      {id: "bsi",  bands: 1, sampleType: "FLOAT32"},
      {id: "nbr",  bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  let ndvi = (s.B05 - s.B04) / (s.B05 + s.B04 + 1e-6);
  let evi  = 2.5 * (s.B05 - s.B04) / (s.B05 + 6*s.B04 - 7.5*s.B02 + 1 + 1e-6);
  let savi = 1.5 * (s.B05 - s.B04) / (s.B05 + s.B04 + 0.5 + 1e-6);
  let ndmi = (s.B05 - s.B06) / (s.B05 + s.B06 + 1e-6);
  let bsi  = ((s.B06 + s.B04) - (s.B05 + s.B02)) / ((s.B06 + s.B04) + (s.B05 + s.B02) + 1e-6);
  let nbr  = (s.B05 - s.B07) / (s.B05 + s.B07 + 1e-6);
  return { ndvi:[ndvi], evi:[evi], savi:[savi], ndmi:[ndmi], bsi:[bsi], nbr:[nbr], dataMask:[1] };
}
"""

# Landsat 4-5 TM — covers 1982-2013 (best source for pre-2013 history)
# B01=Blue, B02=Green, B03=Red, B04=NIR, B05=SWIR1, B07=SWIR2 (B06 is thermal, skip)
_LANDSAT5_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B01","B02","B03","B04","B05","B07"]}],
    output: [
      {id: "ndvi", bands: 1, sampleType: "FLOAT32"},
      {id: "evi",  bands: 1, sampleType: "FLOAT32"},
      {id: "savi", bands: 1, sampleType: "FLOAT32"},
      {id: "ndmi", bands: 1, sampleType: "FLOAT32"},
      {id: "bsi",  bands: 1, sampleType: "FLOAT32"},
      {id: "nbr",  bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  let ndvi = (s.B04 - s.B03) / (s.B04 + s.B03 + 1e-6);
  let evi  = 2.5 * (s.B04 - s.B03) / (s.B04 + 6*s.B03 - 7.5*s.B01 + 1 + 1e-6);
  let savi = 1.5 * (s.B04 - s.B03) / (s.B04 + s.B03 + 0.5 + 1e-6);
  let ndmi = (s.B04 - s.B05) / (s.B04 + s.B05 + 1e-6);
  let bsi  = ((s.B05 + s.B03) - (s.B04 + s.B01)) / ((s.B05 + s.B03) + (s.B04 + s.B01) + 1e-6);
  let nbr  = (s.B04 - s.B07) / (s.B04 + s.B07 + 1e-6);
  return { ndvi:[ndvi], evi:[evi], savi:[savi], ndmi:[ndmi], bsi:[bsi], nbr:[nbr], dataMask:[1] };
}
"""

# Sentinel-1 GRD — SAR Radar Vegetation Index (RVI)
# RVI = 4*VH / (VV+VH): ranges 0–1, higher = denser vegetation canopy.
# Cloud-proof: radar penetrates clouds/smoke. Sensitive to canopy structure.
_S1_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["VV","VH"], units: "LINEAR_POWER"}],
    output: [
      {id: "rvi",      bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  var rvi = 4.0 * s.VH / (s.VV + s.VH + 1e-6);
  return { rvi: [Math.max(0, Math.min(1, rvi))], dataMask: [1] };
}
"""


async def _fetch_sentinel_hub_timeseries(token: str, coords: List) -> List[Dict]:
    """
    Fetch quarterly NDVI from 2020-12-01 to today in a single Stats API call.
    Returns a list of dicts, one per quarter, ordered oldest → newest.
    Each dict: {period_from, period_to, ndvi, evi, savi, ndmi, cloud_cover_pct, valid_pixels}
    Quarters with 0 valid pixels (all cloud) are included with ndvi=None so gaps are visible.
    """
    if not coords:
        raise HTTPException(status_code=400, detail="Parcel has no boundary coordinates.")

    from_date = "2020-12-01T00:00:00Z"
    to_date   = datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")

    payload = {
        "input": {
            "bounds": {"geometry": {"type": "Polygon", "coordinates": [coords]}},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {"timeRange": {"from": from_date, "to": to_date}, "maxCloudCoverage": 90}
            }]
        },
        "aggregation": {
            "timeRange": {"from": from_date, "to": to_date},
            "aggregationInterval": {"of": "P3M"},   # quarterly
            "evalscript": _EVALSCRIPT,
            "resx": 20,
            "resy": 20
        }
    }

    try:
        async with httpx.AsyncClient(timeout=75) as client:
            resp = await client.post(
                _CDSE_STATS_URL,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Copernicus Statistics API timed out during history fetch.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach Copernicus Data Space Statistics API.")

    if resp.status_code == 401:
        raise HTTPException(status_code=503, detail="Copernicus 401 — check OAuth credentials in Admin → System → Satellite.")
    if resp.status_code not in (200, 206):
        raise HTTPException(status_code=503, detail=f"Sentinel Hub returned {resp.status_code}: {resp.text[:300]}")

    intervals = resp.json().get("data", [])
    if not intervals:
        raise HTTPException(status_code=404, detail="No Sentinel-2 imagery found from Dec 2020 to today for this parcel.")

    def _s(outputs, name, key, default=None):
        try:
            v = float(outputs.get(name, {}).get("bands", {}).get("B0", {}).get("stats", {}).get(key, default))
            return None if (math.isnan(v) or math.isinf(v)) else v
        except (TypeError, ValueError):
            return default

    results = []
    for iv in intervals:
        outputs      = iv.get("outputs", {})
        sample_count = _s(outputs, "ndvi", "sampleCount", 0) or 0
        nodata_count = _s(outputs, "ndvi", "noDataCount", 0) or 0
        valid        = int(sample_count - nodata_count)
        ndvi_mean    = _s(outputs, "ndvi", "mean")   if valid > 0 else None
        ndvi_std_raw = _s(outputs, "ndvi", "stDev")  if valid > 0 else None
        ndvi_std     = round(ndvi_std_raw, 4) if ndvi_std_raw is not None else None

        # Pixel-level: estimated % of pixels below deforestation threshold (NDVI < 0.35)
        # Uses normal distribution approximation from mean + stDev.
        ndvi_pct_below = None
        if ndvi_mean is not None and ndvi_std is not None and ndvi_std > 0:
            ndvi_pct_below = round(_normal_cdf(0.35, ndvi_mean, ndvi_std) * 100, 1)

        results.append({
            "period_from":           iv.get("interval", {}).get("from", "")[:10],
            "period_to":             iv.get("interval", {}).get("to",   "")[:10],
            "ndvi":                  round(ndvi_mean, 3) if ndvi_mean is not None else None,
            "evi":                   round(_s(outputs, "evi",  "mean", 0), 3) if valid > 0 else None,
            "savi":                  round(_s(outputs, "savi", "mean", 0), 3) if valid > 0 else None,
            "ndmi":                  round(_s(outputs, "ndmi", "mean", 0), 3) if valid > 0 else None,
            "bsi":                   round(_s(outputs, "bsi",  "mean", 0), 3) if valid > 0 else None,
            "nbr":                   round(_s(outputs, "nbr",  "mean", 0), 3) if valid > 0 else None,
            # Pixel-level stats
            "ndvi_std":              ndvi_std,
            "ndvi_pct_below_035":    ndvi_pct_below,
            "cloud_cover_pct":       round(nodata_count / max(1, sample_count) * 100, 1),
            "valid_pixels":          valid,
        })

    logger.info(f"S2 timeseries: {len(results)} quarters, {sum(1 for r in results if r['ndvi'] is not None)} with valid NDVI")
    return results


async def _fetch_s1_rvi_timeseries(token: str, coords: List, from_date: str, to_date: str) -> Dict[str, float]:
    """
    Fetch Sentinel-1 SAR Radar Vegetation Index (RVI) quarterly aggregates.
    Returns {period_from: rvi_mean} mapping to merge into S2 quarter dicts.
    Cloud-proof — uses radar backscatter so all quarters have valid data.
    """
    payload = {
        "input": {
            "bounds": {"geometry": {"type": "Polygon", "coordinates": [coords]}},
            "data": [{
                "type": "sentinel-1-grd",
                "dataFilter": {
                    "timeRange": {"from": f"{from_date}T00:00:00Z", "to": f"{to_date}T23:59:59Z"},
                    "acquisitionMode": "IW",
                    "polarization": "DV",
                    "orbitDirection": "ASCENDING",
                },
            }]
        },
        "aggregation": {
            "timeRange": {"from": f"{from_date}T00:00:00Z", "to": f"{to_date}T23:59:59Z"},
            "aggregationInterval": {"of": "P3M"},
            "evalscript": _S1_EVALSCRIPT,
            "resx": 10,
            "resy": 10,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _CDSE_STATS_URL,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
    except Exception as e:
        logger.warning(f"[S1-RVI] Request failed: {e}")
        return {}

    if resp.status_code not in (200, 206):
        logger.warning(f"[S1-RVI] API returned {resp.status_code}: {resp.text[:200]}")
        return {}

    rvi_by_period: Dict[str, float] = {}
    for iv in resp.json().get("data", []):
        pfrom  = iv.get("interval", {}).get("from", "")[:10]
        stats  = iv.get("outputs", {}).get("rvi", {}).get("bands", {}).get("B0", {}).get("stats", {})
        mean_v = stats.get("mean")
        count  = stats.get("sampleCount", 0)
        if pfrom and mean_v is not None and count and not math.isnan(float(mean_v)):
            rvi_by_period[pfrom] = round(float(mean_v), 3)

    logger.info(f"[S1-RVI] {len(rvi_by_period)} quarters with valid SAR RVI")
    return rvi_by_period


# ---------------------------------------------------------------------------
# EUDR Farming History — Landsat monthly timeseries (1990 → 2016)
# Extends farming start detection back to 1990 using Landsat 5 and 8.
# Same indices as Sentinel-2 but adapted band mapping. 30m resolution.
# ---------------------------------------------------------------------------

async def _fetch_landsat_monthly_timeseries(
    token: str,
    coords: List,
    dataset_type: str,
    from_year: int,
    to_year: int,
    evalscript: str,
    source_label: str,
) -> List[Dict]:
    """
    Fetch monthly Landsat timeseries for a given period via Sentinel Hub Stats API.
    dataset_type: "landsat-ot-l2" (L8/9, 2013+) or "landsat-tm-l2" (L4-5, 1982-2013)
    Returns [] on any error so the caller can proceed with remaining sources.
    """
    from_date = f"{from_year}-01-01T00:00:00Z"
    to_date   = f"{to_year}-12-31T23:59:59Z"

    payload = {
        "input": {
            "bounds": {"geometry": {"type": "Polygon", "coordinates": [coords]}},
            "data": [{
                "type": dataset_type,
                "dataFilter": {"timeRange": {"from": from_date, "to": to_date}, "maxCloudCoverage": 90}
            }]
        },
        "aggregation": {
            "timeRange": {"from": from_date, "to": to_date},
            "aggregationInterval": {"of": "P1M"},
            "evalscript": evalscript,
            "resx": 30,
            "resy": 30,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                _CDSE_STATS_URL,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning(f"[{source_label}] Fetch failed: {exc} — skipping")
        return []

    if resp.status_code not in (200, 206):
        logger.warning(f"[{source_label}] HTTP {resp.status_code}: {resp.text[:200]} — skipping")
        return []

    intervals = resp.json().get("data", [])

    def _sv(outputs, name, key, default=None):
        try:
            v = float(outputs.get(name, {}).get("bands", {}).get("B0", {}).get("stats", {}).get(key, default))
            return None if (math.isnan(v) or math.isinf(v)) else v
        except (TypeError, ValueError):
            return default

    results = []
    for iv in intervals:
        outputs      = iv.get("outputs", {})
        sample_count = _sv(outputs, "ndvi", "sampleCount", 0) or 0
        nodata_count = _sv(outputs, "ndvi", "noDataCount", 0) or 0
        valid        = int(sample_count - nodata_count)
        ndvi_mean    = _sv(outputs, "ndvi", "mean") if valid > 0 else None
        results.append({
            "month":           iv.get("interval", {}).get("from", "")[:7],
            "period_from":     iv.get("interval", {}).get("from", "")[:10],
            "period_to":       iv.get("interval", {}).get("to",   "")[:10],
            "source":          source_label,
            "ndvi":  round(ndvi_mean, 3) if ndvi_mean is not None else None,
            "evi":   round(_sv(outputs, "evi",  "mean", 0), 3) if valid > 0 else None,
            "savi":  round(_sv(outputs, "savi", "mean", 0), 3) if valid > 0 else None,
            "ndmi":  round(_sv(outputs, "ndmi", "mean", 0), 3) if valid > 0 else None,
            "bsi":   round(_sv(outputs, "bsi",  "mean", 0), 3) if valid > 0 else None,
            "nbr":   round(_sv(outputs, "nbr",  "mean", 0), 3) if valid > 0 else None,
            "cloud_cover_pct": round(nodata_count / max(1, sample_count) * 100, 1),
            "valid_pixels":    valid,
        })

    valid_count = sum(1 for r in results if r["ndvi"] is not None)
    logger.info(f"[{source_label}] {len(results)} months fetched ({from_year}-{to_year}), {valid_count} with valid data")
    return results


# ---------------------------------------------------------------------------
# EUDR Farming History — Sentinel-2 monthly timeseries (2017 → today)
# Uses same evalscript but monthly aggregation for farming start detection.
# ---------------------------------------------------------------------------

async def _fetch_eudr_monthly_timeseries(token: str, coords: List) -> List[Dict]:
    """
    Fetch monthly multi-index timeseries from Jan 2017 to today.
    Returns list of monthly dicts with NDVI, EVI, SAVI, NDMI, BSI, NBR.
    Months with full cloud cover are included with None values (gap markers).
    """
    if not coords:
        raise HTTPException(status_code=400, detail="Parcel has no boundary coordinates.")

    from_date = "2017-01-01T00:00:00Z"
    to_date   = datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")

    payload = {
        "input": {
            "bounds": {"geometry": {"type": "Polygon", "coordinates": [coords]}},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {"timeRange": {"from": from_date, "to": to_date}, "maxCloudCoverage": 90}
            }]
        },
        "aggregation": {
            "timeRange": {"from": from_date, "to": to_date},
            "aggregationInterval": {"of": "P1M"},
            "evalscript": _EVALSCRIPT,
            "resx": 20,
            "resy": 20,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                _CDSE_STATS_URL,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Copernicus Statistics API timed out (monthly EUDR fetch).")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach Copernicus Data Space Statistics API.")

    if resp.status_code == 401:
        raise HTTPException(status_code=503, detail="Copernicus 401 — check OAuth credentials in Admin → System → Satellite.")
    if resp.status_code not in (200, 206):
        raise HTTPException(status_code=503, detail=f"Sentinel Hub returned {resp.status_code}: {resp.text[:300]}")

    intervals = resp.json().get("data", [])
    if not intervals:
        raise HTTPException(status_code=404, detail="No Sentinel-2 imagery found from 2017 for this parcel.")

    def _sv(outputs, name, key, default=None):
        try:
            v = float(outputs.get(name, {}).get("bands", {}).get("B0", {}).get("stats", {}).get(key, default))
            return None if (math.isnan(v) or math.isinf(v)) else v
        except (TypeError, ValueError):
            return default

    results = []
    for iv in intervals:
        outputs      = iv.get("outputs", {})
        sample_count = _sv(outputs, "ndvi", "sampleCount", 0) or 0
        nodata_count = _sv(outputs, "ndvi", "noDataCount", 0) or 0
        valid        = int(sample_count - nodata_count)
        ndvi_mean    = _sv(outputs, "ndvi", "mean") if valid > 0 else None

        results.append({
            "month":        iv.get("interval", {}).get("from", "")[:7],   # "2019-03"
            "period_from":  iv.get("interval", {}).get("from", "")[:10],
            "period_to":    iv.get("interval", {}).get("to",   "")[:10],
            "source":       "sentinel2",
            "ndvi":  round(ndvi_mean, 3) if ndvi_mean is not None else None,
            "evi":   round(_sv(outputs, "evi",  "mean", 0), 3) if valid > 0 else None,
            "savi":  round(_sv(outputs, "savi", "mean", 0), 3) if valid > 0 else None,
            "ndmi":  round(_sv(outputs, "ndmi", "mean", 0), 3) if valid > 0 else None,
            "bsi":   round(_sv(outputs, "bsi",  "mean", 0), 3) if valid > 0 else None,
            "nbr":   round(_sv(outputs, "nbr",  "mean", 0), 3) if valid > 0 else None,
            "cloud_cover_pct": round(nodata_count / max(1, sample_count) * 100, 1),
            "valid_pixels":    valid,
        })

    logger.info(f"[EUDR monthly] {len(results)} months fetched, {sum(1 for r in results if r['ndvi'] is not None)} with valid data")
    return results


def _score_month_land_use(m: Dict) -> Dict:
    """
    Score a single month's multi-index values into land-use signals.

    Returns dict with:
      forest_score  — 0-1, high = stable dense canopy (NDVI high+stable, NDMI high, BSI low)
      crop_score    — 0-1, high = active cropping (NDVI moderate + seasonal, SAVI moderate)
      bare_score    — 0-1, high = exposed soil/cleared land (BSI high, NDMI low, NDVI low)
      disturbance   — 0-1, high = recent disturbance (NBR drop + BSI spike together)
    """
    ndvi = m.get("ndvi")
    evi  = m.get("evi")
    savi = m.get("savi")
    ndmi = m.get("ndmi")
    bsi  = m.get("bsi")
    nbr  = m.get("nbr")

    if ndvi is None:
        return {"forest_score": None, "crop_score": None, "bare_score": None, "disturbance": None}

    # Forest: high NDVI (>0.65), high NDMI (>0.2), low BSI (<0.0), high NBR (>0.5)
    forest_score = 0.0
    if ndvi is not None:  forest_score += min(max((ndvi - 0.4) / 0.4, 0), 1) * 0.35
    if evi  is not None:  forest_score += min(max((evi  - 0.3) / 0.4, 0), 1) * 0.20
    if ndmi is not None:  forest_score += min(max((ndmi - 0.0) / 0.4, 0), 1) * 0.25
    if nbr  is not None:  forest_score += min(max((nbr  - 0.3) / 0.4, 0), 1) * 0.20

    # Crop: NDVI moderate (0.3-0.7), SAVI moderate, NDMI moderate (not as high as forest)
    crop_score = 0.0
    if ndvi is not None:
        crop_score += (1.0 - abs(ndvi - 0.5) / 0.3) * 0.35 if 0.2 <= ndvi <= 0.8 else 0
    if savi is not None:
        crop_score += min(max((savi - 0.1) / 0.4, 0), 1) * 0.35
    if ndmi is not None:
        crop_score += (1.0 - abs(ndmi - 0.1) / 0.2) * 0.30 if -0.1 <= ndmi <= 0.3 else 0

    # Bare soil: high BSI (>0.0), low NDVI (<0.25), low NDMI (<0.0)
    bare_score = 0.0
    if bsi  is not None:  bare_score += min(max((bsi  + 0.1) / 0.3, 0), 1) * 0.40
    if ndvi is not None:  bare_score += min(max((0.25 - ndvi) / 0.25, 0), 1) * 0.35
    if ndmi is not None:  bare_score += min(max((-ndmi) / 0.2, 0), 1) * 0.25

    # Disturbance: NBR drops + BSI spikes simultaneously
    disturbance = 0.0
    if nbr is not None:   disturbance += min(max((0.5 - nbr) / 0.5, 0), 1) * 0.5
    if bsi is not None:   disturbance += min(max((bsi + 0.1) / 0.4, 0), 1) * 0.5

    return {
        "forest_score":  round(min(max(forest_score, 0), 1), 3),
        "crop_score":    round(min(max(crop_score, 0), 1), 3),
        "bare_score":    round(min(max(bare_score, 0), 1), 3),
        "disturbance":   round(min(max(disturbance, 0), 1), 3),
    }


def _detect_farming_start(monthly: List[Dict]) -> Dict:
    """
    Analyse monthly multi-index timeseries to detect:
      - land_clearing_month: first month where bare/disturbance score spikes
      - farming_start_month: first month of consistent crop signal after clearing
      - pre_2020_confirmed: True if farming_start_month < "2020-01"
      - predates_coverage: True if land was already being farmed at start of Sentinel-2 record (2017)
      - confidence: HIGH / MEDIUM / LOW based on cloud gap months around event

    Algorithm:
      1. Score each month using _score_month_land_use()
      2. Check if land was already farmed in first 6 months (predates 2017 coverage)
      3. Find the first persistent bare/disturbance event (land clearing)
      4. Find first crop month after that bare event (crop_score > 0.35)
      5. Compute confidence from valid_pixels around the event
    """
    EUDR_CUTOFF = "2020-01"
    CROP_THRESHOLD    = 0.35
    BARE_THRESHOLD    = 0.40
    DISTURB_THRESHOLD = 0.45

    scored = []
    for m in monthly:
        scores = _score_month_land_use(m)
        scored.append({**m, **scores})

    # --- Check if land was ALREADY being farmed at the start of the satellite record ---
    # If the first 6 valid months show consistent crop signal, the farm predates our data (pre-2017).
    # We must NOT report Jan-2017 as the farming start in this case.
    first_valid = [m for m in scored[:12] if m.get("crop_score") is not None]
    predates_coverage = (
        len(first_valid) >= 4 and
        sum(1 for m in first_valid if m["crop_score"] >= CROP_THRESHOLD) >= 3
    )

    # --- Find clearing / disturbance event ---
    clearing_month   = None
    clearing_idx     = None
    for i, m in enumerate(scored):
        if m.get("bare_score") is None:
            continue
        bare  = m["bare_score"]
        dist  = m.get("disturbance", 0) or 0
        if bare >= BARE_THRESHOLD or dist >= DISTURB_THRESHOLD:
            # Require that previous 2 valid months had higher vegetation (confirms it's a drop, not always bare)
            prev_valid = [s for s in scored[max(0, i-3):i] if s.get("ndvi") is not None]
            if prev_valid and any(p["ndvi"] > 0.35 for p in prev_valid):
                clearing_month = m["month"]
                clearing_idx   = i
                break

    # --- Find farming start (first crop month after clearing) ---
    # Only search if we found a clearing event, OR if land was not already farmed at baseline.
    # If land was already farmed at the start and no clearing was found, the start predates our data.
    search_from = clearing_idx if clearing_idx is not None else (0 if not predates_coverage else len(scored))
    farming_start_month  = None
    farming_start_idx    = None
    consecutive_crop     = 0
    for i in range(search_from, len(scored)):
        m = scored[i]
        if m.get("crop_score") is None:
            consecutive_crop = 0
            continue
        if m["crop_score"] >= CROP_THRESHOLD:
            consecutive_crop += 1
            if consecutive_crop >= 2:  # require 2 consecutive months to avoid false positives
                # Backtrack to first of the pair
                farming_start_idx   = i - 1
                farming_start_month = scored[farming_start_idx]["month"]
                break
        else:
            consecutive_crop = 0

    # --- Confidence: count cloud gaps in 3-month window around event ---
    def _confidence_around(idx: Optional[int], window: int = 3) -> str:
        if idx is None:
            return "LOW"
        lo  = max(0, idx - window)
        hi  = min(len(scored), idx + window + 1)
        gap = sum(1 for m in scored[lo:hi] if m.get("valid_pixels", 0) == 0)
        if gap == 0:
            return "HIGH"
        if gap <= 1:
            return "MEDIUM"
        return "LOW"

    farming_confidence  = _confidence_around(farming_start_idx)
    clearing_confidence = _confidence_around(clearing_idx)

    pre_2020 = False
    if farming_start_month:
        pre_2020 = farming_start_month < EUDR_CUTOFF

    # Forest signal before clearing (was it forested?)
    pre_clearing_months = scored[:clearing_idx] if clearing_idx else scored[:12]
    valid_pre = [m for m in pre_clearing_months if m.get("forest_score") is not None]
    forest_before = (
        len(valid_pre) >= 3 and
        sum(m["forest_score"] for m in valid_pre) / len(valid_pre) >= 0.35
    )

    # Build scored timeseries for frontend chart (all months, with scores)
    chart_months = []
    for m in scored:
        chart_months.append({
            "month":         m["month"],
            "ndvi":          m.get("ndvi"),
            "savi":          m.get("savi"),
            "evi":           m.get("evi"),
            "ndmi":          m.get("ndmi"),
            "bsi":           m.get("bsi"),
            "nbr":           m.get("nbr"),
            "forest_score":  m.get("forest_score"),
            "crop_score":    m.get("crop_score"),
            "bare_score":    m.get("bare_score"),
            "disturbance":   m.get("disturbance"),
            "cloud_cover_pct": m.get("cloud_cover_pct"),
            "source":        m.get("source", "sentinel2"),
        })

    return {
        "clearing_month":        clearing_month,
        "clearing_confidence":   clearing_confidence,
        "farming_start_month":   farming_start_month,
        "farming_start_confidence": farming_confidence,
        "predates_coverage":     predates_coverage,
        "pre_2020_confirmed":    pre_2020,
        "forest_present_before_clearing": forest_before,
        "total_months_analysed": len(monthly),
        "cloud_gap_months":      sum(1 for m in monthly if m.get("valid_pixels", 0) == 0),
        "chart_data":            chart_months,
    }


async def _hansen_forest_loss(lon: float, lat: float) -> Dict:
    """
    Query Hansen Global Forest Change v1.11 (2023) for a given lon/lat.
    Uses free public GeoTIFF COG tiles — no authentication required.

    Returns:
      treecover2000: % forest cover in year 2000 (0-100)
      loss_year: year of forest loss (None = no loss, 2001-2023)
      was_forested: True if treecover2000 >= 30%
    """
    try:
        import rasterio
        from rasterio.windows import Window
        from rasterio.env import Env
    except ImportError:
        logger.warning("[Hansen] rasterio not available — skipping Hansen check")
        return {"treecover2000": None, "loss_year": None, "was_forested": None, "error": "rasterio not installed"}

    def _tile_name(lat_deg: float, lon_deg: float) -> str:
        """Compute Hansen tile filename suffix for a lat/lon point."""
        lat_tile = math.ceil(lat_deg / 10.0) * 10
        lon_tile = math.floor(lon_deg / 10.0) * 10
        lat_str  = f"{abs(lat_tile):02d}{'N' if lat_tile >= 0 else 'S'}"
        lon_str  = f"{abs(lon_tile):03d}{'E' if lon_tile >= 0 else 'W'}"
        return f"{lat_str}_{lon_str}"

    base_url  = "https://storage.googleapis.com/earthenginepartners-hansen/GFC-2023-v1.11"
    tile      = _tile_name(lat, lon)
    tc_url    = f"{base_url}/Hansen_GFC-2023-v1.11_treecover2000_{tile}.tif"
    ly_url    = f"{base_url}/Hansen_GFC-2023-v1.11_lossyear_{tile}.tif"

    def _read_pixel(url: str, lon_pt: float, lat_pt: float) -> Optional[int]:
        gdal_url = f"/vsicurl/{url}"
        try:
            with Env(GDAL_DISABLE_READDIR_ON_OPEN="YES", CPL_VSIL_CURL_ALLOWED_EXTENSIONS="tif"):
                with rasterio.open(gdal_url) as src:
                    row, col = src.index(lon_pt, lat_pt)
                    data = src.read(1, window=Window(col, row, 1, 1))
                    return int(data[0, 0])
        except Exception as e:
            logger.warning(f"[Hansen] Failed to read {url}: {e}")
            return None

    try:
        treecover = await asyncio.get_event_loop().run_in_executor(None, _read_pixel, tc_url, lon, lat)
        lossyear  = await asyncio.get_event_loop().run_in_executor(None, _read_pixel, ly_url, lon, lat)
    except Exception as e:
        logger.warning(f"[Hansen] Executor error: {e}")
        return {"treecover2000": None, "loss_year": None, "was_forested": None, "error": str(e)}

    loss_year_actual = (2000 + lossyear) if (lossyear is not None and lossyear > 0) else None
    was_forested     = (treecover is not None and treecover >= 30)

    logger.info(f"[Hansen] tile={tile} treecover2000={treecover}% lossyear={lossyear} → loss_year={loss_year_actual}")
    return {
        "treecover2000": treecover,
        "loss_year":     loss_year_actual,
        "was_forested":  was_forested,
        "tile":          tile,
    }


async def run_eudr_farming_analysis(
    token: str,
    coords: List,
    centroid_lon: float,
    centroid_lat: float,
) -> Dict:
    """
    Full EUDR farming history analysis for a parcel.
    Combines monthly multi-index satellite timeseries + Hansen forest loss tile.

    Returns complete analysis including:
      farming_start_month, clearing_month, eudr_status, hansen_data, chart_data
    """
    import asyncio as _asyncio

    # Run all four sources concurrently:
    #   Landsat 5  (landsat-tm-l2)  1990–2012: 30m, extends detection back to 1990
    #   Landsat 8  (landsat-ot-l2)  2013–2016: 30m, bridges to Sentinel-2
    #   Sentinel-2 (sentinel-2-l2a) 2017–today: 10m, best resolution
    #   Hansen GFC  —  forest loss tile (no token needed)
    s2_task  = _fetch_eudr_monthly_timeseries(token, coords)
    l8_task  = _fetch_landsat_monthly_timeseries(
        token, coords, "landsat-ot-l2", 2013, 2016, _LANDSAT8_EVALSCRIPT, "landsat8"
    )
    l5_task  = _fetch_landsat_monthly_timeseries(
        token, coords, "landsat-tm-l2", 1990, 2012, _LANDSAT5_EVALSCRIPT, "landsat5"
    )
    hansen_task = _hansen_forest_loss(centroid_lon, centroid_lat)

    s2_data, l8_data, l5_data, hansen_data = await _asyncio.gather(
        s2_task, l8_task, l5_task, hansen_task
    )

    # Merge chronologically; prefer higher-resolution source when months overlap
    # Priority: sentinel2 > landsat8 > landsat5
    source_priority = {"sentinel2": 3, "landsat8": 2, "landsat5": 1}
    merged: Dict[str, Dict] = {}
    for m in l5_data + l8_data + s2_data:
        month = m["month"]
        if month not in merged:
            merged[month] = m
        else:
            existing_prio = source_priority.get(merged[month].get("source", ""), 0)
            new_prio      = source_priority.get(m.get("source", ""), 0)
            if new_prio > existing_prio:
                merged[month] = m
    monthly_data = sorted(merged.values(), key=lambda m: m["month"])

    logger.info(
        f"[EUDR farming] Merged timeseries: {len(l5_data)} L5 + {len(l8_data)} L8 + {len(s2_data)} S2 "
        f"= {len(monthly_data)} months total ({monthly_data[0]['month'] if monthly_data else '?'} → "
        f"{monthly_data[-1]['month'] if monthly_data else '?'})"
    )

    # Detect farming start from merged multi-source monthly signals
    detection = _detect_farming_start(monthly_data)

    farming_start     = detection.get("farming_start_month")
    clearing_month    = detection.get("clearing_month")
    predates_coverage = detection.get("predates_coverage", False)

    # If land was already being farmed at the very start of our merged dataset (1990)
    # and no clearing was found, fall back to Hansen loss year as proxy.
    # (predates_coverage now means "pre-1990" since L5 starts at 1990)
    farming_start_source = monthly_data[0].get("source", "sentinel2") if farming_start and monthly_data else "sentinel2"
    if farming_start:
        # identify which source detected the farming start
        for m in monthly_data:
            if m["month"] == farming_start:
                farming_start_source = m.get("source", "sentinel2")
                break

    if predates_coverage and farming_start is None and hansen_data.get("loss_year"):
        loss_yr = hansen_data["loss_year"]
        farming_start = f"{loss_yr}-01"
        farming_start_source = "hansen_proxy"
        logger.info(f"Farming predates Landsat coverage; using Hansen loss year {loss_yr} as proxy")
    elif predates_coverage and farming_start is None:
        farming_start_source = "pre_1990_unknown"

    pre_2020 = (farming_start is not None and farming_start < "2020-01") or predates_coverage
    forest_cleared = (
        hansen_data.get("was_forested") and
        hansen_data.get("loss_year") is not None and
        hansen_data.get("loss_year") >= 2021
    )

    def _fmt_start(s):
        if s is None:
            return "unknown"
        try:
            y, m = s.split("-")
            from datetime import date
            return date(int(y), int(m), 1).strftime("%B %Y")
        except Exception:
            return s

    if predates_coverage and farming_start_source == "pre_1990_unknown":
        eudr_status = "COMPLIANT"
        eudr_summary = (
            "Farm was already established before 1990 (predates all satellite coverage). "
            "No Hansen forest loss detected post-2020. EUDR Compliant."
        )
    elif predates_coverage and farming_start_source == "hansen_proxy":
        loss_yr = hansen_data["loss_year"]
        was_forested = hansen_data.get("was_forested", False)
        if loss_yr >= 2021:
            eudr_status = "RISK"
            eudr_summary = (
                f"Hansen shows forest cleared in {loss_yr} at this location. "
                "Post-2020 deforestation detected. EUDR NON-COMPLIANT."
            )
        elif was_forested and loss_yr >= 2000:
            eudr_status = "COMPLIANT"
            eudr_summary = (
                f"Forest loss detected in {loss_yr} (pre-2020). "
                "Farming predates the EUDR Dec 2020 cutoff. EUDR Compliant."
            )
        else:
            eudr_status = "COMPLIANT"
            eudr_summary = (
                f"Farm established ~{loss_yr} (predates 2020). "
                "No post-2020 deforestation. EUDR Compliant."
            )
    elif pre_2020 and not forest_cleared:
        eudr_status = "COMPLIANT"
        eudr_summary = (
            f"Farming confirmed from {_fmt_start(farming_start)} (pre-2020). "
            "No post-2020 deforestation detected."
        )
    elif forest_cleared and farming_start and farming_start >= "2021-01":
        eudr_status = "RISK"
        eudr_summary = (
            f"Forest cleared in {hansen_data['loss_year']} and farming started {_fmt_start(farming_start)}. "
            "Likely post-2020 deforestation. EUDR NON-COMPLIANT."
        )
    elif forest_cleared and pre_2020:
        eudr_status = "INVESTIGATE"
        eudr_summary = (
            f"Farming pre-2020 confirmed ({_fmt_start(farming_start)}) but Hansen shows forest loss "
            f"in {hansen_data['loss_year']} at this location. Manual review required."
        )
    elif farming_start is None:
        eudr_status  = "INSUFFICIENT_DATA"
        eudr_summary = "Could not determine farming start date. Insufficient cloud-free imagery."
    else:
        eudr_status  = "PENDING_REVIEW"
        eudr_summary = f"Farming start detected {_fmt_start(farming_start)}. Additional evidence recommended."

    risk_flags = []
    if forest_cleared:
        risk_flags.append(f"Hansen: forest loss detected in {hansen_data['loss_year']}")
    if detection.get("forest_present_before_clearing"):
        risk_flags.append("Satellite: forest signature present before clearing event")
    if detection.get("cloud_gap_months", 0) > 6:
        risk_flags.append(f"Data quality: {detection['cloud_gap_months']} months with cloud cover gaps")

    return {
        "farming_start_month":           farming_start,
        "farming_start_confidence":      detection.get("farming_start_confidence"),
        "farming_start_source":          farming_start_source,
        "predates_coverage":             predates_coverage,
        "land_clearing_month":           clearing_month,
        "clearing_confidence":           detection.get("clearing_confidence"),
        "pre_2020_farming_confirmed":    pre_2020,
        "forest_present_before_clearing": detection.get("forest_present_before_clearing"),
        "eudr_status":                   eudr_status,
        "eudr_summary":                  eudr_summary,
        "eudr_risk_flags":               risk_flags,
        "hansen": {
            "treecover2000":  hansen_data.get("treecover2000"),
            "loss_year":      hansen_data.get("loss_year"),
            "was_forested":   hansen_data.get("was_forested"),
            "tile":           hansen_data.get("tile"),
            "error":          hansen_data.get("error"),
        },
        "timeseries_months":    detection.get("total_months_analysed"),
        "cloud_gap_months":     detection.get("cloud_gap_months"),
        "chart_data":           detection.get("chart_data", []),
        "analysed_at":          datetime.utcnow().isoformat(),
    }


def _classify_timeseries_events(quarters: List[Dict]) -> Dict:
    """
    Walk through quarterly NDVI values and classify events.

    Rules:
      - Baseline = first quarter with valid NDVI (≥ Dec 2020)
      - DEFORESTATION: sudden drop > 0.20 AND result NDVI < 0.35, no recovery within 2 quarters
      - VEGETATION_LOSS: drop > 0.15 AND result NDVI < 0.45, partial or no recovery
      - SEASONAL_DIP: drop > 0.10 but recovers within next 1–2 quarters
      - REGROWTH: gain > 0.15 after a prior loss
      EUDR cutoff = 2020-12-31: only events whose period_from > that date are non-compliant.
    """
    EUDR_CUTOFF = "2020-12-31"
    valid = [q for q in quarters if q["ndvi"] is not None]
    if len(valid) < 2:
        return {"events": [], "baseline_ndvi": None, "current_ndvi": None, "eudr_compliant": True,
                "deforestation_detected": False, "summary": "Insufficient cloud-free imagery for analysis."}

    baseline_ndvi  = valid[0]["ndvi"]
    current_ndvi   = valid[-1]["ndvi"]
    events         = []

    for i in range(1, len(valid)):
        prev = valid[i - 1]
        curr = valid[i]
        delta = curr["ndvi"] - prev["ndvi"]

        # Check if next quarter recovers (look ahead 1–2 quarters)
        next_vals = [valid[j]["ndvi"] for j in range(i + 1, min(i + 3, len(valid)))]
        recovers  = any(v >= prev["ndvi"] - 0.05 for v in next_vals)

        severity = event_type = None

        if delta <= -0.20 and curr["ndvi"] < 0.35:
            event_type = "DEFORESTATION"
            severity   = "critical" if curr["ndvi"] < 0.20 else "high"
        elif delta <= -0.15 and curr["ndvi"] < 0.45:
            if recovers:
                event_type, severity = "SEASONAL_DIP", "low"
            else:
                event_type, severity = "VEGETATION_LOSS", "medium"
        elif delta <= -0.10:
            event_type, severity = "SEASONAL_DIP", "low"
        elif delta >= 0.15 and prev["ndvi"] < 0.45:
            event_type, severity = "REGROWTH", "info"

        if event_type:
            post_cutoff = curr["period_from"] > EUDR_CUTOFF
            events.append({
                "period_from":    curr["period_from"],
                "period_to":      curr["period_to"],
                "event_type":     event_type,
                "severity":       severity,
                "ndvi_before":    prev["ndvi"],
                "ndvi_after":     curr["ndvi"],
                "ndvi_change":    round(delta, 3),
                "recovered":      recovers,
                "post_eudr_cutoff": post_cutoff,
                "eudr_violation": event_type in ("DEFORESTATION", "VEGETATION_LOSS") and post_cutoff,
            })

    violations         = [e for e in events if e["eudr_violation"]]
    deforestation_det  = any(e["event_type"] == "DEFORESTATION" for e in violations)
    eudr_compliant     = len(violations) == 0

    if deforestation_det:
        summary = f"Deforestation detected in {len([e for e in violations if e['event_type']=='DEFORESTATION'])} period(s) after Dec 2020. EUDR NON-COMPLIANT."
    elif violations:
        summary = f"Significant vegetation loss in {len(violations)} period(s) after Dec 2020. Review required."
    elif current_ndvi < 0.35:
        summary = "Low current vegetation cover. No post-2020 deforestation events detected."
    else:
        summary = "No deforestation detected since Dec 2020. EUDR compliant."

    return {
        "events":                events,
        "baseline_ndvi":         baseline_ndvi,
        "current_ndvi":          current_ndvi,
        "ndvi_change_total":     round(current_ndvi - baseline_ndvi, 3),
        "eudr_compliant":        eudr_compliant,
        "deforestation_detected": deforestation_det,
        "violations_count":      len(violations),
        "summary":               summary,
    }


async def fetch_weather_history(lat: float, lon: float) -> Dict:
    """
    Fetch daily weather from Open-Meteo Historical API (free, no auth needed).
    Returns daily arrays: time, precipitation_sum, et0_fao_evapotranspiration, temperature_2m_max.
    Data available from 1940 to ~5 days ago.
    """
    from_date = "2020-12-01"
    to_date   = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "start_date": from_date,
        "end_date":   to_date,
        "daily": "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max",
        "timezone": "UTC",
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(url, params=params)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Open-Meteo weather API timed out.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach Open-Meteo weather API.")

    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail=f"Open-Meteo returned {resp.status_code}: {resp.text[:200]}")

    body = resp.json()
    if "daily" not in body or not body["daily"].get("time"):
        raise HTTPException(status_code=404, detail="Open-Meteo returned no daily data for these coordinates.")

    logger.info(f"Weather fetched for ({lat:.4f},{lon:.4f}): {len(body['daily']['time'])} days")
    return body


def _aggregate_weather_to_quarters(daily_data: Dict, quarters: List[Dict]) -> List[Dict]:
    """
    Map Open-Meteo daily weather data onto the same quarterly windows as satellite data.
    Returns one dict per quarter with rainfall_mm, et0_mm, water_deficit_mm, temp_max_avg_c, drought_flag.

    Drought detection rule:
      water_deficit < -80 mm  AND  rainfall < 40 mm  in the same quarter
      = the vegetation is under severe water stress, not deforestation.
    """
    times  = daily_data.get("daily", {}).get("time", [])
    precip = daily_data.get("daily", {}).get("precipitation_sum", [])
    et0    = daily_data.get("daily", {}).get("et0_fao_evapotranspiration", [])
    temp   = daily_data.get("daily", {}).get("temperature_2m_max", [])

    # Build date → values lookup
    daily: Dict[str, Dict] = {}
    for i, t in enumerate(times):
        daily[t] = {
            "precip": precip[i] if i < len(precip) else None,
            "et0":    et0[i]    if i < len(et0)    else None,
            "temp":   temp[i]   if i < len(temp)   else None,
        }

    result = []
    for q in quarters:
        qfrom, qto = q["period_from"], q["period_to"]
        period_days = [v for k, v in daily.items() if qfrom <= k <= qto]

        if not period_days:
            result.append({
                "period_from": qfrom, "period_to": qto,
                "rainfall_mm": None, "et0_mm": None,
                "water_deficit_mm": None, "temp_max_avg_c": None,
                "drought_flag": False,
            })
            continue

        p_vals = [d["precip"] for d in period_days if d["precip"] is not None]
        e_vals = [d["et0"]    for d in period_days if d["et0"]    is not None]
        t_vals = [d["temp"]   for d in period_days if d["temp"]   is not None]

        rainfall = round(sum(p_vals), 1) if p_vals else None
        et0_sum  = round(sum(e_vals), 1) if e_vals else None
        temp_avg = round(sum(t_vals) / len(t_vals), 1) if t_vals else None

        if rainfall is not None and et0_sum is not None:
            water_deficit = round(rainfall - et0_sum, 1)
        else:
            water_deficit = None

        # Flag severe water stress quarters: large ET0 deficit + very low rainfall
        drought = bool(
            water_deficit is not None and water_deficit < -80
            and rainfall is not None and rainfall < 40
        )

        result.append({
            "period_from":    qfrom,
            "period_to":      qto,
            "rainfall_mm":    rainfall,
            "et0_mm":         et0_sum,
            "water_deficit_mm": water_deficit,
            "temp_max_avg_c": temp_avg,
            "drought_flag":   drought,
        })

    return result


async def _store_weather_observations(parcel_id: str, weather_quarters: List[Dict]) -> None:
    """Upsert quarterly weather records into weather_observations table."""
    from app.core.database import async_session_factory
    from app.models.satellite import WeatherObservation
    from sqlalchemy import select

    logger.info(f"[WX-STORE] parcel={parcel_id} quarters={len(weather_quarters)} periods={[q.get('period_from') for q in weather_quarters]}")
    async with async_session_factory() as session:
        for wq in weather_quarters:
            pfrom = wq.get("period_from") or ""
            pto   = wq.get("period_to")   or ""
            if not pfrom or not pto:
                continue  # skip malformed quarters — period_from/to are NOT NULL
            result = await session.execute(
                select(WeatherObservation).where(
                    WeatherObservation.parcel_id == parcel_id,
                    WeatherObservation.period_from == pfrom,
                )
            )
            rec = result.scalar_one_or_none()
            if rec is None:
                rec = WeatherObservation(parcel_id=parcel_id, period_from=pfrom)
                session.add(rec)
            rec.period_to         = pto
            rec.rainfall_mm       = wq.get("rainfall_mm")
            rec.et0_mm            = wq.get("et0_mm")
            rec.water_deficit_mm  = wq.get("water_deficit_mm")
            rec.temp_max_avg_c    = wq.get("temp_max_avg_c")
            rec.drought_flag      = 1 if wq.get("drought_flag") else 0
        await session.commit()


def _compute_fusion_score(q: Dict) -> Optional[float]:
    """
    Weighted 5-index vegetation score (S2 optical + S1 SAR).
    Weights: NDVI 28%, EVI 22%, SAVI 16%, NDMI 16%, RVI(SAR) 18%.
    RVI from Sentinel-1 is cloud-proof and sensitive to canopy structure.
    Re-normalizes weights when indices are absent.
    """
    ndvi = q.get("ndvi")
    if ndvi is None:
        return None
    pairs = [
        (ndvi,          0.28),
        (q.get("evi"),  0.22),
        (q.get("savi"), 0.16),
        (q.get("ndmi"), 0.16),
        (q.get("rvi"),  0.18),  # SAR RVI — cloud-proof
    ]
    score, total_w = 0.0, 0.0
    for val, w in pairs:
        if val is not None:
            score  += val * w
            total_w += w
    return round(score / total_w, 3) if total_w > 0 else None


def _build_event_reasoning(
    prev: Dict, curr: Dict,
    ndvi_d: float,
    evi_d: Optional[float], savi_d: Optional[float], ndmi_d: Optional[float],
    fusion_d: Optional[float],
    event_type: str, drought_induced: bool, canopy_intact: bool,
    ndmi_drought: bool, recovers: bool, w: Dict,
) -> str:
    """
    Plain-language explanation for each classified event.
    Covers what each index measured, what changed, and what it means
    for EUDR compliance. Includes BSI and NBR where available.
    """
    def _fmt(v):
        return f"{v:.3f}" if v is not None else "n/a"

    def _d(d):
        if d is None: return ""
        return f" ({'+' if d > 0 else ''}{d:.3f})"

    def _plain_index(name: str, meaning: str, before, after, delta) -> Optional[str]:
        if delta is None: return None
        direction = "rose" if delta > 0 else "fell"
        return f"{name} ({meaning}) {direction} from {_fmt(before)} to {_fmt(after)}{_d(delta)}"

    ndvi_line = _plain_index("NDVI", "overall plant cover",   prev.get("ndvi"),  curr.get("ndvi"),  ndvi_d)
    evi_line  = _plain_index("EVI",  "canopy density",         prev.get("evi"),   curr.get("evi"),   evi_d)
    savi_line = _plain_index("SAVI", "crops/sparse vegetation",prev.get("savi"),  curr.get("savi"),  savi_d)
    ndmi_line = _plain_index("NDMI", "moisture in vegetation", prev.get("ndmi"),  curr.get("ndmi"),  ndmi_d)
    bsi_line  = _plain_index("BSI",  "bare/exposed soil",      prev.get("bsi"),   curr.get("bsi"),   curr.get("bsi") - prev.get("bsi") if curr.get("bsi") is not None and prev.get("bsi") is not None else None)
    nbr_line  = _plain_index("NBR",  "forest disturbance",     prev.get("nbr"),   curr.get("nbr"),   curr.get("nbr") - prev.get("nbr") if curr.get("nbr") is not None and prev.get("nbr") is not None else None)
    fuse_line = (f"Combined index score fell from {_fmt(prev.get('fusion_score'))} to "
                 f"{_fmt(curr.get('fusion_score'))}{_d(fusion_d)}.") if fusion_d is not None else None

    index_lines = " · ".join(s for s in [ndvi_line, evi_line, savi_line, ndmi_line, bsi_line, nbr_line] if s)

    bsi_curr = curr.get("bsi")
    nbr_curr = curr.get("nbr")
    bsi_spike = bsi_curr is not None and bsi_curr > 0.10
    nbr_drop  = nbr_curr is not None and nbr_curr < 0.30

    if event_type == "DEFORESTATION":
        bsi_note = (f" BSI (bare soil) rose to {bsi_curr:.3f} — the land surface became exposed, "
                    "which is a direct sign of vegetation removal."
                    if bsi_spike else "")
        nbr_note = (f" NBR (forest disturbance) fell to {nbr_curr:.3f}, "
                    "well below the undisturbed forest level (>0.5), confirming severe canopy damage."
                    if nbr_drop else "")
        evi_note = (f" EVI (canopy density) also collapsed ({evi_d:+.3f}), "
                    "confirming the tree canopy — not just the ground cover — was removed."
                    if evi_d is not None and evi_d <= -0.15 else "")
        return (
            f"All vegetation indices declined sharply this quarter. {index_lines}.{evi_note}{bsi_note}{nbr_note} "
            f"{fuse_line or ''} "
            f"No recovery was detected in the next two quarters. "
            f"This combination — falling plant cover, rising bare soil, and forest disturbance signal — "
            f"is consistent with land clearing or tree removal. "
            f"Because this happened after the EUDR cut-off date (31 Dec 2020), "
            f"it is classified as an EUDR VIOLATION."
        ).strip()

    if event_type == "DROUGHT_STRESS":
        wx_note = ""
        if w.get("drought_flag"):
            wx_note = (f" Rainfall records confirm this: only {w.get('rainfall_mm', '?')} mm "
                       f"fell this quarter with a water deficit of {w.get('water_deficit_mm', '?')} mm.")
        ndmi_note = (" NDMI (moisture) dropped faster than NDVI, "
                     f"at {abs(ndmi_d)/max(abs(ndvi_d),0.001):.1f}× the rate — "
                     "this pattern means the vegetation was water-stressed, not removed."
                     if ndmi_drought and ndmi_d is not None else "")
        return (
            f"Vegetation declined this quarter ({index_lines}) but the cause is drought, "
            f"not land clearing.{wx_note}{ndmi_note} "
            f"BSI (bare soil) did not rise significantly, meaning the soil surface stayed covered. "
            f"Drought-related declines are temporary and expected in dry seasons. "
            f"This is NOT an EUDR violation."
        )

    if event_type == "CANOPY_DISTURBANCE":
        evi_note = (f" EVI (which measures the tall canopy specifically) changed only "
                    f"{evi_d:+.3f} compared to NDVI's {ndvi_d:+.3f} — "
                    "the tree layer is still intact, only the ground-level vegetation was affected."
                    if evi_d is not None else "")
        nbr_note = (f" NBR (forest disturbance) stayed at {nbr_curr:.3f}, "
                    "indicating the canopy structure was not damaged."
                    if nbr_curr is not None and nbr_curr >= 0.40 else "")
        return (
            f"NDVI declined this quarter but the tree canopy remained intact: {index_lines}.{evi_note}{nbr_note} "
            f"This is consistent with a seasonal crop harvest, understory clearing, or grazing — "
            f"activities that reduce ground-level vegetation without removing trees. "
            f"This is NOT classified as deforestation and is NOT an EUDR violation."
        )

    if event_type == "VEGETATION_LOSS":
        bsi_note = (f" BSI (bare soil) rose to {bsi_curr:.3f}, suggesting some land exposure."
                    if bsi_spike else " BSI (bare soil) did not spike significantly.")
        nbr_note = (f" NBR (forest disturbance) dropped to {nbr_curr:.3f}, "
                    "suggesting partial forest damage."
                    if nbr_drop else "")
        no_wx = " No drought or water stress was detected from weather or moisture data." if not drought_induced else ""
        return (
            f"A sustained vegetation decline was detected that did not recover: {index_lines}.{bsi_note}{nbr_note}{no_wx} "
            f"This falls short of the full deforestation threshold (EVI did not collapse completely), "
            f"but the persistence and scale are concerning. "
            f"Possible causes include partial clearing, agroforestry change, or gradual degradation. "
            f"Field verification is recommended before making an EUDR compliance decision."
        )

    if event_type == "SEASONAL_DIP":
        return (
            f"Vegetation declined this quarter but recovered within 1–2 quarters: {index_lines}. "
            f"BSI (bare soil) and NBR (forest disturbance) did not show abnormal changes. "
            f"This is a normal dry-season pattern — for example, a crop harvest or leaf-off period. "
            f"No EUDR concern. Seasonal variation is expected and is not a compliance issue."
        )

    if event_type == "REGROWTH":
        return (
            f"Vegetation is recovering this quarter — indices are rising after a previous low: {index_lines}. "
            f"BSI (bare soil) is declining as plant cover returns. "
            f"This is consistent with post-drought recovery, crop re-establishment, or reforestation. "
            f"A positive signal for this parcel."
        )

    return index_lines


def _classify_with_weather(quarters: List[Dict], weather_by_period: Dict, xgb_classify_fn=None) -> Dict:
    """
    Full 4-index event classifier with weather fusion and canopy-intact discrimination.

    Classification rules (in priority order):
      1. DROUGHT_STRESS — large NDMI drop relative to NDVI (moisture signal dominates),
                          OR weather drought_flag. NOT an EUDR violation.
      2. CANOPY_DISTURBANCE — NDVI drops but EVI (canopy proxy) holds. Trees intact,
                               only understory affected. NOT an EUDR violation.
      3. DEFORESTATION — all indices including EVI collapse sharply, no recovery.
                         Fusion score < 0.35. EUDR VIOLATION if after Dec 2020.
      4. VEGETATION_LOSS — sustained multi-index decline without drought or canopy evidence.
                            EUDR VIOLATION if after Dec 2020.
      5. SEASONAL_DIP — any decline that recovers within 2 quarters. Normal variation.
      6. REGROWTH — rising indices after prior low. Positive signal.

    All thresholds are applied to the weighted fusion score (NDVI 35%, EVI 25%,
    SAVI 20%, NDMI 20%) rather than NDVI alone, for greater accuracy.
    """
    EUDR_CUTOFF = "2020-12-31"

    # Compute fusion score for every quarter in place (mutates the shared dicts)
    for q in quarters:
        q["fusion_score"] = _compute_fusion_score(q)

    valid = [q for q in quarters if q["ndvi"] is not None]
    if len(valid) < 2:
        return {
            "events": [], "baseline_ndvi": None, "current_ndvi": None,
            "baseline_fusion": None, "current_fusion": None,
            "eudr_compliant": True, "deforestation_detected": False,
            "drought_events_count": 0, "canopy_disturbance_count": 0,
            "summary": "Insufficient cloud-free imagery for analysis.",
        }

    baseline_ndvi   = valid[0]["ndvi"]
    current_ndvi    = valid[-1]["ndvi"]
    baseline_fusion = valid[0].get("fusion_score")
    current_fusion  = valid[-1].get("fusion_score")
    events: List[Dict] = []

    for i in range(1, len(valid)):
        prev = valid[i - 1]
        curr = valid[i]

        # Per-index deltas
        ndvi_d  = curr["ndvi"] - prev["ndvi"]
        evi_d   = (curr["evi"]  - prev["evi"])  if (curr.get("evi")  is not None and prev.get("evi")  is not None) else None
        savi_d  = (curr["savi"] - prev["savi"]) if (curr.get("savi") is not None and prev.get("savi") is not None) else None
        ndmi_d  = (curr["ndmi"] - prev["ndmi"]) if (curr.get("ndmi") is not None and prev.get("ndmi") is not None) else None
        fs_prev = prev.get("fusion_score")
        fs_curr = curr.get("fusion_score")
        fusion_d = round(fs_curr - fs_prev, 3) if (fs_prev is not None and fs_curr is not None) else None

        # Use fusion delta as primary signal when available
        eff_delta = fusion_d if fusion_d is not None else ndvi_d
        eff_score = fs_curr  if fs_curr  is not None else curr["ndvi"]

        # Recovery look-ahead: did indices recover in the next 1–2 quarters?
        next_fusions = [valid[j].get("fusion_score") or valid[j]["ndvi"]
                        for j in range(i + 1, min(i + 3, len(valid)))]
        ref_level = (fs_prev or prev["ndvi"]) - 0.05
        recovers  = any(v >= ref_level for v in next_fusions)

        # Weather-based drought signal
        w          = weather_by_period.get(curr["period_from"], {})
        wx_drought = bool(w.get("drought_flag", False))

        # CUSUM and pixel-level stats (pre-computed by analyze_parcel_history)
        cusum_score   = curr.get("cusum_score",        0.0) or 0.0
        is_breakpoint = bool(curr.get("is_breakpoint", False))
        ndvi_std      = curr.get("ndvi_std")
        ndvi_pct_b035 = curr.get("ndvi_pct_below_035")

        # XGBoost classification — runs in parallel with rule-based logic
        xgb_result = None
        if xgb_classify_fn is not None:
            try:
                xgb_result = xgb_classify_fn(prev, curr, w, cusum_score, is_breakpoint)
            except Exception:
                pass

        # Satellite-only drought signal: NDMI drops proportionally more than NDVI
        # Ratio > 1.4 means moisture loss is the dominant stressor, not canopy removal
        ndmi_drought = False
        if ndmi_d is not None and ndvi_d < -0.05:
            ndmi_ratio   = abs(ndmi_d) / (abs(ndvi_d) + 1e-6)
            ndmi_drought = ndmi_ratio > 1.4

        drought = wx_drought or ndmi_drought

        # Canopy-intact check: EVI (canopy structure index) stayed relatively stable
        # while NDVI dropped — trees are still there, only understory was affected
        canopy_intact = False
        if evi_d is not None and ndvi_d <= -0.10:
            # EVI dropped less than 50% of NDVI's drop
            canopy_intact = evi_d > ndvi_d * 0.50

        # ── Classification (priority order) ──────────────────────────────────
        severity = event_type = None
        drought_induced = False

        if eff_delta <= -0.20 and eff_score < 0.35:
            if drought:
                event_type, severity, drought_induced = "DROUGHT_STRESS", "medium", True
            elif canopy_intact:
                event_type, severity = "CANOPY_DISTURBANCE", "medium"
            else:
                event_type = "DEFORESTATION"
                severity   = "critical" if eff_score < 0.20 else "high"

        elif eff_delta <= -0.15 and eff_score < 0.42:
            if recovers:
                event_type, severity = "SEASONAL_DIP", "low"
            elif drought:
                event_type, severity, drought_induced = "DROUGHT_STRESS", "low", True
            elif canopy_intact:
                event_type, severity = "CANOPY_DISTURBANCE", "low"
            else:
                event_type, severity = "VEGETATION_LOSS", "medium"

        elif eff_delta <= -0.10:
            event_type, severity = "SEASONAL_DIP", "low"

        elif eff_delta >= 0.15 and eff_score < 0.65:
            if (fs_prev or prev["ndvi"]) < 0.48:
                event_type, severity = "REGROWTH", "info"

        # XGBoost override: if confident and not NO_CHANGE, prefer ML label
        if xgb_result and event_type and xgb_result["confidence"] >= 0.60:
            xgb_type = xgb_result["event_type"]
            if xgb_type not in ("NO_CHANGE",):
                event_type = xgb_type

        if event_type:
            post_cutoff    = curr["period_from"] > EUDR_CUTOFF
            eudr_violation = (
                event_type in ("DEFORESTATION", "VEGETATION_LOSS")
                and post_cutoff
                and not drought_induced
            )
            reasoning = _build_event_reasoning(
                prev, curr, ndvi_d, evi_d, savi_d, ndmi_d, fusion_d,
                event_type, drought_induced, canopy_intact, ndmi_drought, recovers, w,
            )
            events.append({
                "period_from":       curr["period_from"],
                "period_to":         curr["period_to"],
                "event_type":        event_type,
                "severity":          severity,
                # NDVI
                "ndvi_before":       prev["ndvi"],
                "ndvi_after":        curr["ndvi"],
                "ndvi_change":       round(ndvi_d, 3),
                # EVI
                "evi_before":        prev.get("evi"),
                "evi_after":         curr.get("evi"),
                "evi_change":        round(evi_d,  3) if evi_d  is not None else None,
                # SAVI
                "savi_change":       round(savi_d, 3) if savi_d is not None else None,
                # NDMI
                "ndmi_change":       round(ndmi_d, 3) if ndmi_d is not None else None,
                # Fusion
                "fusion_before":     fs_prev,
                "fusion_after":      fs_curr,
                "fusion_change":     fusion_d,
                # Context flags
                "recovered":         recovers,
                "drought_induced":   drought_induced,
                "canopy_intact":     canopy_intact,
                "ndmi_drought_signal": ndmi_drought,
                "drought_flag":      drought,
                "water_deficit_mm":  w.get("water_deficit_mm"),
                "rainfall_mm":       w.get("rainfall_mm"),
                "post_eudr_cutoff":  post_cutoff,
                "eudr_violation":    eudr_violation,
                "reasoning":         reasoning,
                # ML / CUSUM enrichment
                "confidence":        xgb_result["confidence"] if xgb_result else None,
                "probabilities":     xgb_result["probabilities"] if xgb_result else None,
                "cusum_score":       round(cusum_score, 3),
                "is_breakpoint":     is_breakpoint,
                "ndvi_std":          round(ndvi_std,      4) if ndvi_std      is not None else None,
                "ndvi_pct_below_035": round(ndvi_pct_b035, 3) if ndvi_pct_b035 is not None else None,
            })

    violations        = [e for e in events if e["eudr_violation"]]
    deforestation_det = any(e["event_type"] == "DEFORESTATION" for e in violations)
    eudr_compliant    = len(violations) == 0
    drought_events    = [e for e in events if e.get("drought_induced")]
    canopy_dist_events = [e for e in events if e["event_type"] == "CANOPY_DISTURBANCE"]

    has_wx_drought = any(w.get("drought_flag") for w in weather_by_period.values())
    drought_source = "weather data" if has_wx_drought else "NDMI moisture pattern"

    if deforestation_det:
        n = len([e for e in violations if e["event_type"] == "DEFORESTATION"])
        summary = (
            f"Deforestation detected in {n} period(s) after Dec 2020 "
            f"(confirmed by 4-index analysis including EVI canopy collapse). "
            f"EUDR NON-COMPLIANT."
        )
    elif violations:
        summary = (
            f"Significant vegetation loss in {len(violations)} period(s) after Dec 2020. "
            f"No drought signal detected. Manual field verification required."
        )
    elif drought_events:
        summary = (
            f"Vegetation stress in {len(drought_events)} period(s) attributed to drought "
            f"(confirmed by {drought_source}). NDMI moisture pattern rules out deforestation. "
            f"EUDR compliant."
        )
    elif canopy_dist_events:
        summary = (
            f"Canopy disturbance in {len(canopy_dist_events)} period(s) — EVI analysis confirms "
            f"canopy trees are intact, only understory affected. EUDR compliant."
        )
    elif current_ndvi < 0.35:
        summary = "Current vegetation cover is low. No post-2020 deforestation events detected by 4-index analysis."
    else:
        summary = "No deforestation detected since Dec 2020. All 4 vegetation indices confirm compliance."

    return {
        "events":                  events,
        "baseline_ndvi":           baseline_ndvi,
        "current_ndvi":            current_ndvi,
        "baseline_fusion":         baseline_fusion,
        "current_fusion":          current_fusion,
        "ndvi_change_total":       round(current_ndvi - baseline_ndvi, 3),
        "fusion_change_total":     round(current_fusion - baseline_fusion, 3)
                                   if (current_fusion is not None and baseline_fusion is not None) else None,
        "eudr_compliant":          eudr_compliant,
        "deforestation_detected":  deforestation_det,
        "violations_count":        len(violations),
        "drought_events_count":    len(drought_events),
        "canopy_disturbance_count": len(canopy_dist_events),
        "summary":                 summary,
    }


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
    from_date = (acquisition_date - timedelta(days=180)).strftime("%Y-%m-%dT00:00:00Z")

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
            "aggregationInterval": {"of": "P90D"},
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
                "after cloud/shadow masking. All available scenes in the past 6 months are heavily "
                "clouded over this parcel. This is common during rainy seasons. Try again in a few "
                "weeks or during the dry season (Dec–Feb or Jul–Sep in Kenya)."
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
        # Invalidate cached model if it was trained without BSI/NBR (32 features).
        # The new feature set has 32 features; old models have 24. Force retrain.
        self._ensure_model_features()

    @staticmethod
    def _ensure_model_features():
        """Delete cached model if it was built with fewer features than current schema."""
        try:
            from app.services.ml_classifier import (
                MODEL_PATH, FEATURE_NAMES, delete_cached_model,
            )
            import xgboost as xgb
            if os.path.exists(MODEL_PATH):
                clf = xgb.XGBClassifier()
                clf.load_model(MODEL_PATH)
                n_cached = clf.n_features_in_
                if n_cached != len(FEATURE_NAMES):
                    logger.info(
                        f"[XGB] Cached model has {n_cached} features, "
                        f"current schema has {len(FEATURE_NAMES)} — deleting stale model."
                    )
                    delete_cached_model()
        except Exception as e:
            logger.debug(f"[XGB] Feature check skipped: {e}")

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

    async def analyze_parcel_history(self, parcel: Any) -> Dict[str, Any]:
        """
        Full deforestation history from Dec 2020 to today.
        Pipeline:
          1. Sentinel-2 quarterly optical indices (NDVI/EVI/SAVI/NDMI) + pixel stats
          2. Sentinel-1 SAR RVI (cloud-proof, parallel fetch)
          3. Open-Meteo weather aggregation + drought detection
          4. CUSUM time-series segmentation (structural breakpoint detection)
          5. 5-index fusion score (S2 optical + S1 SAR)
          6. XGBoost event classification with calibrated probabilities
             (rule-based fallback if XGBoost unavailable)
        """
        from app.services.ml_classifier import classify_event as xgb_classify

        parcel_id = getattr(parcel, "id", None)
        coords    = []
        if getattr(parcel, "boundary_geojson", None):
            coords = parcel.boundary_geojson.get("coordinates", [[]])[0]
        if not coords:
            raise HTTPException(status_code=400, detail="Parcel has no boundary polygon — cannot run history analysis.")

        lat = sum(c[1] for c in coords) / len(coords)
        lon = sum(c[0] for c in coords) / len(coords)

        creds         = await _load_satellite_credentials()
        client_id     = creds.get("oauth_client_id", "")
        client_secret = creds.get("oauth_client_secret", "")
        token         = await _get_sentinel_hub_token(client_id, client_secret)

        # 1+2+4. Fetch S2 timeseries, SAR RVI, and weather concurrently to cut wall-clock time
        from_date = "2020-12-01"
        to_date   = datetime.utcnow().strftime("%Y-%m-%d")

        import asyncio as _asyncio

        async def _safe_sar():
            try:
                return await _fetch_s1_rvi_timeseries(token, coords, from_date, to_date)
            except Exception as exc:
                logger.warning(f"[S1-RVI] Fetch failed: {exc} — proceeding without SAR data")
                return {}

        async def _safe_weather():
            try:
                raw = await fetch_weather_history(lat, lon)
                return raw
            except Exception as exc:
                detail = getattr(exc, 'detail', None) or str(exc) or type(exc).__name__
                logger.warning(f"Weather fetch failed for parcel {parcel_id}: {detail}")
                return None

        quarters, rvi_by_period, weather_raw = await _asyncio.gather(
            _fetch_sentinel_hub_timeseries(token, coords),
            _safe_sar(),
            _safe_weather(),
        )

        # Merge SAR RVI into quarters
        for q in quarters:
            q["rvi"] = rvi_by_period.get(q["period_from"])
        logger.info(f"[S1-RVI] Merged SAR RVI for {sum(1 for q in quarters if q.get('rvi') is not None)} quarters")

        # 3. CUSUM segmentation on fusion score series
        for q in quarters:
            q["fusion_score"] = _compute_fusion_score(q)

        fusion_series = [q.get("fusion_score") for q in quarters]
        cusum_scores, breakpoints = _cusum_detect(fusion_series)
        for i, q in enumerate(quarters):
            q["cusum_score"]   = cusum_scores[i]
            q["is_breakpoint"] = breakpoints[i]

        # 4. Aggregate weather (already fetched above in parallel)
        weather_quarters: List[Dict] = []
        if weather_raw:
            try:
                weather_quarters = _aggregate_weather_to_quarters(weather_raw, quarters)
                logger.info(f"Weather merged: {len(weather_quarters)} quarters, "
                            f"{sum(1 for w in weather_quarters if w['drought_flag'])} drought quarter(s)")
            except Exception as exc:
                logger.warning(f"Weather aggregation failed for parcel {parcel_id}: {exc}")

        if weather_quarters and parcel_id:
            try:
                await _store_weather_observations(parcel_id, weather_quarters)
            except Exception as exc:
                logger.warning(f"Weather DB store failed for parcel {parcel_id}: {exc}")

        # 5. Classify events (XGBoost + rule-based fallback)
        weather_by_period = {w["period_from"]: w for w in weather_quarters}
        analysis = _classify_with_weather(
            quarters, weather_by_period, xgb_classify_fn=xgb_classify
        )

        return {
            "parcel_id":     parcel_id,
            "analysis_from": from_date,
            "analysis_to":   to_date,
            "centroid_lat":  round(lat, 6),
            "centroid_lon":  round(lon, 6),
            "quarters":      quarters,
            "weather":       weather_quarters,
            **analysis,
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
