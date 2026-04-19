import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.core.database import async_session_factory
from app.models.user import User
from sqlalchemy import select

async def check_users():
    async with async_session_factory() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        print(f"Total users found: {len(users)}")
        for user in users:
            print(f"ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Role: {user.role}")
            print(f"Is Active: {user.is_active}")
            print(f"Is Locked: {user.is_locked}")
            print(f"Status: {user.status}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(check_users())
