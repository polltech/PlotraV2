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