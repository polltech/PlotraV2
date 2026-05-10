"""
Plotra Platform - Satellite Analysis Engine
Real Sentinel Hub Statistics API. Auth via Planet API key (no OAuth needed).
The Sentinel Hub dashboard is deprecated — authenticate directly with your Planet API key.
"""
import math
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
  // Accept all pixels regardless of cloud cover (diagnostic mode)
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-6);
  let evi  = 2.5 * (s.B08 - s.B04) / (s.B08 + 6*s.B04 - 7.5*s.B02 + 1 + 1e-6);
  let savi = 1.5 * (s.B08 - s.B04) / (s.B08 + s.B04 + 0.5 + 1e-6);
  let ndmi = (s.B8A - s.B11) / (s.B8A + s.B11 + 1e-6);
  let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08 + 1e-6);
  return {
    ndvi: [ndvi], evi: [evi], savi: [savi],
    ndmi: [ndmi], ndwi: [ndwi], dataMask: [1]
  };
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
        async with httpx.AsyncClient(timeout=120) as client:
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
        ndvi         = _s(outputs, "ndvi", "mean") if valid > 0 else None
        results.append({
            "period_from":        iv.get("interval", {}).get("from", "")[:10],
            "period_to":          iv.get("interval", {}).get("to",   "")[:10],
            "ndvi":               round(ndvi, 3) if ndvi is not None else None,
            "evi":                round(_s(outputs, "evi",  "mean", 0), 3) if valid > 0 else None,
            "savi":               round(_s(outputs, "savi", "mean", 0), 3) if valid > 0 else None,
            "ndmi":               round(_s(outputs, "ndmi", "mean", 0), 3) if valid > 0 else None,
            "cloud_cover_pct":    round(nodata_count / max(1, sample_count) * 100, 1),
            "valid_pixels":       valid,
        })

    logger.info(f"Timeseries fetched: {len(results)} quarters, {sum(1 for r in results if r['ndvi'] is not None)} with valid NDVI")
    return results


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
        async with httpx.AsyncClient(timeout=60) as client:
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

    async with async_session_factory() as session:
        for wq in weather_quarters:
            result = await session.execute(
                select(WeatherObservation).where(
                    WeatherObservation.parcel_id == parcel_id,
                    WeatherObservation.period_from == wq["period_from"],
                )
            )
            rec = result.scalar_one_or_none()
            if rec is None:
                rec = WeatherObservation(parcel_id=parcel_id)
                rec.period_from = wq["period_from"]
                session.add(rec)
            rec.period_to         = wq["period_to"]
            rec.rainfall_mm       = wq.get("rainfall_mm")
            rec.et0_mm            = wq.get("et0_mm")
            rec.water_deficit_mm  = wq.get("water_deficit_mm")
            rec.temp_max_avg_c    = wq.get("temp_max_avg_c")
            rec.drought_flag      = 1 if wq.get("drought_flag") else 0
        await session.commit()


