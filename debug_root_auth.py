import asyncio
import sys
import os
import bcrypt

# Add root app to path
sys.path.append(os.getcwd())

from app.core.auth import authenticate_user, verify_password
from app.core.database import async_session_factory
from app.models.user import User, UserRole
from sqlalchemy import select

async def debug_auth():
    email = "admin@plotra.africa"
    password = "password123"
    
    print(f"Testing authentication for {email} on root database...")
    
    async with async_session_factory() as session:
        # 1. Check user existence and raw data
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            print("FAILED: User not found in database via SQLAlchemy")
            return

        print(f"User found: ID={user.id}, Role={user.role}, Status={user.status}")
        print(f"Password Hash in DB: {user.password_hash[:20]}...")
        
        # 2. Test manual bcrypt verification
        # Using passlib since that's what app uses
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        is_valid = pwd_context.verify(password, user.password_hash)
        print(f"Manual passlib verify: {is_valid}")
        
        # 3. Test backend verify_password function
        is_valid_func = verify_password(password, user.password_hash)
        print(f"Backend verify_password call: {is_valid_func}")
        
        # 4. Test full authenticate_user logic
        auth_user = await authenticate_user(session, email, password)
        if auth_user:
            print("SUCCESS: authenticate_user returned the user object")
        else:
            print("FAILED: authenticate_user returned None")
            print(f"User Active: {user.is_active}, Locked: {user.is_locked}, Failed Attempts: {user.failed_login_attempts}")

if __name__ == "__main__":
    asyncio.run(debug_auth())
