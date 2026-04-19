"""
Add admin user to the database
"""
import asyncio
import bcrypt
from app.core.database import get_db
from app.models.user import User, UserRole, UserStatus

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def add_admin_user():
    async for session in get_db():
        # Check if admin user already exists
        existing_admin = await session.execute(
            User.__table__.select().where(User.email == "admin@plotra.africa")
        )
        if existing_admin.scalar_one_or_none():
            print("Admin user already exists")
            return
        
        # Create admin user
        admin_user = User(
            email="admin@plotra.africa",
            password_hash=hash_password("password123"),
            first_name="Admin",
            last_name="User",
            phone="+254700000001",
            national_id="99999999",
            role=UserRole.PLOTRA_ADMIN,
            status=UserStatus.ACTIVE,
            is_active=True
        )
        
        session.add(admin_user)
        await session.commit()
        print("Admin user created successfully")

if __name__ == "__main__":
    asyncio.run(add_admin_user())
