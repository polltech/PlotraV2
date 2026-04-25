"""
Plotra Platform - System Configuration API
Manage system settings, env credentials, and configurations
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_platform_admin
from app.models.user import User
from app.models.system import SystemConfig

router = APIRouter(prefix="/admin/config", tags=["System Configuration"])


class SystemSettingUpdate(BaseModel):
    """Update a system setting."""
    key: str
    value: Any
    description: Optional[str] = None
    is_public: bool = False


class EnvCredentialUpdate(BaseModel):
    """Add or update an environment credential."""
    key: str
    value: str
    description: Optional[str] = None
    is_public: bool = False


class SystemSettingResponse(BaseModel):
    """System setting response."""
    key: str
    value: Any
    description: Optional[str] = None
    is_public: bool
    is_active: bool
    updated_at: Optional[str] = None


class SystemSettingsListResponse(BaseModel):
    """List of system settings."""
    settings: List[SystemSettingResponse]
    total: int


@router.get("/settings", response_model=SystemSettingsListResponse)
async def get_all_system_settings(
    include_inactive: bool = False,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all system settings."""
    from sqlalchemy import select
    
    query = select(SystemConfig)
    if not include_inactive:
        query = query.where(SystemConfig.is_active == True)
    
    query = query.order_by(SystemConfig.config_key)
    result = await db.execute(query)
    settings = result.scalars().all()
    
    return SystemSettingsListResponse(
        settings=[
            SystemSettingResponse(
                key=s.config_key,
                value=s.config_value,
                description=s.description,
                is_public=s.is_public or False,
                is_active=s.is_active or True,
                updated_at=s.updated_at.isoformat() if s.updated_at else None
            )
            for s in settings
        ],
        total=len(settings)
    )


