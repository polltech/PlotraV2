"""
Update all Plotra references to Plotra
Run this script to update existing database records and enum definitions after renaming
"""

import os
import sys
import asyncio

# Get the project root (parent of scripts directory)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


async def update_database():
    """Update user roles in database"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/plotra_db")
    
    print(f"Connecting to database: {db_url}")
    engine = create_async_engine(db_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Update users with 'plotra_admin' role (from old 'plotra_admin' value)
            result = await session.execute(text("""
                UPDATE users 
                SET role = 'plotra_admin' 
                WHERE role = 'plotra_admin'
            """))
            print(f"Updated {result.rowcount} users from 'plotra_admin' to 'plotra_admin'")
            
            await session.commit()
            print("Database updated successfully!")
            
        except Exception as e:
            await session.rollback()
            print(f"Error updating database: {e}")
        finally:
            await engine.dispose()


def update_enum_definitions():
    """Update the UserRole enum definitions in models"""
    
    # Update app/models/user.py
    user_model_path = os.path.join(PROJECT_ROOT, "app", "models", "user.py")
    if os.path.exists(user_model_path):
        with open(user_model_path, "r") as f:
            content = f.read()
        
        new_content = content.replace("PLOTRA_ADMIN = \"plotra_admin\"", "PLOTRA_ADMIN = \"plotra_admin\"")
        
        if new_content != content:
            with open(user_model_path, "w") as f:
                f.write(new_content)
            print(f"Updated {user_model_path}")
    
    # Update app/api/schemas.py
    schemas_path = os.path.join(PROJECT_ROOT, "app", "api", "schemas.py")
    if os.path.exists(schemas_path):
        with open(schemas_path, "r") as f:
            content = f.read()
        
        new_content = content.replace("PLOTRA_ADMIN = \"plotra_admin\"", "PLOTRA_ADMIN = \"plotra_admin\"")
        
        if new_content != content:
            with open(schemas_path, "w") as f:
                f.write(new_content)
            print(f"Updated {schemas_path}")
    
    # Update app/core/auth.py references
    auth_path = os.path.join(PROJECT_ROOT, "app", "core", "auth.py")
    if os.path.exists(auth_path):
        with open(auth_path, "r") as f:
            content = f.read()
        
        new_content = content.replace("UserRole.PLOTRA_ADMIN", "UserRole.PLOTRA_ADMIN")
        new_content = new_content.replace("require_plotra_admin = require_role([UserRole.PLOTRA_ADMIN])", 
                                     "require_plotra_admin = require_role([UserRole.PLOTRA_ADMIN])")
        
        if new_content != content:
            with open(auth_path, "w") as f:
                f.write(new_content)
            print(f"Updated {auth_path}")
    
    # Update backend/app/models/user.py
    backend_user_path = os.path.join(PROJECT_ROOT, "backend", "app", "models", "user.py")
    if os.path.exists(backend_user_path):
        with open(backend_user_path, "r") as f:
            content = f.read()
        
        new_content = content.replace("PLOTRA_ADMIN = \"plotra_admin\"", "PLOTRA_ADMIN = \"plotra_admin\"")
        
        if new_content != content:
            with open(backend_user_path, "w") as f:
                f.write(new_content)
            print(f"Updated {backend_user_path}")
    
    # Update backend/app/api/schemas.py
    backend_schemas_path = os.path.join(PROJECT_ROOT, "backend", "app", "api", "schemas.py")
    if os.path.exists(backend_schemas_path):
        with open(backend_schemas_path, "r") as f:
            content = f.read()
        
        new_content = content.replace("PLOTRA_ADMIN = \"plotra_admin\"", "PLOTRA_ADMIN = \"plotra_admin\"")
        
        if new_content != content:
            with open(backend_schemas_path, "w") as f:
                f.write(new_content)
            print(f"Updated {backend_schemas_path}")
    
    # Update backend/app/core/auth.py references
    backend_auth_path = os.path.join(PROJECT_ROOT, "backend", "app", "core", "auth.py")
    if os.path.exists(backend_auth_path):
        with open(backend_auth_path, "r") as f:
            content = f.read()
        
        new_content = content.replace("UserRole.PLOTRA_ADMIN", "UserRole.PLOTRA_ADMIN")
        new_content = new_content.replace("require_plotra_admin = require_role([UserRole.PLOTRA_ADMIN])", 
                                     "require_plotra_admin = require_role([UserRole.PLOTRA_ADMIN])")
        
        if new_content != content:
            with open(backend_auth_path, "w") as f:
                f.write(new_content)
            print(f"Updated {backend_auth_path}")


if __name__ == "__main__":
    print("=" * 50)
    print("Updating Plotra -> Plotra")
    print("=" * 50)
    
    print("\n[1/2] Updating enum definitions in source files...")
    update_enum_definitions()
    
    print("\n[2/2] Updating database records...")
    asyncio.run(update_database())
    
    print("\n" + "=" * 50)
    print("Done! All Plotra references updated to Plotra.")
    print("=" * 50)