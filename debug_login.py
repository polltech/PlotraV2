import sys
sys.path.insert(0, 'backend')

import asyncio
from sqlalchemy import text
from app.core.database import async_session_factory

async def test():
    output = []
    output.append("Starting debug...")
    
    try:
        # Check if users table exists
        async with async_session_factory() as session:
            result = await session.execute(text('SELECT name FROM sqlite_master WHERE type="table"'))
            tables = result.fetchall()
            output.append(f"Tables: {[t[0] for t in tables]}")
            
            # Check if there are any users
            try:
                result = await session.execute(text('SELECT COUNT(*) FROM users'))
                count = result.scalar()
                output.append(f"User count: {count}")
                
                if count > 0:
                    result = await session.execute(text('SELECT id, email, first_name, role FROM users LIMIT 3'))
                    users = result.fetchall()
                    output.append(f"Users: {users}")
            except Exception as e:
                output.append(f"Error querying users: {e}")
                import traceback
                output.append(traceback.format_exc())
    except Exception as e:
        output.append(f"Error: {e}")
        import traceback
        output.append(traceback.format_exc())
    
    # Write output
    with open('debug_output.txt', 'w') as f:
        f.write('\n'.join(output))
    print("Debug complete. Check debug_output.txt")

if __name__ == "__main__":
    asyncio.run(test())