@router.get("/settings/{key}", response_model=SystemSettingResponse)
async def get_system_setting(
    key: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific system setting."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )
    setting = result.scalar_one_or_none()
    
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    
    return SystemSettingResponse(
        key=setting.config_key,
        value=setting.config_value,
        description=setting.description,
        is_public=setting.is_public or False,
        is_active=setting.is_active or True,
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None
    )


@router.put("/settings/{key}", response_model=SystemSettingResponse)
async def update_system_setting(
    key: str,
    update: SystemSettingUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update or create a system setting."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )
    setting = result.scalar_one_or_none()
    
    now = datetime.utcnow()
    
    if setting:
        setting.config_value = update.value
        setting.description = update.description or setting.description
        setting.is_public = update.is_public
        setting.is_active = True
        setting.updated_at = now
    else:
        setting = SystemConfig(
            config_key=key,
            config_value=update.value,
            description=update.description,
            is_public=update.is_public,
            is_active=True
        )
        db.add(setting)
    
    await db.commit()
    await db.refresh(setting)
    
    return SystemSettingResponse(
        key=setting.config_key,
        value=setting.config_value,
        description=setting.description,
        is_public=setting.is_public or False,
        is_active=setting.is_active or True,
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None
    )


@router.delete("/settings/{key}")
async def delete_system_setting(
    key: str,
    hard_delete: bool = False,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete or deactivate a system setting."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )
    setting = result.scalar_one_or_none()
    
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    
    if hard_delete:
        await db.delete(setting)
        await db.commit()
        return {"message": f"Setting '{key}' deleted"}
    else:
        setting.is_active = False
        setting.updated_at = datetime.utcnow()
        await db.commit()
        return {"message": f"Setting '{key}' deactivated"}


@router.get("/env-credentials")
async def get_env_credentials(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all stored environment credentials (only non-sensitive ones)."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "env_credentials")
    )
    cfg = result.scalar_one_or_none()
    
    credentials = cfg.config_value if (cfg and cfg.config_value) else {}
    
    # Filter out sensitive values
    public_credentials = {}
    for key, data in credentials.items():
        if isinstance(data, dict):
            if data.get("is_public", False):
                public_credentials[key] = {
                    "value": data.get("value", "***HIDDEN***") if not data.get("is_public") else data.get("value"),
                    "description": data.get("description"),
                    "is_public": True
                }
            else:
                public_credentials[key] = {
                    "value": "***HIDDEN***",
                    "description": data.get("description"),
                    "is_public": False
                }
        else:
            public_credentials[key] = "***HIDDEN***"
    
    return {"credentials": public_credentials}


@router.put("/env-credentials")
async def upsert_env_credential(
    credential: EnvCredentialUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add or update an environment credential."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "env_credentials")
    )
    cfg = result.scalar_one_or_none()
    
    credentials = cfg.config_value if (cfg and cfg.config_value) else {}
    credentials[credential.key] = {
        "value": credential.value,
        "description": credential.description,
        "is_public": credential.is_public,
        "updated_at": datetime.utcnow().isoformat(),
        "updated_by": current_user.id
    }
    
    if cfg:
        cfg.config_value = credentials
        cfg.updated_at = datetime.utcnow()
    else:
        cfg = SystemConfig(
            config_key="env_credentials",
            config_value=credentials,
            description="Stored environment credentials",
            is_public=False
        )
        db.add(cfg)
    
    await db.commit()
    
    return {
        "message": f"Credential '{credential.key}' saved",
        "key": credential.key,
        "is_public": credential.is_public
    }


@router.delete("/env-credentials/{key}")
async def delete_env_credential(
    key: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Remove an environment credential."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "env_credentials")
    )
    cfg = result.scalar_one_or_none()
    
    if not cfg or not cfg.config_value or key not in cfg.config_value:
        raise HTTPException(status_code=404, detail=f"Credential '{key}' not found")
    
    del cfg.config_value[key]
    cfg.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": f"Credential '{key}' deleted"}


@router.get("/session-timeout")
async def get_session_timeout(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get current session timeout setting."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "session_timeout")
    )
    cfg = result.scalar_one_or_none()
    
    if cfg and cfg.config_value:
        return {"session_timeout_minutes": cfg.config_value.get("timeout_minutes", 60)}
    
    return {"session_timeout_minutes": 60}


@router.put("/session-timeout")
async def update_session_timeout(
    timeout_minutes: int,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update session timeout."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "session_timeout")
    )
    cfg = result.scalar_one_or_none()
    
    now = datetime.utcnow()
    
    if cfg:
        cfg.config_value = {"timeout_minutes": timeout_minutes}
        cfg.updated_at = now
    else:
        cfg = SystemConfig(
            config_key="session_timeout",
            config_value={"timeout_minutes": timeout_minutes},
            description="Session timeout in minutes",
            is_public=True
        )
        db.add(cfg)
    
    await db.commit()
    
    return {"session_timeout_minutes": timeout_minutes, "message": "Session timeout updated"}


@router.get("/system-info")
async def get_system_info(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get system information."""
    from sqlalchemy import select, func
    
    user_count = await db.execute(select(func.count()).select_from(User))
    coop_count = await db.execute(select(func.count()).select_from(Cooperative))
    
    return {
        "app_name": "Kipawa Platform",
        "version": "1.0.0",
        "total_users": user_count.scalar() or 0,
        "total_cooperatives": coop_count.scalar() or 0,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/export-config")
async def export_configuration(
    include_credentials: bool = False,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Export all system configuration as .env format."""
    from sqlalchemy import select
    
    result = await db.execute(select(SystemConfig))
    settings = result.scalars().all()
    
    env_lines = []
    for s in settings:
        key = s.config_key.upper().replace("-", "_")
        value = s.config_value
        
        # Skip credentials unless explicitly requested
        if s.config_key == "env_credentials" and not include_credentials:
            continue
        
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, dict):
                    if sub_value.get("is_public") or include_credentials:
                        env_lines.append(f"{key}__{sub_key.upper()}={sub_value.get('value', '')}")
                else:
                    env_lines.append(f"{key}__{sub_key.upper()}={sub_value}")
        elif isinstance(value, str):
            env_lines.append(f"{key}={value}")
        elif isinstance(value, (int, float, bool)):
            env_lines.append(f"{key}={value}")
    
    return {
        "filename": "plotra-export.env",
        "lines": env_lines,
        "total_settings": len(settings)
    }


@router.post("/import-config")
async def import_configuration(
    settings_data: Dict[str, Any],
    overwrite: bool = True,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db)
):
    """Import configuration from settings dict."""
    from sqlalchemy import select
    
    imported = 0
    skipped = 0
    errors = []
    
    for key, value in settings_data.items():
        try:
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.config_key == key)
            )
            existing = result.scalar_one_or_none()
            
            if existing and not overwrite:
                skipped += 1
                continue
            
            if existing:
                existing.config_value = value
                existing.updated_at = datetime.utcnow()
            else:
                new_setting = SystemConfig(
                    config_key=key,
                    config_value=value,
                    description=f"Imported setting",
                    is_public=False
                )
                db.add(new_setting)
            
            imported += 1
            
        except Exception as e:
            errors.append(f"{key}: {str(e)}")
    
    await db.commit()
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": len(settings_data)
    }