"""
One-time: store the EUDR API key in SystemConfig so the backend can load it.
Run: python seed_eudr_api_key.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.core.config import settings

EUDR_API_KEY = "ea_06d2ddf7a5c67c989f5d71438fa513db"


async def main():
    engine = create_async_engine(settings.database.async_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        from app.models.system import SystemConfig
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.config_key == "cfg_eudr_api_key")
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.config_value = EUDR_API_KEY
            print(f"Updated cfg_eudr_api_key")
        else:
            session.add(SystemConfig(
                config_key="cfg_eudr_api_key",
                config_value=EUDR_API_KEY,
                is_public=False,
                description="EUDR REST API key (eudr-api.eu)"
            ))
            print(f"Inserted cfg_eudr_api_key")
        await session.commit()

    await engine.dispose()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
