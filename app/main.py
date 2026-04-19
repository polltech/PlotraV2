"""
Plotra Platform - EUDR Compliance & Traceability
Main FastAPI Application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import init_db, close_db
from .api.v2 import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.logging.level),
    format=settings.logging.format
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initialize and cleanup resources.
    """
    # Startup
    logger.info("Starting Plotra Platform...")
    logger.info(f"Database: {settings.database.host}:{settings.database.port}/{settings.database.name}")
    logger.info(f"Satellite Analysis: {'Simulation Mode' if settings.satellite.simulation_mode else 'Live Mode'}")
    
    # Initialize database tables
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Plotra Platform...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Plotra Platform",
    description="EUDR Compliance & Traceability Platform for East African Coffee Smallholders",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    import traceback
    logger.exception(f"Unhandled exception: {exc}")
    # Return more detailed error for debugging
    error_detail = str(exc)
    if hasattr(exc, '__traceback__'):
        error_detail = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "error": str(exc)[:200]  # Include error message for debugging
        }
    )


# Include API routers
app.include_router(api_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "plotra-platform"
    }


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Plotra Platform",
        "version": "1.0.0",
        "description": "EUDR Compliance & Traceability Platform for East African Coffee Smallholders",
        "documentation": "/api/docs",
        "health": "/health"
    }


# Readiness check (includes database connectivity)
@app.get("/ready")
async def readiness_check():
    """
    Readiness check that includes database connectivity.
    """
    from sqlalchemy import text
    
    try:
        from .core.database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ready" if db_status == "connected" else "degraded",
        "database": db_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=settings.app.debug
    )
