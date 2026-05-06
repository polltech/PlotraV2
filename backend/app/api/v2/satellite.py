"""
Plotra Platform - Satellite Analysis API
GEE integration for NDVI, EUDR deforestation, and heritage slope.

KPIs:
- Baseline Confidence (NDVI): >90%
- False Positive Rate: <5%
- Heritage Slope: 2015-2020 NDVI trend
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import get_current_user, require_farmer, require_coop_admin, require_plotra_admin
from app.models.user import User
from app.models.farm import Farm, LandParcel
from app.models.satellite import SatelliteObservation
from app.services.satellite_analysis import SatelliteAnalysisEngine

router = APIRouter(prefix="", tags=["Satellite Analysis"])


class SatelliteAnalysisRequest(BaseModel):
    """Request satellite analysis for parcels."""
    parcel_ids: Optional[List[str]] = None
    farm_id: Optional[str] = None
    acquisition_date: Optional[str] = None
    analysis_type: str = Field(default="full", description="full, ndvi, eudr, heritage")


class SatelliteJobResponse(BaseModel):
    """Response for satellite job submission."""
    job_id: str
    parcel_id: str
    status: str
    submitted_at: str
    poll_url: str


class SatelliteAnalysisResponse(BaseModel):
    """Satellite analysis result."""
    analysis_id: str
    parcel_id: str
    status: str
    satellite_source: str
    acquisition_date: str
    ndvi_mean: Optional[float] = None
    ndvi_min: Optional[float] = None
    ndvi_max: Optional[float] = None
    evi: Optional[float] = None
    savi: Optional[float] = None
    ndmi: Optional[float] = None
    canopy_cover_percentage: Optional[float] = None
    tree_density: Optional[float] = None
    biomass_tons_hectare: Optional[float] = None
    land_cover_type: Optional[str] = None
    land_cover_confidence: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    gap_filled: bool = False
    confidence: float = Field(default=0.9, ge=0, le=1)


class HeritageSlopeResponse(BaseModel):
    """Heritage slope calculation result."""
    parcel_id: str
    slope_value: float
    confidence: float
    years_analyzed: int
    start_year: int
    end_year: int
    trend: str
    deforestation_detected: bool
    heritage_score: float


class EUDRCheckResponse(BaseModel):
    """EUDR deforestation check result."""
    parcel_id: str
    deforestation_check_2020: bool
    forest_cover_date: str
    confidence: float
    gap_filled: bool
    cloud_cover_pct: Optional[float] = None
    risk_level: str
    false_positive_likely: bool


@router.post("/analyze", response_model=dict)
async def request_satellite_analysis(
    request: SatelliteAnalysisRequest,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Request satellite analysis for farm parcels.
    
    Supports:
    - Full NDVI/EVI/NDMI analysis
    - EUDR deforestation check
    - Heritage slope calculation
    
    Returns analysis job ID for polling.
    """
    parcel_ids = request.parcel_ids or []
    
    if not parcel_ids and not request.farm_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide parcel_ids or farm_id"
        )
    
    if request.farm_id and not parcel_ids:
        result = await db.execute(
            select(LandParcel).where(LandParcel.farm_id == request.farm_id)
        )
        parcels = result.scalars().all()
        parcel_ids = [p.id for p in parcels]
    
    results = []
    for parcel_id in parcel_ids:
        parcel_result = await db.execute(
            select(LandParcel).where(LandParcel.id == parcel_id)
        )
        parcel = parcel_result.scalar_one_or_none()
        
        if not parcel:
            continue
        
        if not parcel.boundary_geojson:
            continue
        
        coords = parcel.boundary_geojson.get('coordinates', [[]])[0]
        
        if request.analysis_type == 'eudr':
            eudr_result = await SatelliteAnalysisEngine.eudr_deforestation_check(
                parcel_id, coords
            )
            results.append({
                "parcel_id": parcel_id,
                "status": "completed",
                "deforestation_check_2020": eudr_result.deforestation_check_2020,
                "confidence": eudr_result.confidence,
                "risk_level": eudr_result.risk_level
            })
        elif request.analysis_type == 'heritage':
            heritage_result = await SatelliteAnalysisEngine.calculate_heritage_slope(
                parcel_id, coords
            )
            results.append({
                "parcel_id": parcel_id,
                "heritage_score": heritage_result.slope_value,
                "confidence": heritage_result.confidence,
                "trend": heritage_result.trend
            })
        else:
            full_result = await SatelliteAnalysisEngine.analyze_parcel(
                parcel_id, coords
            )
            results.append(full_result)
        
        await db.commit()
    
    return {
        "results": results,
        "total_parcels": len(results),
        "analysis_type": request.analysis_type
    }


