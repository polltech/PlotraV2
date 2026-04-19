"""
Quick script to update user role directly in the database.
Run this to fix the admin user role after code changes.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.core.database import async_session_factory


async def update_user_role():
    """Update the admin user role to PLOTRA_ADMIN"""
    
    async with async_session_factory() as session:
        try:
            # First check what roles exist in the users table
            result = await session.execute(text("""
                SELECT id, email, role FROM users WHERE email = 'admin@plotra.africa'
            """))
            user = result.fetchone()
            
            if user:
                print(f"Current user: {user}")
                print(f"Current role: {user[2]}")
            else:
                print("No user found with email admin@plotra.africa")
                return

            # Update the role to plotra_admin
            await session.execute(text("""
                UPDATE users SET role = 'plotra_admin' WHERE email = 'admin@plotra.africa'
            """))
            
            await session.commit()
            print("User role updated successfully!")
            
            # Verify the update
            result = await session.execute(text("""
                SELECT id, email, role FROM users WHERE email = 'admin@plotra.africa'
            """))
            user = result.fetchone()
            print(f"Updated user: {user}")
            
        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(update_user_role())
