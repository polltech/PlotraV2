"""
Plotra Platform - Database Migration Script
Renames 'region' column to 'county' in users and cooperatives tables

This script handles both SQLite and PostgreSQL databases.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import async_session_factory, engine


async def check_and_rename_column(table_name: str, old_col: str, new_col: str):
    """Check if column exists and rename it"""
    async with async_session_factory() as session:
        try:
            # Get current columns using PRAGMA for SQLite or information_schema for PostgreSQL
            db_url = str(engine.url)
            
            if 'sqlite' in db_url:
                # SQLite: Use PRAGMA to get columns
                result = await session.execute(text(f"PRAGMA table_info({table_name})"))
                columns = [row[1] for row in result.fetchall()]
            else:
                # PostgreSQL: Use information_schema
                result = await session.execute(text(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                """))
                columns = [row[0] for row in result.fetchall()]
            
            if old_col in columns and new_col not in columns:
                if 'sqlite' in db_url:
                    # SQLite: Use ALTER TABLE RENAME COLUMN
                    await session.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN {old_col} TO {new_col}"))
                    print(f"[OK] Renamed '{old_col}' to '{new_col}' in '{table_name}'")
                else:
                    # PostgreSQL: Add new column, copy data, drop old column
                    # First, get the column type
                    result = await session.execute(text(f"""
                        SELECT data_type FROM information_schema.columns 
                        WHERE table_name = '{table_name}' AND column_name = '{old_col}'
                    """))
                    row = result.fetchone()
                    if row:
                        col_type = row[0]
                        # Add new column
                        await session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {new_col} {col_type}"))
                        # Copy data
                        await session.execute(text(f"UPDATE {table_name} SET {new_col} = {old_col}"))
                        # Drop old column
                        await session.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {old_col}"))
                        print(f"[OK] Renamed '{old_col}' to '{new_col}' in '{table_name}'")
                
                await session.commit()
                return True
            elif new_col in columns:
                print(f"[OK] Column '{new_col}' already exists in '{table_name}'")
                return True
            else:
                print(f"[WARN] Column '{old_col}' not found in '{table_name}'")
                return False
                
        except Exception as e:
            print(f"[ERROR] Error processing {table_name}: {e}")
            await session.rollback()
            return False


async def main():
    """Main migration function"""
    print("=" * 60)
    print("Plotra Platform - Region to County Migration")
    print("=" * 60)
    
    # Check database type
    db_url = str(engine.url)
    db_type = "SQLite" if "sqlite" in db_url else "PostgreSQL"
    print(f"\nDatabase type: {db_type}")
    print(f"Database URL: {db_url}")
    print()
    
    # Tables to update
    tables = [
        ("users", "region", "county"),
        ("cooperatives", "region", "county"),
    ]
    
    success_count = 0
    for table_name, old_col, new_col in tables:
        print(f"Processing table: {table_name}")
        if await check_and_rename_column(table_name, old_col, new_col):
            success_count += 1
        print()
    
    print("=" * 60)
    print(f"Migration complete: {success_count}/{len(tables)} tables updated")
    print("=" * 60)
    
    return success_count == len(tables)


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)