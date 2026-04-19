import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

import inspect
from app.api.v2.auth import router as auth_router
from app.api.v2.farmer import router as farmer_router
from app.api.v2.coop import router as coop_router
from app.api.v2.admin import router as admin_router
from app.api.v2 import api_router as main_router

def print_router_info(name, router):
    print(f"\n=== {name} ===")
    print(f"Router type: {type(router)}")
    print(f"Prefix: {getattr(router, 'prefix', 'N/A')}")
    print(f"Tags: {getattr(router, 'tags', 'N/A')}")
    print(f"Routes count: {len(router.routes)}")
    for i, route in enumerate(router.routes):
        if hasattr(route, "path"):
            print(f"  Route {i}: {route.path}")
        elif hasattr(route, "name"):
            print(f"  Route {i}: {route.name}")

print_router_info("Auth Router", auth_router)
print_router_info("Farmer Router", farmer_router)
print_router_info("Coop Router", coop_router)
print_router_info("Admin Router", admin_router)
print_router_info("Main API Router", main_router)
