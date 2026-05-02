"""
Plotra Platform - EUDR Compliance & Traceability
Main FastAPI Application
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v2 import api_router

# Let uvicorn own the root logger — only set level, don't add handlers
logging.getLogger().setLevel(getattr(logging, settings.logging.level))
# Suppress noisy SQLAlchemy engine logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _is_primary_worker() -> bool:
    """True only in the first uvicorn worker so init_db runs exactly once."""
    # Uvicorn sets this env var on the parent/first worker process
    return os.environ.get("UVICORN_WORKER_ID", "0") == "0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("Starting Plotra Platform...")
    logger.info(f"Database: {settings.database.host}:{settings.database.port}/{settings.database.name}")
    logger.info(f"Satellite Analysis: {'Simulation Mode' if settings.satellite.simulation_mode else 'Live Mode'}")

    await init_db()
    logger.info("Database initialized")

    yield

    logger.info("Shutting down Plotra Platform...")
    await close_db()


# Create FastAPI application
_is_debug = settings.app.debug
app = FastAPI(
    title="Plotra Platform",
    description="EUDR Compliance & Traceability Platform for East African Coffee Smallholders",
    version="1.0.0",
    docs_url="/api/docs"      if _is_debug else None,
    redoc_url="/api/redoc"    if _is_debug else None,
    openapi_url="/api/openapi.json" if _is_debug else None,
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
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler for Pydantic validation errors - logs details for debugging.
    """
    logger.error(f"Request validation error: {exc.errors()}")
    for error in exc.errors():
        logger.error(f"  Field: {error['loc']}, Type: {error['type']}, Message: {error['msg']}")
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
        headers={"Access-Control-Allow-Origin": "*"}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    import traceback
    logger.exception(f"Unhandled exception: {exc}")
    # Return more detailed error for debugging
    error_str = str(exc)[:300]
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "error": error_str
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


# Include API routers
app.include_router(api_router, prefix="/api/v2")


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
        from app.core.database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ready" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app.debug
    )
