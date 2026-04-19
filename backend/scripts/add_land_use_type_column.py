"""
Add missing land_use_type column to land_parcels table
Run this script to add the missing column to the PostgreSQL database
"""

import os
import sys
import asyncio

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


async def add_land_use_type_column():
    """Add land_use_type column to land_parcels table"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/plotra_db")
    
    print(f"Connecting to database: {db_url}")
    engine = create_async_engine(db_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # First check if column exists
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'land_parcels' AND column_name = 'land_use_type'
            """))
            column_exists = result.fetchone()
            
            if column_exists:
                print("Column 'land_use_type' already exists in land_parcels table")
            else:
                # Add the column
                await session.execute(text("""
                    ALTER TABLE land_parcels 
                    ADD COLUMN land_use_type VARCHAR(50) DEFAULT 'agroforestry'
                """))
                print("Added 'land_use_type' column to land_parcels table")
            
            # Also check if the column exists in farms table (line 214)
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'farms' AND column_name = 'land_use_type'
            """))
            column_exists = result.fetchone()
            
            if column_exists:
                print("Column 'land_use_type' already exists in farms table")
            else:
                # Add the column to farms table
                await session.execute(text("""
                    ALTER TABLE farms 
                    ADD COLUMN land_use_type VARCHAR(50) DEFAULT 'agroforestry'
                """))
                print("Added 'land_use_type' column to farms table")
            
            await session.commit()
            print("Database updated successfully!")
            
        except Exception as e:
            await session.rollback()
            print(f"Error updating database: {e}")
        finally:
            await engine.dispose()


if __name__ == "__main__":
    print("=" * 50)
    print("Adding land_use_type column to database")
    print("=" * 50)
    
    asyncio.run(add_land_use_type_column())
    
    print("=" * 50)
    print("Done!")
    print("=" * 50)
