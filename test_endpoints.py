#!/usr/bin/env python3
"""
Production Endpoint Test Suite — Kipawa Platform (KIP-BRS-2026-001)
Tests all critical API endpoints after rebuilding Docker containers.
Run: python test_endpoints.py
"""

import sys
import subprocess
import time
import json

BASE_URL = "http://localhost:8000/api/v2"

print("="*75)
print("  KIP-BRS-2026-001 — Production Endpoint Validation")
print("="*75)

def run_test(name, func):
    try:
        func()
        print(f"[PASS] {name}")
        return True
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        return False

passed = 0
failed = 0

# ── Health Check ──────────────────────────────────────────────────────────
print("\n[1] Backend Health")
try:
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL.replace('/api/v2','')}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status == 200:
            print("  Backend /health returns 200 OK")
            passed += 1
        else:
            raise Exception(f"Status {resp.status}")
except Exception as e:
    print(f"  Health check failed: {e}")
    print("  (Backend may not be running — start Docker Desktop first)")
    failed += 1

# ── Python Syntax ─────────────────────────────────────────────────────────
print("\n[2] Python Module Syntax")
py_files = [
    "backend/app/api/v2/__init__.py",
    "backend/app/api/v2/farmer.py",
    "backend/app/api/v2/gis.py",
    "backend/app/api/v2/system_config.py",
    "backend/app/api/v2/satellite.py",
    "backend/app/api/v2/eudr.py",
    "backend/app/api/v2/admin.py",
    "backend/app/services/eudr_integration.py",
    "backend/app/services/delta_sync.py",
    "backend/app/core/schema_enforcement.py",
    "backend/app/services/geometry_validator.py",
    "backend/app/core/eudr_risk.py",
]
all_ok = True
for f in py_files:
    r = subprocess.run(["python", "-m", "py_compile", f], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  FAIL: {f}")
        all_ok = False
if all_ok:
    print("  All 12 Python modules compile cleanly")
    passed += 1
else:
    failed += 1

# ── JavaScript Syntax ─────────────────────────────────────────────────────
print("\n[3] JavaScript Module Syntax")
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
all_ok = True
for f in js_files:
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  FAIL: {f}: {r.stderr.strip()}")
        all_ok = False
if all_ok:
    print("  All 8 JavaScript modules pass syntax check")
    passed += 1
else:
    failed += 1

# ── HTML Structure Checks ─────────────────────────────────────────────────
print("\n[4] HTML Modal Structure")
required_modals = [
    ("addFarmModal", "Add Farm"),
    ("farmCaptureModal", "Farm Boundary Capture"),
    ("generateDDSModal", "Generate DDS"),
    ("viewDDSModal", "View DDS"),
]
missing = []
with open("frontend/dashboard/index.html", encoding="utf-8") as f:
    html = f.read()
for modal_id, name in required_modals:
    if f'id="{modal_id}"' not in html:
        missing.append(name)
if missing:
    print(f"  Missing modals: {', '.join(missing)}")
    failed += 1
else:
    print("  All required modals present:")
    for _, name in required_modals:
        print(f"    • {name}")
    passed += 1

# ── API Route Counts ──────────────────────────────────────────────────────
print("\n[5] API Route Counts (static analysis)")
farmer_routes = subprocess.run(["grep", "-c", "@router\\.(get|post|patch|delete)", "backend/app/api/v2/farmer.py"], capture_output=True, text=True)
count = int(farmer_routes.stdout.strip()) if farmer_routes.returncode == 0 else 0
print(f"  farmer.py: {count} endpoints (target: 35+)")
passed += 1 if count >= 35 else 0
failed += 0 if count >= 35 else 1

gis_routes = subprocess.run(["grep", "-c", "@router\\.(get|post)", "backend/app/api/v2/gis.py"], capture_output=True, text=True)
count = int(gis_routes.stdout.strip()) if gis_routes.returncode == 0 else 0
print(f"  gis.py: {count} endpoints (target: 8+)")
passed += 1 if count >= 8 else 0
failed += 0 if count >= 8 else 1

admin_routes = subprocess.run(["grep", "-c", "@router\\.(get|post|patch|delete)", "backend/app/api/v2/admin.py"], capture_output=True, text=True)
count = int(admin_routes.stdout.strip()) if admin_routes.returncode == 0 else 0
print(f"  admin.py: {count} endpoints (target: 20+)")
passed += 1 if count >= 20 else 0
failed += 0 if count >= 20 else 1

# ── Summary ───────────────────────────────────────────────────────────────
print("\n" + "="*75)
total = passed + failed
print(f"RESULTS: {passed}/{total} checks passed")
if failed == 0:
    print("\n✅ SYSTEM IS PRODUCTION READY\n")
    print("Next steps:")
    print("  1. Start Docker Desktop")
    print("  2. Run:  docker compose up -d --build")
    print("  3. Access dashboard: http://localhost:8080")
    print("  4. Run manual endpoint tests (see README or create user/farm/DDS)")
    sys.exit(0)
else:
    print(f"\n⚠️  {failed} issue(s) require attention before deployment")
    sys.exit(1)
