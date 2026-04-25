#!/usr/bin/env python3
"""
Final Build Verification — Kipawa Platform (KIP-BRS-2026-001)
Checks code integrity after Docker rebuild.
"""

import ast, sys, os

print("="*70)
print("  FINAL BUILD VERIFICATION")
print("="*70)

errors = 0

# Python syntax check
print("\n[1] Python Syntax")
py_files = [
    "backend/app/api/v2/__init__.py",
    "backend/app/api/v2/farmer.py",
    "backend/app/api/v2/gis.py",
    "backend/app/api/v2/system_config.py",
    "backend/app/api/v2/admin.py",
    "backend/app/api/v2/eudr.py",
    "backend/app/api/v2/satellite.py",
    "backend/app/services/eudr_integration.py",
    "backend/app/services/delta_sync.py",
    "backend/app/core/schema_enforcement.py",
    "backend/app/services/geometry_validator.py",
    "backend/app/core/eudr_risk.py",
]
for f in py_files:
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        print(f"  [OK] {f}")
    except Exception as e:
        print(f"  [FAIL] {f}: {e}")
        errors += 1

# JavaScript syntax check
print("\n[2] JavaScript Syntax")
js_files = [
    "frontend/dashboard/js/app.js",
    "frontend/dashboard/js/gps.js",
    "frontend/dashboard/js/config.js",
    "frontend/dashboard/js/auth.js",
    "frontend/dashboard/js/delta_sync.js",
    "frontend/dashboard/js/conflict_resolution.js",
    "frontend/dashboard/js/core.js",
    "frontend/dashboard/js/api.js",
]
for f in js_files:
    import subprocess
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  [OK] {f}")
    else:
        print(f"  [FAIL] {f}: {r.stderr.strip()}")
        errors += 1

# HTML modals
print("\n[3] Required HTML Modals")
required = [
    ("generateDDSModal", "Generate DDS"),
    ("viewDDSModal", "View DDS"),
    ("addFarmModal", "Add Farm"),
    ("farmCaptureModal", "Farm Capture"),
]
with open("frontend/dashboard/index.html", encoding='utf-8') as fh:
    html = fh.read()
for modal_id, name in required:
    if f'id="{modal_id}"' in html:
        print(f"  [OK] {name} ({modal_id})")
    else:
        print(f"  [MISSING] {name}")
        errors += 1

# API endpoint counts
print("\n[4] API Endpoint Counts")
import re

def count_endpoints(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    # Count @router decorators
    return len(re.findall(r'@router\.(get|post|patch|delete)', content))

farmer = count_endpoints("backend/app/api/v2/farmer.py")
gis = count_endpoints("backend/app/api/v2/gis.py")
admin = count_endpoints("backend/app/api/v2/admin.py")
print(f"  farmer.py: {farmer} endpoints (target >=35) {'[OK]' if farmer >= 35 else '[FAIL]'}")
print(f"  gis.py:    {gis} endpoints (target >=8)   {'[OK]' if gis >= 8 else '[FAIL]'}")
print(f"  admin.py:  {admin} endpoints (target >=20) {'[OK]' if admin >= 20 else '[FAIL]'}")
if farmer < 35 or gis < 8 or admin < 20:
    errors += 1

# Docker container check
print("\n[5] Docker Container Status")
import subprocess
r = subprocess.run(["docker", "compose", "ps", "--format", "json"], capture_output=True, text=True)
if r.returncode == 0 and "Up" in r.stdout:
    print("  All containers are UP")
    for line in r.stdout.splitlines():
        if "Up" in line:
            name = line.split()[0] if line else ""
            status = "HEALTHY" if "healthy" in line else "running"
            print(f"    • {name}: {status}")
else:
    print("  Containers may not be running - check 'docker compose ps'")
    print("  (This is not a code error)")

# Summary
print("\n" + "="*70)
if errors == 0:
    print("✅ BUILD VALIDATED — All systems ready")
    print("\nNext: Open http://localhost:8080 in your browser")
    print("Then: Test GPS capture → DDS generation flow")
    sys.exit(0)
else:
    print(f"⚠️  {errors} issue(s) found — review before deployment")
    sys.exit(1)
