from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db, engine
from app.models.user import User

router = APIRouter(tags=["Debug"])

@router.get("/db-info")
async def get_db_info(db: AsyncSession = Depends(get_db)):
    """
    Get information about the current database connection.
    """
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    return {
        "database_url": str(engine.url),
        "total_users": len(users),
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "role": str(user.role),
                "is_active": user.is_active,
                "is_locked": user.is_locked
            } for user in users
        ]
    }
