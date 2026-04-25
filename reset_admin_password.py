#!/usr/bin/env python3
"""
Reset Admin Password — Kipawa Platform
Updates admin user password directly in PostgreSQL.
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.database import async_session_factory, init_db
from app.core.auth import get_password_hash
from app.models.user import User

async def reset_admin():
    await init_db()
    async with async_session_factory() as session:
        # Find admin
        result = await session.execute(select(User).where(User.email == "admin@plotra.com"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            print("Admin user not found!")
            return
        
        # Set new password
        new_hash = get_password_hash("AdminPass123!")
        admin.password_hash = new_hash
        admin.failed_login_attempts = 0
        admin.is_locked = False
        admin.is_active = True
        admin.verification_status = "verified"
        
        await session.commit()
        print("✅ Admin password reset successfully")
        print(f"   Email: {admin.email}")
        print(f"   Phone: {admin.phone}")
        print(f"   Password: AdminPass123!")
        print(f"   Hash: {new_hash[:30]}...")

if __name__ == "__main__":
    import sys
    try:
        asyncio.run(reset_admin())
    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
