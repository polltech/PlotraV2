"""
Plotra Platform - API v2 Router
Main API router combining all v2 endpoints
"""
from fastapi import APIRouter, Depends
from app.api.v2 import auth, farmer, coop, admin, sustainability, debug

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(farmer.router, prefix="/farmer", tags=["Farmer"])
api_router.include_router(coop.router, prefix="/coop", tags=["Cooperative"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(sustainability.router, prefix="/sustainability", tags=["Sustainability & Incentives"])
api_router.include_router(debug.router, prefix="/debug", tags=["Debug"])
