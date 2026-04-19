import sys
# Clear cached modules
for mod in list(sys.modules.keys()):
    if 'app' in mod:
        del sys.modules[mod]

sys.path.insert(0, 'backend')

import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.user import User
from app.models.farm import Farm

async def test():
    output = []
    output.append("Testing after fix...")
    
    try:
        # Try to import models
        output.append("Models imported successfully")
        
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.email == 'admin@plotra.africa'))
            user = result.scalar_one_or_none()
            if user:
                output.append(f"User found: {user.email}")
                output.append(f"Owned farms relationship exists: {hasattr(user, 'owned_farms')}")
                
                # Test authentication
                from app.core.auth import authenticate_user
                auth_result = await authenticate_user(session, 'admin@plotra.africa', 'admin123')
                output.append(f"Authentication result: {auth_result}")
            else:
                output.append("User not found!")
    except Exception as e:
        output.append(f"Error: {e}")
        import traceback
        output.append(traceback.format_exc())
    
    with open('debug_output3.txt', 'w') as f:
        f.write('\n'.join(output))
    print("Done. Check debug_output3.txt")

if __name__ == "__main__":
    asyncio.run(test())
