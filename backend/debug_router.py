"""Debug script to print the router structure"""
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.main import app

print("=== FastAPI App Routes ===")
for route in app.routes:
    if hasattr(route, "path"):
        print(route.path)

print("\n=== API Router Structure ===")
# Get the main API router (which has prefix /api/v2)
api_router = app.routes[0].dependant.body_params[0].type_ if hasattr(app.routes[0], 'dependant') else None
print(f"Main API Router: {api_router}")

# If we can't access it that way, let's check the app's router directly
print("\n=== App Router Stack ===")
if hasattr(app, 'router'):
    print(f"App Router: {app.router}")
    if hasattr(app.router, 'routes'):
        for i, route in enumerate(app.router.routes):
            print(f"Route {i}: {type(route)}, {getattr(route, 'path', 'No path')}")
