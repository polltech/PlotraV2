"""
Migration: add shade_trees_present and shade_tree_canopy_percent to farms table.
Run once on the server: python add_farm_shade_fields.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

DDL = [
    "ALTER TABLE farms ADD COLUMN IF NOT EXISTS shade_trees_present INTEGER DEFAULT 0;",
    "ALTER TABLE farms ADD COLUMN IF NOT EXISTS shade_tree_canopy_percent INTEGER;",
]

async def main():
    engine = create_async_engine(settings.database_url, echo=True)
    async with engine.begin() as conn:
        for stmt in DDL:
            try:
                await conn.exec_driver_sql(stmt)
                print(f"OK: {stmt}")
            except Exception as e:
                print(f"SKIP ({e}): {stmt}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
