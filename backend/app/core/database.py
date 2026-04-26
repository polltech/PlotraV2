"""
Plotra Platform - Database Connection and Session Management
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create engine options
engine_options = {
    "echo": False,  # never echo SQL; use query logging middleware if needed
    "pool_pre_ping": True,
}

# Add pool options only for non-sqlite databases (PostgreSQL)
if not settings.database.async_url.startswith("sqlite"):
    engine_options["pool_size"] = settings.database.pool_size
    engine_options["max_overflow"] = settings.database.max_overflow

# Create async engine for PostgreSQL with PostGIS
engine = create_async_engine(
    settings.database.async_url,
    **engine_options
)

# Session factory
async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safely add new columns that may not exist on older deployments
        for sql in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS update_requested BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS update_requested_by_name VARCHAR(150)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS update_request_notes TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS update_requested_at TIMESTAMP",
        ]:
            await conn.execute(__import__('sqlalchemy').text(sql))


async def close_db():
    """Close database connections"""
    await engine.dispose()


def create_test_engine():
    """Create a test engine with NullPool"""
    return create_async_engine(
        settings.database.async_url,
        poolclass=NullPool,
        echo=True,
    )