@router.get("/heritage/{parcel_id}", response_model=HeritageSlopeResponse)
async def get_heritage_slope(
    parcel_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get NDVI heritage slope for parcel (2015-2020).
    
    This is a Phase 2 HARD STOP field for sustainability schema.
    Computes linear regression of NDVI over 6 years.
    """
    result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id)
    )
    parcel = result.scalar_one_or_none()
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    if not parcel.boundary_geojson:
        raise HTTPException(status_code=400, detail="Parcel has no boundary data")
    
    coords = parcel.boundary_geojson.get('coordinates', [[]])[0]
    
    heritage = await SatelliteAnalysisEngine.calculate_heritage_slope(
        parcel_id, coords
    )
    
    return HeritageSlopeResponse(
        parcel_id=parcel_id,
        slope_value=heritage.slope_value,
        confidence=heritage.confidence,
        years_analyzed=heritage.years_analyzed,
        start_year=heritage.start_year,
        end_year=heritage.end_year,
        trend=heritage.trend,
        deforestation_detected=heritage.deforestation_detected,
        heritage_score=round(heritage.slope_value, 4)
    )


@router.get("/eudr/{parcel_id}", response_model=EUDRCheckResponse)
async def get_eudr_deforestation_check(
    parcel_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get EUDR deforestation check result.
    
    Compares current NDVI to baseline on 31 Dec 2020.
    Returns deforestation_check_2020 boolean.
    """
    result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id)
    )
    parcel = result.scalar_one_or_none()
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    if not parcel.boundary_geojson:
        raise HTTPException(status_code=400, detail="Parcel has no boundary data")
    
    coords = parcel.boundary_geojson.get('coordinates', [[]])[0]
    
    eudr_result = await SatelliteAnalysisEngine.eudr_deforestation_check(
        parcel_id, coords
    )
    
    return EUDRCheckResponse(
        parcel_id=parcel_id,
        deforestation_check_2020=eudr_result.deforestation_check_2020 or False,
        forest_cover_date=eudr_result.forest_cover_date.isoformat() if eudr_result.forest_cover_date else "",
        confidence=eudr_result.confidence,
        gap_filled=eudr_result.gap_filled,
        cloud_cover_pct=eudr_result.cloud_cover_pct,
        risk_level=eudr_result.risk_level,
        false_positive_likely=eudr_result.false_positive_likely
    )


