"""
Plotra Platform - API v2 Router
Main API router combining all v2 endpoints
"""
from fastapi import APIRouter, Depends
from app.api.v2 import auth, farmer, coop, admin, sustainability, debug, sync, gis, satellite, eudr, system_config

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(farmer.router, prefix="/farmer", tags=["Farmer"])
api_router.include_router(coop.router, prefix="/coop", tags=["Cooperative"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(sustainability.router, prefix="/sustainability", tags=["Sustainability & Incentives"])
api_router.include_router(debug.router, prefix="/debug", tags=["Debug"])
api_router.include_router(sync.router, prefix="", tags=["Delta Sync & Conflict Resolution"])
api_router.include_router(gis.router, prefix="", tags=["Geospatial & Polygon Validation"])
api_router.include_router(satellite.router, prefix="", tags=["Satellite Analysis"])
api_router.include_router(eudr.router, prefix="", tags=["EUDR & DDS"])
api_router.include_router(system_config.router, prefix="/admin/config", tags=["System Configuration"])
