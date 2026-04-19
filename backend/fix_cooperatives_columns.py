"""
Script to add missing columns to the cooperatives table in PostgreSQL.
Run this script to fix the database schema.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.core.database import async_session_factory


async def fix_cooperatives_columns():
    """Add missing columns to cooperatives table"""
    
    # Columns to add with their definitions
    columns_to_add = [
        ("subcounty", "VARCHAR(100)"),
        ("ward", "VARCHAR(100)"),
        ("description", "TEXT"),
        ("mission", "TEXT"),
        ("vision", "TEXT"),
        ("objectives", "JSON"),
        ("contact_person", "VARCHAR(255)"),
        ("contact_person_phone", "VARCHAR(20)"),
        ("contact_person_email", "VARCHAR(255)"),
        ("legal_status", "VARCHAR(100)"),
        ("governing_document", "VARCHAR(500)"),
        ("latitude", "VARCHAR(50)"),
        ("longitude", "VARCHAR(50)"),
        ("cooperative_type", "VARCHAR(100)"),
        ("establishment_date", "TIMESTAMP"),
        ("primary_officer_id", "VARCHAR(36)"),
    ]
    
    async with async_session_factory() as session:
        try:
            # Check if table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name = 'cooperatives'
                )
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("ERROR: cooperatives table does not exist!")
                return
            
            print("Cooperatives table exists. Checking columns...")
            
            # Get existing columns
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cooperatives'
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            print(f"Existing columns: {existing_columns}")
            
            # Add missing columns
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    try:
                        await session.execute(text(f"""
                            ALTER TABLE cooperatives 
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
    asyncio.run(fix_cooperatives_columns())
