"""
Script to update existing cooperatives with the new code format PTC/YEAR/001
"""
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.user import Cooperative
from datetime import datetime


async def update_cooperative_codes():
    """Update existing cooperatives with new code format PTC/YEAR/001"""
    async with async_session_factory() as db:
        # Get all cooperatives ordered by creation date
        result = await db.execute(
            select(Cooperative).order_by(Cooperative.created_at)
        )
        cooperatives = result.scalars().all()
        
        print(f"Found {len(cooperatives)} cooperatives to update")
        
        # Group cooperatives by year
        cooperatives_by_year = {}
        for coop in cooperatives:
            year = coop.created_at.year
            if year not in cooperatives_by_year:
                cooperatives_by_year[year] = []
            cooperatives_by_year[year].append(coop)
        
        # Update each cooperative with a code
        for year, coops in cooperatives_by_year.items():
            print(f"\nProcessing {len(coops)} cooperatives for year {year}")
            
            for idx, coop in enumerate(coops, start=1):
                # Skip if cooperative already has a code
                if coop.code:
                    print(f"  Skipping {coop.name} - already has code {coop.code}")
                    continue
                
                # Generate code in format PTC/YEAR/001
                code = f"PTC/{year}/{idx:03d}"
                
                # Check if code already exists
                existing = await db.execute(
                    select(Cooperative).where(Cooperative.code == code)
                )
                if existing.scalar_one_or_none():
                    print(f"  Skipping {coop.name} - code {code} already exists")
                    continue
                
                # Update cooperative with new code
                coop.code = code
                print(f"  Updated {coop.name} with code {code}")
        
        # Commit all changes
        await db.commit()
        print("\nAll cooperatives updated successfully!")


if __name__ == "__main__":
    asyncio.run(update_cooperative_codes())
