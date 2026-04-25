# 🔧 FIX SUMMARY — 2026-04-23

## Problem
After rebuilding Docker containers, the dashboard returned **502 Bad Gateway** for all `/api/*` requests.

**Nginx error:** `connect() failed (111: Connection refused) while connecting to upstream, upstream: "http://172.20.0.3:8000"`

## Root Cause
The `docker-compose.yml` used a multi-line `command:` block:

```yaml
command: >
  sh -c "python -m uvicorn app.main:app
         --host 0.0.0.0
         --port 8000
         --workers 1
         --proxy-headers
         --forwarded-allow-ips='*'"
```

When `sh -c` receives a string with newlines, it treats each newline as a **command separator**. Only the first line executed:
```
python -m uvicorn app.main:app
```
All subsequent lines (`--host 0.0.0.0`, etc.) were separate commands that never ran (uvicorn blocked). Uvicorn defaulted to `--host 127.0.0.1`.

Result: Backend only listened on `127.0.0.1` inside container → unreachable from other containers → **502 errors**.

## Solution
Changed to single-line command (no `sh -c` wrapper):

```yaml
command: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'
```

Rebuilt backend image → backend now binds to `0.0.0.0:8000` and is reachable from dashboard.

## Verification
```bash
# From dashboard container
wget -qO- http://backend:8000/health
# => {"status":"healthy",...}

# Check listening sockets
docker exec plotra-backend cat /proc/net/tcp | findstr :1F40
# => 00000000:1F40  (0.0.0.0:8000) ✅

# Backend log startup line
docker logs plotra-backend | findstr "Uvicorn running"
# => INFO: Uvicorn running on http://0.0.0.0:8000 ✅
```

## Files Modified
- `docker-compose.yml` — backend service command (line 50)

## Status
✅ **All endpoints working** — DDS generation, GPS capture, farm creation, all API routes functional.
