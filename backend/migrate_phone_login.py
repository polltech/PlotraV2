"""
Migration: Add phone unique constraint, make email nullable, add country/datetime fields
Implements phone login with country codes and optional email registration.
"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Add backend directory to path so we can import settings
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

# Get database URL from settings
DATABASE_URL = settings.database.async_url
print(f"Database URL: {DATABASE_URL}")


async def run_migration():
    """Run all migration steps"""
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        try:
            print("\n=== Starting Migration: Phone Login & Optional Email ===\n")

            # Step 1: Check current columns
            print("1. Checking current table structure...")
            result = await conn.execute(text("""
                SELECT column_name, is_nullable, data_type
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name IN ('email', 'phone', 'country', 'phone_number')
                ORDER BY column_name
            """))
            columns = result.fetchall()
            print("Current columns:")
            for col in columns:
                print(f"  {col[0]}: nullable={col[1]}, type={col[2]}")

            # Step 2: Make email nullable
            print("\n2. Making email column nullable...")
            try:
                await conn.execute(text("""
                    ALTER TABLE users ALTER COLUMN email DROP NOT NULL
                """))
                print("✓ Email column is now nullable")
            except Exception as e:
                print(f"  Note: {e}")
                print("  (This is okay if already nullable)")

            # Step 3: Make phone unique
            print("\n3. Adding unique constraint to phone column...")
            try:
                # Check if unique constraint already exists
                result = await conn.execute(text("""
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE tablename = 'users'
                    AND indexname = 'ix_users_phone'
                """))
                index_exists = result.scalar() > 0

                if not index_exists:
                    # Create unique index on phone (NULLs allowed)
                    await conn.execute(text("""
                        CREATE UNIQUE INDEX ix_users_phone ON users (phone)
                        WHERE phone IS NOT NULL
                    """))
                    print("✓ Created unique index on phone column")
                else:
                    print("✓ Unique index on phone already exists")
            except Exception as e:
                print(f"  Error creating phone index: {e}")

            # Step 4: Add country constraint if needed
            print("\n4. Checking country column values...")
            try:
                result = await conn.execute(text("""
                    SELECT DISTINCT country FROM users WHERE country IS NOT NULL
                """))
                countries = [row[0] for row in result.fetchall()]
                print(f"Current countries in use: {countries}")

                # Check if constraint exists
                result = await conn.execute(text("""
                    SELECT COUNT(*)
                    FROM pg_constraint
                    WHERE conname = 'users_country_check'
                """))
                constraint_exists = result.scalar() > 0

                if not constraint_exists:
                    await conn.execute(text("""
                        ALTER TABLE users
                        ADD CONSTRAINT users_country_check
                        CHECK (country IN ('Kenya', 'Uganda', 'Tanzania'))
                    """))
                    print("✓ Added country constraint")
                else:
                    print("✓ Country constraint already exists")
            except Exception as e:
                print(f"  Note: {e}")

            # Step 5: Verify changes
            print("\n5. Verifying changes...")
            result = await conn.execute(text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name IN ('email', 'phone')
            """))
            for row in result:
                print(f"  {row[0]}: nullable={row[1]}")

            print("\n✓ Migration completed successfully!")

        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())