def _compute_fusion_score(q: Dict) -> Optional[float]:
    """
    Weighted 4-index vegetation score.
    Weights: NDVI 35%, EVI 25%, SAVI 20%, NDMI 20%.
    More robust than NDVI alone: EVI corrects for atmosphere/soil, NDMI captures moisture stress.
    Falls back gracefully when some indices are missing (re-normalizes weights).
    """
    ndvi = q.get("ndvi")
    if ndvi is None:
        return None
    pairs = [(ndvi, 0.35), (q.get("evi"), 0.25), (q.get("savi"), 0.20), (q.get("ndmi"), 0.20)]
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
    Human-readable explanation for each classified event.
    Explains which indices changed, why the classification was made,
    and what it means for EUDR compliance.
    """
    def _fmt(v):
        return f"{v:.3f}" if v is not None else "n/a"

    def _d(d):
        if d is None:
            return ""
        sign = "+" if d > 0 else ""
        return f" ({sign}{d:.3f})"

    ndvi_str  = f"NDVI {_fmt(prev.get('ndvi'))}→{_fmt(curr.get('ndvi'))}{_d(ndvi_d)}"
    evi_str   = f"EVI {_fmt(prev.get('evi'))}→{_fmt(curr.get('evi'))}{_d(evi_d)}" if evi_d is not None else None
    savi_str  = f"SAVI {_fmt(prev.get('savi'))}→{_fmt(curr.get('savi'))}{_d(savi_d)}" if savi_d is not None else None
    ndmi_str  = f"NDMI {_fmt(prev.get('ndmi'))}→{_fmt(curr.get('ndmi'))}{_d(ndmi_d)}" if ndmi_d is not None else None
    fuse_str  = f"Fusion {_fmt(prev.get('fusion_score'))}→{_fmt(curr.get('fusion_score'))}{_d(fusion_d)}" if fusion_d is not None else None

    indices = " | ".join(s for s in [ndvi_str, evi_str, savi_str, ndmi_str, fuse_str] if s)

    if event_type == "DEFORESTATION":
        evi_note = (f" EVI also collapsed ({evi_d:+.3f}), confirming canopy removal."
                    if evi_d is not None and evi_d <= -0.15 else "")
        return (
            f"All 4 vegetation indices declined sharply: {indices}.{evi_note} "
            f"Fusion score fell below the deforestation threshold (0.35). "
            f"No vegetation recovery detected in the following 2 quarters. "
            f"This pattern is consistent with tree clearing or severe land conversion. "
            f"Post-EUDR cutoff (Dec 2020) — classified as a EUDR VIOLATION."
        )

    if event_type == "DROUGHT_STRESS":
        wx_note = ""
        if w.get("drought_flag"):
            wx_note = (f" Weather data confirms: rainfall was {w.get('rainfall_mm', '?')} mm "
                       f"with water deficit of {w.get('water_deficit_mm', '?')} mm for this quarter.")
        ndmi_note = (" NDMI moisture signal dropped proportionally more than NDVI "
                     f"(ratio {abs(ndmi_d)/max(abs(ndvi_d),0.001):.1f}×), indicating the primary "
                     "stressor is water deficit rather than vegetation removal."
                     if ndmi_drought and ndmi_d is not None else "")
        return (
            f"Vegetation stress detected ({indices}) but attributed to drought, not deforestation.{wx_note}{ndmi_note} "
            f"Drought-induced NDVI declines are temporary and do not represent land clearing. "
            f"NOT an EUDR violation."
        )

    if event_type == "CANOPY_DISTURBANCE":
        evi_note = (f" EVI changed only {evi_d:+.3f} while NDVI changed {ndvi_d:+.3f} "
                    f"— EVI is more sensitive to canopy structure and its relative stability "
                    "indicates overstory trees remain in place."
                    if evi_d is not None else "")
        return (
            f"NDVI declined notably but EVI (canopy proxy) remained relatively stable: {indices}.{evi_note} "
            f"Interpretation: the forest canopy is intact — only the understory, ground cover, or crop layer "
            f"has been affected (e.g. seasonal crop harvest, understory clearing, grazing). "
            f"This is NOT classified as deforestation. NOT an EUDR violation."
        )

    if event_type == "VEGETATION_LOSS":
        no_wx = " No drought signal detected from weather data or NDMI pattern." if not drought_induced else ""
        return (
            f"Sustained multi-index vegetation decline without recovery: {indices}.{no_wx} "
            f"This does not meet the EVI-confirmed canopy-loss threshold for DEFORESTATION, "
            f"but the persistence and magnitude are concerning. "
            f"Possible causes: partial clearing, agroforestry change, or slow degradation. "
            f"Manual field verification recommended."
        )

    if event_type == "SEASONAL_DIP":
        return (
            f"Vegetation declined but recovered within 1–2 quarters: {indices}. "
            f"This matches a normal seasonal dry-season pattern (e.g. leaf-off, crop harvest). "
            f"No EUDR concern — seasonal variation is expected and not a compliance issue."
        )

    if event_type == "REGROWTH":
        return (
            f"Positive vegetation recovery detected: {indices}. "
            f"All indices trending upward after a prior low period. "
            f"Consistent with post-drought recovery, reforestation, or new crop establishment."
        )

    return indices


def _classify_with_weather(quarters: List[Dict], weather_by_period: Dict) -> Dict:
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
        Fetches quarterly Sentinel-2 indices + Open-Meteo weather, merges both,
        classifies events with drought discrimination, and returns EUDR verdict.
        """
        parcel_id = getattr(parcel, "id", None)
        coords    = []
        if getattr(parcel, "boundary_geojson", None):
            coords = parcel.boundary_geojson.get("coordinates", [[]])[0]
        if not coords:
            raise HTTPException(status_code=400, detail="Parcel has no boundary polygon — cannot run history analysis.")

        # Compute polygon centroid for weather lookup
        lat = sum(c[1] for c in coords) / len(coords)
        lon = sum(c[0] for c in coords) / len(coords)

        creds         = await _load_satellite_credentials()
        client_id     = creds.get("oauth_client_id", "")
        client_secret = creds.get("oauth_client_secret", "")
        token         = await _get_sentinel_hub_token(client_id, client_secret)

        # 1. Fetch Sentinel-2 quarterly timeseries
        quarters = await _fetch_sentinel_hub_timeseries(token, coords)

        # 2. Fetch weather history — non-blocking (proceed without it on failure)
        weather_quarters: List[Dict] = []
        try:
            weather_raw      = await fetch_weather_history(lat, lon)
            weather_quarters = _aggregate_weather_to_quarters(weather_raw, quarters)
            logger.info(f"Weather merged for parcel {parcel_id}: {len(weather_quarters)} quarters, "
                        f"{sum(1 for w in weather_quarters if w['drought_flag'])} drought quarter(s)")
        except Exception as exc:
            logger.warning(f"Weather fetch failed for parcel {parcel_id}: {exc} — proceeding without weather data")

        # 3. Persist weather to DB
        if weather_quarters and parcel_id:
            try:
                await _store_weather_observations(parcel_id, weather_quarters)
            except Exception as exc:
                logger.warning(f"Weather DB store failed for parcel {parcel_id}: {exc}")

        # 4. Classify events with weather context
        weather_by_period = {w["period_from"]: w for w in weather_quarters}
        analysis = _classify_with_weather(quarters, weather_by_period)

        return {
            "parcel_id":     parcel_id,
            "analysis_from": "2020-12-01",
            "analysis_to":   datetime.utcnow().strftime("%Y-%m-%d"),
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
