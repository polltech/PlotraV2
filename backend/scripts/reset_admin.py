"""
Reset admin user password and account status
"""
import asyncio
import bcrypt
import sys
import os

# Add the current directory to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_db, init_db
from app.models.user import User, UserRole, UserStatus
from sqlalchemy import update, select

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def reset_admin_user():
    # Initialize database tables
    print("Initializing database tables...")
    await init_db()
    
    async for session in get_db():
        # Update admin user
        password_hash = hash_password("Admin123!")
        
        # Check if admin user exists first
        result = await session.execute(
            select(User).where(User.email == "admin@plotra.africa")
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print("Admin user does not exist. Creating...")
            admin_user = User(
                email="admin@plotra.africa",
                password_hash=password_hash,
                first_name="Admin",
                last_name="User",
                phone="+254700000001",
                national_id="99999999",
                role=UserRole.PLOTRA_ADMIN,
                status=UserStatus.ACTIVE,
                is_active=True,
                is_locked=False,
                failed_login_attempts=0
            )
            session.add(admin_user)
        else:
            print(f"Resetting admin user (ID: {user.id})...")
            user.password_hash = password_hash
            user.status = UserStatus.ACTIVE
            user.is_active = True
            user.is_locked = False
            user.failed_login_attempts = 0
            user.role = UserRole.PLOTRA_ADMIN
        
        await session.commit()
        print("Admin user reset successfully")

if __name__ == "__main__":
    asyncio.run(reset_admin_user())
