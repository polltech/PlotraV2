import asyncio
import sys
from app.core.database import async_session_factory, engine
from sqlalchemy import text, select
from app.models.user import User

async def test_login():
    output = []
    
    try:
        output.append("Starting test...")
        
        # Check the database URL
        from app.core.config import settings
        output.append(f"Database URL: {settings.database.async_url}")
        
        # Check tables
        async with engine.connect() as conn:
            result = await conn.execute(text('SELECT name FROM sqlite_master WHERE type="table"'))
            tables = result.fetchall()
            output.append(f"Tables: {[t[0] for t in tables]}")
            
            # Check user count
            result = await conn.execute(text('SELECT COUNT(*) FROM user'))
            count = result.scalar()
            output.append(f"User count: {count}")
            
            # Try query
            result = await conn.execute(text('SELECT * FROM user LIMIT 5'))
            rows = result.fetchall()
            output.append(f"Users: {rows}")
            
    except Exception as e:
        output.append(f"Error: {e}")
        import traceback
        output.append(traceback.format_exc())
    
    # Write to file
    with open('test_output.txt', 'w') as f:
        f.write('\n'.join(output))

if __name__ == "__main__":
    asyncio.run(test_login())
