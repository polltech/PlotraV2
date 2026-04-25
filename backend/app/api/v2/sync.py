"""
Plotra Platform - Sync API Endpoints
Delta-sync with deduplication and conflict detection for 2G conditions.

KPIs:
- Sync Success Rate: >99.5%
- Conflict Resolution SLA: <48h
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_farmer, require_coop_admin
from app.models.user import User
from app.services.delta_sync import (
    DeltaSyncEngine, DeltaSyncPayload, SyncResult, ConflictRecord,
    ConflictResolutionService, ConflictDetector, SyncStatus
)

router = APIRouter(prefix="/sync", tags=["Sync & Conflict Resolution"])


class SyncRecord(BaseModel):
    """Single record for delta sync."""
    entity_type: str
    id: Optional[str] = None
    farm_id: Optional[str] = None
    parcel_id: Optional[str] = None
    version: int = 1
    updated_at: Optional[str] = None
    checksum: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    boundary_geojson: Optional[Dict] = None
    gps_accuracy_meters: Optional[float] = None


class SyncPayload(BaseModel):
    """Delta sync payload from mobile client."""
    device_id: str
    last_sync_timestamp: Optional[str] = None
    records: List[SyncRecord] = Field(default_factory=list)
    checksum: Optional[str] = None


class SyncPayloadResponse(BaseModel):
    """Response to sync payload."""
    success: bool
    synced_count: int
    conflict_count: int
    failed_count: int
    server_timestamp: str
    retry_recommended: bool
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)


class ConflictResponse(BaseModel):
    """Conflict resolution response."""
    id: str
    conflict_type: str
    entity_type: str
    entity_id: str
    severity: str
    created_at: str
    status: str
    local_data: Dict[str, Any]
    server_data: Dict[str, Any]


@router.post("/delta", response_model=SyncPayloadResponse)
async def delta_sync(
    payload: SyncPayload,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit delta sync from mobile client.
    
    Supports:
    - Parcel GPS data
    - Practice log entries
    - Delivery records
    - Photos
    
    Returns counts and any conflicts requiring resolution.
    """
    delta_payload = DeltaSyncPayload(
        device_id=payload.device_id,
        last_sync_timestamp=datetime.fromisoformat(payload.last_sync_timestamp) if payload.last_sync_timestamp else None,
        records=[r.model_dump() for r in payload.records],
        checksum=payload.checksum
    )
    
    result = await DeltaSyncEngine.process_delta_sync(db, delta_payload, current_user.id)
    
    return SyncPayloadResponse(
        success=result.success,
        synced_count=result.synced_count,
        conflict_count=result.conflict_count,
        failed_count=result.failed_count,
        server_timestamp=result.server_timestamp.isoformat(),
        retry_recommended=result.retry_recommended,
        conflicts=result.conflicts
    )


@router.get("/conflicts", response_model=List[ConflictResponse])
async def get_pending_conflicts(
    coop_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get pending conflicts for cooperative managers.
    
    Requires: COOPERATIVE_OFFICER role or higher.
    """
    conflicts = await ConflictResolutionService.get_pending_conflicts(db, coop_id, limit)
    
    return [
        ConflictResponse(
            id=c.id,
            conflict_type=c.conflict_type,
            entity_type=c.entity_type,
            entity_id=c.entity_id,
            severity=c.severity.value if hasattr(c.severity, 'value') else str(c.severity),
            created_at=c.created_at.isoformat() if c.created_at else "",
            status=c.status,
            local_data=c.local_version or {},
            server_data=c.server_version or {}
        )
        for c in conflicts
    ]


class ConflictResolutionRequest(BaseModel):
    """Request to resolve a conflict."""
    resolution: str = Field(description="keep_local, keep_server, merge, resurvey")
    resolution_data: Optional[Dict[str, Any]] = None


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    resolution: ConflictResolutionRequest,
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Resolve a polygon conflict.
    
    Resolution options:
    - keep_local: Use mobile device data
    - keep_server: Keep server version
    - merge: Manual merge (resolution_data contains merged data)
    - resurvey: Requires new boundary photo
    
    SLA: Resolution must be completed within 48 hours.
    """
    result = await ConflictResolutionService.resolve_conflict(
        db, conflict_id, resolution.resolution, current_user.id, resolution.resolution_data
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    return result


@router.get("/sla-alerts")
async def check_sla_alerts(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Check for SLA breach alerts.
    
    Alerts at 36h and 44h marks.
    Critical alert at 44h (4h before 48h SLA).
    """
    alerts = await ConflictResolutionService.check_sla_alerts(db)
    
    return {"alerts": alerts}


@router.get("/stats")
async def get_sync_stats(
    current_user: User = Depends(require_coop_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync statistics for cooperative.
    """
    from app.models.system import SyncLog
    from sqlalchemy import select, func
    
    stats_result = await db.execute(
        select(
            func.count(SyncLog.id).label('total_syncs'),
            func.sum(SyncLog.synced_count).label('total_synced'),
            func.sum(SyncLog.conflict_count).label('total_conflicts'),
            func.sum(SyncLog.failed_count).label('total_failed')
        ).where(SyncLog.user_id == current_user.id)
    )
    
    stats = stats_result.one()
    
    total_syncs = stats.total_syncs or 0
    total_synced = stats.total_synced or 0
    total_failed = stats.total_failed or 0
    
    success_rate = (total_synced / total_syncs * 100) if total_syncs > 0 else 100
    
    return {
        "total_syncs": total_syncs,
        "total_synced": total_synced,
        "total_conflicts": stats.total_conflicts or 0,
        "total_failed": total_failed,
        "success_rate": round(success_rate, 2),
        "meets_kpi": success_rate >= 99.5
    }