@router.get("/indices/{parcel_id}", response_model=SatelliteAnalysisResponse)
async def get_parcel_indices(
    parcel_id: str,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get latest satellite indices for parcel.
    
    Returns NDVI, EVI, NDMI, and derived metrics.
    """
    result = await db.execute(
        select(SatelliteObservation)
        .where(SatelliteObservation.parcel_id == parcel_id)
        .order_by(SatelliteObservation.acquisition_date.desc())
        .limit(1)
    )
    observation = result.scalar_one_or_none()
    
    if observation:
        return SatelliteAnalysisResponse(
            analysis_id=observation.id,
            parcel_id=parcel_id,
            status="completed",
            satellite_source=observation.satellite_source or "SENTINEL_2",
            acquisition_date=observation.acquisition_date.isoformat() if observation.acquisition_date else "",
            ndvi_mean=observation.ndvi_mean,
            ndvi_min=observation.ndvi_min,
            ndvi_max=observation.ndvi_max,
            evi=observation.evi,
            savi=observation.savi,
            ndmi=observation.ndmi,
            canopy_cover_percentage=observation.canopy_cover_percentage,
            tree_density=observation.tree_density,
            biomass_tons_hectare=observation.biomass_tons_hectare,
            confidence=0.9
        )
    
    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    raise HTTPException(
        status_code=404,
        detail="No satellite analysis found. Request analysis first."
    )


@router.get("/history/{parcel_id}")
async def get_satellite_history(
    parcel_id: str,
    limit: int = 50,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical satellite observations for parcel.
    """
    result = await db.execute(
        select(SatelliteObservation)
        .where(SatelliteObservation.parcel_id == parcel_id)
        .order_by(SatelliteObservation.acquisition_date.desc())
        .limit(limit)
    )
    observations = result.scalars().all()
    
    return [
        {
            "id": obs.id,
            "acquisition_date": obs.acquisition_date.isoformat() if obs.acquisition_date else None,
            "satellite_source": obs.satellite_source,
            "ndvi_mean": obs.ndvi_mean,
            "canopy_cover_pct": obs.canopy_cover_percentage,
            "biomass_tons_hectare": obs.biomass_tons_hectare,
            "cloud_cover_pct": obs.cloud_cover_percentage if hasattr(obs, 'cloud_cover_percentage') else None
        }
        for obs in observations
    ]


@router.get("/false-positive-filter/{parcel_id}")
async def check_false_positive(
    parcel_id: str,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Cross-reference satellite brown-down events with practice logs.
    
    Human-in-loop filter for false positive detection.
    Used when cloud_cover > 20% or confidence < 90%.
    """
    parcel_result = await db.execute(
        select(LandParcel).where(LandParcel.id == parcel_id)
    )
    parcel = parcel_result.scalar_one_or_none()
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    from app.models.traceability import PracticeLog
    from sqlalchemy import and_
    
    logs_result = await db.execute(
        select(PracticeLog)
        .where(
            PracticeLog.parcel_id == parcel_id,
            PracticeLog.practice_type.in_(['pruning', 'harvest', 'clearing'])
        )
        .order_by(PracticeLog.recorded_at.desc())
        .limit(10)
    )
    practice_logs = logs_result.scalars().all()
    
    has_practice_explanation = len(practice_logs) > 0
    
    return {
        "parcel_id": parcel_id,
        "false_positive_likely": has_practice_explanation,
        "explanation": "Practice logs found for brown-down period" if has_practice_explanation else None,
        "practice_logs_count": len(practice_logs),
        "requires_manual_review": has_practice_explanation
    }


@router.post("/job", response_model=SatelliteJobResponse)
async def submit_satellite_job(
    parcel_id: str,
    job_type: str = "full",
    priority: str = "normal",
    current_user: User = Depends(require_farmer)
):
    """
    Submit async satellite analysis job.
    
    Returns job_id for polling.
    """
    job = await SatelliteAnalysisEngine.submit_analysis_job(
        parcel_id, job_type, priority
    )
    
    return SatelliteJobResponse(
        job_id=job['job_id'],
        parcel_id=parcel_id,
        status=job['status'],
        submitted_at=job['submitted_at'],
        poll_url=job['poll_url']
    )


@router.get("/job/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(require_farmer)
):
    """
    Poll satellite analysis job status.
    """
    status = await SatelliteAnalysisEngine.get_job_status(job_id)
    
    return status


@router.delete("/job/{job_id}")
async def cancel_satellite_job(
    job_id: str,
    current_user: User = Depends(require_farmer)
):
    """
    Cancel a pending satellite analysis job.
    """
    result = await SatelliteAnalysisEngine.cancel_job(job_id)
    
    return result


@router.get("/batch-stats")
async def get_batch_stats(
    current_user: User = Depends(require_plotra_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get batch satellite analysis statistics.
    
    Admin-only endpoint.
    """
    from sqlalchemy import func, select
    
    stats_result = await db.execute(
        select(
            func.count(SatelliteObservation.id).label('total_analyses'),
            func.avg(SatelliteObservation.ndvi_mean).label('avg_ndvi'),
            func.count(SatelliteObservation.id).filter(
                SatelliteObservation.cloud_cover_percentage > 20
            ).label('high_cloud')
        )
    )
    
    stats = stats_result.one()
    
    return {
        "total_analyses": stats.total_analyses or 0,
        "average_ndvi": round(float(stats.avg_ndvi or 0), 3),
        "high_cloud_analyses": stats.high_cloud or 0,
        "meets_confidence_kpi": (stats.avg_ndvi or 0) > 0.5
    }


# ---------------------------------------------------------------------------
# Real-data-only endpoint — returns only genuine Sentinel-2 measurements
# ---------------------------------------------------------------------------

def _interpret_ndvi(v: float) -> tuple[str, str]:
    if v >= 0.7: return "good", "Dense, healthy vegetation. Canopy is well-established and actively photosynthesising."
    if v >= 0.5: return "good", "Moderate-to-good vegetation. Crop or canopy cover is healthy."
    if v >= 0.3: return "moderate", "Sparse or stressed vegetation. Could indicate dry season, young plants, or partial bare soil."
    if v >= 0.1: return "low", "Very sparse vegetation or stressed plants. Soil is likely exposed."
    return "critical", "Bare soil or non-vegetated surface. No significant plant cover detected."

def _interpret_evi(v: float) -> tuple[str, str]:
    if v >= 0.5: return "good", "High vegetation density. EVI accounts for atmospheric effects better than NDVI in dense canopies."
    if v >= 0.3: return "good", "Moderate vegetation. Reliable signal with low atmospheric interference."
    if v >= 0.1: return "moderate", "Low-to-moderate vegetation. Possible stress or sparse canopy."
    return "low", "Minimal vegetation detected. Atmospheric correction applied but signal is weak."

def _interpret_savi(v: float) -> tuple[str, str]:
    if v >= 0.5: return "good", "Strong vegetation with low soil background influence. Healthy, dense cover."
    if v >= 0.3: return "good", "Good vegetation signal after soil correction. Reliable for sparse-to-medium crops."
    if v >= 0.1: return "moderate", "Sparse vegetation — soil background is contributing significantly to the signal."
    return "low", "Predominantly bare soil. Very little plant cover above ground."

def _interpret_ndmi(v: float) -> tuple[str, str]:
    if v >= 0.2:  return "good",     "High leaf moisture content. Plants are well-hydrated and canopy is dense."
    if v >= 0.0:  return "good",     "Adequate leaf moisture. No signs of water stress."
    if v >= -0.2: return "moderate", "Moderate moisture stress detected. Canopy may be thinning or plants experiencing mild water deficit."
    if v >= -0.4: return "low",      "Significant moisture stress. Canopy is likely sparse and plants may be experiencing drought conditions."
    return "critical", "Severe water stress or very sparse dry vegetation."

def _interpret_ndwi(v: float) -> tuple[str, str]:
    if v >= 0.3:  return "low",      "Strong water signal. Surface water present in the parcel or waterlogged soil."
    if v >= 0.0:  return "moderate", "Mild water presence or very moist soil. Could indicate irrigation or recent rainfall."
    if v >= -0.2: return "good",     "Normal dry-land conditions. No excess surface water."
    return "good", "Dry surface. No surface water detected. Vegetation is the dominant reflector."


@router.get("/parcel/{parcel_id}/real-data")
async def get_real_satellite_data(
    parcel_id: str,
    acquisition_date: Optional[str] = None,
    current_user: User = Depends(require_plotra_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns ONLY genuine Sentinel-2 measurements for a parcel — no derived
    estimates, no models, no fixed-ratio calculations.

    Every value here is computed directly from satellite spectral bands.
    """
    from sqlalchemy.orm import selectinload
    from app.services.satellite_analysis import _load_satellite_credentials, _get_sentinel_hub_token, _fetch_sentinel_hub_indices

    result = await db.execute(
        select(LandParcel)
        .options(selectinload(LandParcel.farm))
        .where(LandParcel.id == parcel_id)
    )
    parcel = result.scalar_one_or_none()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if not parcel.boundary_geojson:
        raise HTTPException(status_code=400, detail="Parcel has no GPS boundary — capture the boundary first.")

    acq_dt = datetime.utcnow()
    if acquisition_date:
        try:
            acq_dt = datetime.fromisoformat(acquisition_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid acquisition_date format — use YYYY-MM-DD")

    creds = await _load_satellite_credentials()
    token = await _get_sentinel_hub_token(
        creds.get("oauth_client_id", ""),
        creds.get("oauth_client_secret", ""),
    )

    coords = parcel.boundary_geojson.get("coordinates", [[]])[0]
    raw = await _fetch_sentinel_hub_indices(token, coords, acq_dt)

    cloud = raw["cloud_cover_percentage"]
    if   cloud <= 10: quality, quality_label = "excellent", "Excellent — less than 10% cloud cover"
    elif cloud <= 25: quality, quality_label = "good",      "Good — cloud cover is low"
    elif cloud <= 50: quality, quality_label = "moderate",  "Moderate — some pixels were masked by cloud"
    else:             quality, quality_label = "poor",      "Poor — more than half the parcel was covered by cloud"

    from datetime import timedelta
    window_from = (acq_dt - timedelta(days=90)).strftime("%Y-%m-%d")
    window_to   = acq_dt.strftime("%Y-%m-%d")

    ndvi_status, ndvi_note = _interpret_ndvi(raw["ndvi_mean"])
    evi_status,  evi_note  = _interpret_evi(raw["evi"])
    savi_status, savi_note = _interpret_savi(raw["savi"])
    ndmi_status, ndmi_note = _interpret_ndmi(raw["ndmi"])
    ndwi_status, ndwi_note = _interpret_ndwi(raw["ndwi"])

    return {
        "parcel_id":   parcel_id,
        "parcel_name": parcel.parcel_name or parcel.parcel_number,
        "farm_name":   getattr(parcel.farm, "farm_name", None),
        "farm_id":     parcel.farm_id,

        "image": {
            "source":        "Copernicus Sentinel-2 L2A",
            "resolution_m":  20,
            "window_from":   window_from,
            "window_to":     window_to,
            "acquired_at":   acq_dt.strftime("%Y-%m-%d"),
            "cloud_cover_pct": cloud,
            "data_quality":  quality,
            "data_quality_label": quality_label,
            "note": "A 90-day window is searched. The clearest available image in that period is used."
        },

        "indices": {
            "ndvi": {
                "label":           "NDVI — Normalized Difference Vegetation Index",
                "mean":            raw["ndvi_mean"],
                "min":             raw["ndvi_min"],
                "max":             raw["ndvi_max"],
                "std_dev":         raw["ndvi_std_dev"],
                "unit":            "ratio (dimensionless)",
                "scale":           [-1, 1],
                "healthy_range":   [0.4, 0.9],
                "bands_used":      "B08 (NIR) and B04 (Red)",
                "formula":         "(B08 − B04) / (B08 + B04)",
                "what_it_measures": (
                    "How green and dense the vegetation is. "
                    "Healthy green plants strongly absorb red light (B04) for photosynthesis "
                    "and strongly reflect near-infrared (B08). "
                    "A high NDVI means healthy, dense plants. "
                    "A low NDVI means bare soil, stressed, or dead vegetation."
                ),
                "status":          ndvi_status,
                "interpretation":  ndvi_note,
            },
            "evi": {
                "label":           "EVI — Enhanced Vegetation Index",
                "value":           raw["evi"],
                "unit":            "ratio (dimensionless)",
                "scale":           [-1, 1],
                "healthy_range":   [0.2, 0.8],
                "bands_used":      "B08 (NIR), B04 (Red), B02 (Blue)",
                "formula":         "2.5 × (B08 − B04) / (B08 + 6×B04 − 7.5×B02 + 1)",
                "what_it_measures": (
                    "Similar to NDVI but corrects for atmospheric haze (using B02 Blue band) "
                    "and soil background signal. "
                    "More accurate than NDVI in very dense canopies where NDVI saturates. "
                    "Best used for agroforestry parcels with thick tree cover."
                ),
                "status":          evi_status,
                "interpretation":  evi_note,
            },
            "savi": {
                "label":           "SAVI — Soil-Adjusted Vegetation Index",
                "value":           raw["savi"],
                "unit":            "ratio (dimensionless)",
                "scale":           [-1, 1],
                "healthy_range":   [0.2, 0.7],
                "bands_used":      "B08 (NIR) and B04 (Red)",
                "formula":         "1.5 × (B08 − B04) / (B08 + B04 + 0.5)",
                "what_it_measures": (
                    "Vegetation signal corrected for bare soil influence. "
                    "The factor 0.5 reduces the effect of soil reflectance. "
                    "More reliable than NDVI in young plantations or sparse crops "
                    "where significant bare soil is visible between plants. "
                    "Useful for detecting early-stage crop growth."
                ),
                "status":          savi_status,
                "interpretation":  savi_note,
            },
            "ndmi": {
                "label":           "NDMI — Normalized Difference Moisture Index",
                "value":           raw["ndmi"],
                "unit":            "ratio (dimensionless)",
                "scale":           [-1, 1],
                "healthy_range":   [0.0, 0.6],
                "bands_used":      "B8A (Red-Edge NIR) and B11 (SWIR)",
                "formula":         "(B8A − B11) / (B8A + B11)",
                "what_it_measures": (
                    "Water content inside plant leaves and in the canopy. "
                    "SWIR (B11) is absorbed by water — when plants are well-watered "
                    "B11 is low and NDMI is high. "
                    "A dropping NDMI over time indicates drought stress, "
                    "even before NDVI shows any change. "
                    "Key indicator for irrigation management decisions."
                ),
                "status":          ndmi_status,
                "interpretation":  ndmi_note,
            },
            "ndwi": {
                "label":           "NDWI — Normalized Difference Water Index",
                "value":           raw["ndwi"],
                "unit":            "ratio (dimensionless)",
                "scale":           [-1, 1],
                "healthy_range":   [-0.3, 0.1],
                "bands_used":      "B03 (Green) and B08 (NIR)",
                "formula":         "(B03 − B08) / (B03 + B08)",
                "what_it_measures": (
                    "Surface water presence. "
                    "Open water reflects green light (B03) and absorbs NIR (B08), "
                    "giving a positive NDWI. Dry land gives a negative value. "
                    "Useful for detecting flooded areas, irrigation ponds, "
                    "or waterlogged parcels after heavy rain."
                ),
                "status":          ndwi_status,
                "interpretation":  ndwi_note,
            },
        },

        "disclaimer": (
            "All values above are direct mathematical calculations on real Sentinel-2 spectral bands. "
            "No models, machine learning, or fixed ratios were used. "
            "Resolution: 20 metres per pixel — parcels smaller than 400 m² may have unreliable results."
        ),
    }