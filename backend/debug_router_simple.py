"""Simple debug script to print router prefixes"""
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.api.v2 import api_router as v2_router
from app.api.v2.auth import router as auth_router
from app.api.v2.farmer import router as farmer_router
from app.api.v2.coop import router as coop_router
from app.api.v2.admin import router as admin_router

print("=== API V2 Router Structure ===")
print(f"Main V2 Router: {v2_router}")
print(f"Main V2 Router Prefix: {getattr(v2_router, 'prefix', 'N/A')}")
print()
print("=== Auth Router ===")
print(f"Auth Router: {auth_router}")
print(f"Auth Router Prefix: {getattr(auth_router, 'prefix', 'N/A')}")
print(f"Auth Router Routes: {len(auth_router.routes)} routes")
print(f"Auth Router Routes List: {[getattr(route, 'path', 'No path') for route in auth_router.routes]}")
print()
print("=== Farmer Router ===")
print(f"Farmer Router: {farmer_router}")
print(f"Farmer Router Prefix: {getattr(farmer_router, 'prefix', 'N/A')}")
print(f"Farmer Router Routes: {len(farmer_router.routes)} routes")
print()
print("=== Coop Router ===")
print(f"Coop Router: {coop_router}")
print(f"Coop Router Prefix: {getattr(coop_router, 'prefix', 'N/A')}")
print(f"Coop Router Routes: {len(coop_router.routes)} routes")
print()
print("=== Admin Router ===")
print(f"Admin Router: {admin_router}")
print(f"Admin Router Prefix: {getattr(admin_router, 'prefix', 'N/A')}")
print(f"Admin Router Routes: {len(admin_router.routes)} routes")
print()
print("=== Main V2 Router Routes ===")
print(f"Main V2 Router Routes: {len(v2_router.routes)} routes")
print(f"Main V2 Router Route Paths:")
for i, route in enumerate(v2_router.routes):
    print(f"  Route {i}: {getattr(route, 'path', 'No path')}")
