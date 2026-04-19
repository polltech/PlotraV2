"""
Delete all cooperatives and their related data from the database.

This script will delete:
- All cooperatives
- All cooperative members
- All farms linked to cooperatives
- All warehouses linked to cooperatives  
- All batches linked to cooperatives
- All carbon projects linked to cooperatives

Usage:
    python delete_all_cooperatives.py [--force]

Use --force to skip confirmation prompt.
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from app.core.database import async_session_factory, init_db
from app.models.user import Cooperative, CooperativeMember, User
from app.models.farm import Farm, LandParcel
from app.models.traceability import Batch, Delivery, Warehouse
from app.models.sustainability import CarbonProject


async def delete_all_cooperatives(force: bool = False):
    """Delete all cooperatives and related data"""
    
    print("=" * 60)
    print("DELETE ALL COOPERATIVES SCRIPT")
    print("=" * 60)
    print("\nThis will delete ALL cooperatives and related data!")
    print("Data to be deleted:")
    print("  - All cooperatives")
    print("  - All cooperative memberships")
    print("  - All farms linked to cooperatives")
    print("  - All land parcels linked to farms")
    print("  - All warehouses linked to cooperatives")
    print("  - All batches linked to cooperatives")
    print("  - All deliveries linked to batches")
    print("  - All carbon projects linked to cooperatives")
    print()
    
    if not force:
        confirm = input("Are you sure you want to continue? Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("Operation cancelled.")
            return
    
    # Initialize database
    print("\nInitializing database...")
    await init_db()
    
    async with async_session_factory() as session:
        try:
            # Count existing data
            coop_result = await session.execute(select(Cooperative))
            cooperatives = coop_result.scalars().all()
            print(f"\nFound {len(cooperatives)} cooperatives to delete")
            
            # Get all cooperative IDs
            coop_ids = [c.id for c in cooperatives]
            
            if not coop_ids:
                print("No cooperatives found. Nothing to delete.")
                return
            
            # Delete carbon projects (depends on cooperative_id)
            print("Deleting carbon projects...")
            await session.execute(
                delete(CarbonProject).where(CarbonProject.cooperative_id.in_(coop_ids))
            )
            
            # Delete deliveries (depends on batch -> cooperative)
            print("Deleting deliveries...")
            batch_result = await session.execute(
                select(Batch.id).where(Batch.cooperative_id.in_(coop_ids))
            )
            batch_ids = list(batch_result.scalars().all())
            if batch_ids:
                await session.execute(
                    delete(Delivery).where(Delivery.batch_id.in_(batch_ids))
                )
            
            # Delete batches (depends on cooperative_id and warehouse)
            print("Deleting batches...")
            await session.execute(
                delete(Batch).where(Batch.cooperative_id.in_(coop_ids))
            )
            
            # Delete warehouses
            print("Deleting warehouses...")
            await session.execute(
                delete(Warehouse).where(Warehouse.cooperative_id.in_(coop_ids))
            )
            
            # Delete land parcels (depends on farms)
            print("Deleting land parcels...")
            farm_result = await session.execute(
                select(Farm.id).where(Farm.cooperative_id.in_(coop_ids))
            )
            farm_ids = list(farm_result.scalars().all())
            if farm_ids:
                await session.execute(
                    delete(LandParcel).where(LandParcel.farm_id.in_(farm_ids))
                )
            
            # Delete farms
            print("Deleting farms...")
            await session.execute(
                delete(Farm).where(Farm.cooperative_id.in_(coop_ids))
            )
            
            # Delete cooperative memberships
            print("Deleting cooperative memberships...")
            await session.execute(
                delete(CooperativeMember).where(CooperativeMember.cooperative_id.in_(coop_ids))
            )
            
            # Delete cooperatives
            print("Deleting cooperatives...")
            await session.execute(
                delete(Cooperative).where(Cooperative.id.in_(coop_ids))
            )
            
            await session.commit()
            
            print("\n" + "=" * 60)
            print("SUCCESS! All cooperatives and related data deleted.")
            print("=" * 60)
            
            # Verify deletion
            coop_result = await session.execute(select(Cooperative))
            remaining = coop_result.scalars().all()
            print(f"\nRemaining cooperatives: {len(remaining)}")
            
        except Exception as e:
            await session.rollback()
            print(f"\nError deleting cooperatives: {e}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete all cooperatives and related data")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
    asyncio.run(delete_all_cooperatives(force=args.force))
