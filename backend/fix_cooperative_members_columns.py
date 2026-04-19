"""
Script to add missing columns to the cooperative_members table in PostgreSQL.
Run this script to fix the database schema.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.core.database import async_session_factory


async def fix_cooperative_members_columns():
    """Add missing columns to cooperative_members table"""
    
    # Columns to add with their definitions
    columns_to_add = [
        ("membership_type", "VARCHAR(50) DEFAULT 'regular'"),
        ("join_date", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("exit_date", "TIMESTAMP"),
        ("is_primary", "BOOLEAN DEFAULT FALSE"),
        ("cooperative_role", "VARCHAR(100)"),
    ]
    
    async with async_session_factory() as session:
        try:
            # Check if table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name = 'cooperative_members'
                )
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("ERROR: cooperative_members table does not exist!")
                return
            
            print("cooperative_members table exists. Checking columns...")
            
            # Get existing columns
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cooperative_members'
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            print(f"Existing columns: {existing_columns}")
            
            # Add missing columns
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    try:
                        await session.execute(text(f"""
                            ALTER TABLE cooperative_members 
                            ADD COLUMN {column_name} {column_type}
                        """))
                        print(f"Added column: {column_name}")
                    except Exception as e:
                        print(f"Error adding {column_name}: {e}")
                else:
                    print(f"Column {column_name} already exists")
            
            await session.commit()
            print("\nDone! All columns should now be present.")
            
        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(fix_cooperative_members_columns())
