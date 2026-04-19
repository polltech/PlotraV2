"""
Fix KIPACA_ADMIN typo to KIPAWA_ADMIN in database
Run this script to update any users with the incorrect role
"""
import asyncio
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.core.database import get_db, init_db
from sqlalchemy import text

async def fix_kipaca_role():
    """Update any users with KIPACA_ADMIN role to KIPAWA_ADMIN"""
    print("Initializing database...")
    await init_db()
    
    async for session in get_db():
        # Check for users with KIPACA_ADMIN role
        result = await session.execute(
            text("SELECT id, email, role FROM users WHERE role = 'KIPACA_ADMIN'")
        )
        kipaca_users = result.fetchall()
        
        if kipaca_users:
            print(f"Found {len(kipaca_users)} users with KIPACA_ADMIN role:")
            for user in kipaca_users:
                print(f"  - ID: {user[0]}, Email: {user[1]}, Role: {user[2]}")
                # Update to correct role
                await session.execute(
                    text("UPDATE users SET role = 'plotra_admin' WHERE id = :user_id"),
                    {"user_id": user[0]}
                )
            await session.commit()
            print("Fixed KIPACA_ADMIN -> plotra_admin")
        else:
            print("No users found with KIPACA_ADMIN role")
        
        # Also check for lowercase kipaca_admin
        result2 = await session.execute(
            text("SELECT id, email, role FROM users WHERE role = 'kipaca_admin'")
        )
        kipaca_users2 = result2.fetchall()
        
        if kipaca_users2:
            print(f"Found {len(kipaca_users2)} users with kipaca_admin role:")
            for user in kipaca_users2:
                print(f"  - ID: {user[0]}, Email: {user[1]}, Role: {user[2]}")
                await session.execute(
                    text("UPDATE users SET role = 'plotra_admin' WHERE id = :user_id"),
                    {"user_id": user[0]}
                )
            await session.commit()
            print("Fixed kipaca_admin -> plotra_admin")
        
        # Display all admin users
        result3 = await session.execute(
            text("SELECT id, email, role FROM users WHERE role IN ('plotra_admin', 'platform_admin', 'super_admin', 'admin')")
        )
        admin_users = result3.fetchall()
        
        print("\n=== Current Admin Users ===")
        for user in admin_users:
            print(f"  - Email: {user[1]}, Role: {user[2]}")
        
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(fix_kipaca_role())