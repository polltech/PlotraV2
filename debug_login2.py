import sys
sys.path.insert(0, 'backend')

import asyncio
from sqlalchemy import text, select
from app.core.database import async_session_factory
from app.core.auth import authenticate_user, verify_password
from app.models.user import User

async def test():
    output = []
    output.append("Testing authentication...")
    
    try:
        async with async_session_factory() as session:
            # Get user
            result = await session.execute(select(User).where(User.email == 'admin@plotra.africa'))
            user = result.scalar_one_or_none()
            
            if user:
                output.append(f"User found: {user.email}, {user.first_name} {user.last_name}")
                output.append(f"Password hash: {user.password_hash[:50]}...")
                output.append(f"Is active: {user.is_active}")
                output.append(f"Is locked: {user.is_locked}")
                
                # Try password verification
                test_password = "admin123"
                is_valid = verify_password(test_password, user.password_hash)
                output.append(f"Password 'admin123' valid: {is_valid}")
                
                # Try authenticate_user
                output.append("Testing authenticate_user...")
                auth_user = await authenticate_user(session, 'admin@plotra.africa', 'admin123')
                output.append(f"authenticate_user result: {auth_user}")
            else:
                output.append("User not found!")
                
    except Exception as e:
        output.append(f"Error: {e}")
        import traceback
        output.append(traceback.format_exc())
    
    # Write output
    with open('debug_output2.txt', 'w') as f:
        f.write('\n'.join(output))
    print("Done. Check debug_output2.txt")

if __name__ == "__main__":
    asyncio.run(test())
