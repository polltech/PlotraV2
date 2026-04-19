"""
Plotra Platform - API v2 Router Configuration
"""
from fastapi import APIRouter
from .auth import router as auth
from .farmer import router as farmer
from .coop import router as coop
from .admin import router as admin
from .sustainability import router as sustainability

api_router = APIRouter(prefix="/api/v2")

# Include all route modules
api_router.include_router(auth, prefix="/auth", tags=["Authentication"])
api_router.include_router(farmer, prefix="/farmer", tags=["Farmer"])
api_router.include_router(coop, prefix="/coop", tags=["Cooperative"])
api_router.include_router(admin, prefix="/admin", tags=["Admin"])
api_router.include_router(sustainability, prefix="/sustainability", tags=["Sustainability & Incentives"])
