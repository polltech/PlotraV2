"""
Fix user roles enum mismatch - convert database enum from uppercase to lowercase
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback if running locally
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/plotra"

print(f"Database URL: {DATABASE_URL}")

async def fix_user_roles():
    """Fix the user roles enum in the database"""
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        try:
            print("\n1. Checking current enum type...")
            result = await conn.execute(text("""
                SELECT enum_range(NULL::userrole)
            """))
            enum_values = result.scalar()
            print(f"Current enum values: {enum_values}")
            
            # First, let's rename the old enum
            print("\n2. Renaming old enum type...")
            await conn.execute(text("ALTER TYPE userrole RENAME TO userrole_old;"))
            print("✓ Renamed to userrole_old")
            
            # Create new enum with lowercase values
            print("\n3. Creating new enum type with lowercase values...")
            await conn.execute(text("""
                CREATE TYPE userrole AS ENUM (
                    'farmer',
                    'cooperative_officer',
                    'plotra_admin',
                    'eudr_reviewer'
                )
            """))
            print("✓ Created new userrole enum with lowercase values")
            
            # Update the column to use the new enum
            print("\n4. Converting column type...")
            await conn.execute(text("""
                ALTER TABLE users 
                ALTER COLUMN role TYPE userrole 
                USING role::text::userrole
            """))
            print("✓ Converted column type")
            
            # Drop the old enum
            print("\n5. Dropping old enum type...")
            await conn.execute(text("DROP TYPE userrole_old;"))
            print("✓ Dropped old enum")
            
            # Verify the fix
            print("\n6. Verifying fix...")
            result = await conn.execute(text("SELECT COUNT(*) FROM users WHERE role IS NOT NULL"))
            count = result.scalar()
            print(f"✓ Successfully processed {count} users")
            
            # Sample some users
            print("\n7. Sample users:")
            result = await conn.execute(text("SELECT id, email, role FROM users LIMIT 5"))
            for row in result:
                print(f"  - {row[1]}: {row[2]}")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            raise
    
    await engine.dispose()
    print("\n✓ All fixes applied successfully!")

if __name__ == "__main__":
    asyncio.run(fix_user_roles())
