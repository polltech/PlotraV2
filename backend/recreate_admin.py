"""
Script to delete and recreate admin user with correct role.
Run this to fix the admin user after code changes.
"""
import asyncio
import sys
import bcrypt
import uuid

sys.path.insert(0, '.')

from sqlalchemy import text
from app.core.database import async_session_factory, init_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


async def recreate_admin():
    """Delete and recreate admin user with PLOTRA_ADMIN role"""
    
    # Initialize database tables first
    print("Initializing database...")
    await init_db()
    
    async with async_session_factory() as session:
        try:
            # Delete existing admin user if exists
            await session.execute(text("""
                DELETE FROM users WHERE email = 'admin@plotra.africa'
            """))
            print("Deleted existing admin user (if any)")
            
            # Create new admin user
            password_hash = hash_password("Admin123!")
            user_id = str(uuid.uuid4())
            
            await session.execute(text("""
                INSERT INTO users (
                    id, email, password_hash, first_name, last_name, phone,
                    national_id, role, status, is_active, is_locked,
                    failed_login_attempts, verification_status, country,
                    created_at, updated_at
                ) VALUES (
                    :id, :email, :password_hash, :first_name,
                    :last_name, :phone, :national_id, :role, :status,
                    :is_active, :is_locked, :failed_login_attempts,
                    :verification_status, :country, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """), {
                "id": user_id,
                "email": "admin@plotra.africa",
                "password_hash": password_hash,
                "first_name": "Admin",
                "last_name": "User",
                "phone": "+254700000001",
                "national_id": "99999999",
                "role": "plotra_admin",
                "status": "active",
                "is_active": True,
                "is_locked": False,
                "failed_login_attempts": 0,
                "verification_status": "verified",
                "country": "Kenya"
            })
            
            await session.commit()
            print("Admin user created successfully!")
            print("Email: admin@plotra.africa")
            print("Password: Admin123!")
            print("Role: plotra_admin")
            
        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(recreate_admin())
