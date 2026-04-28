# Plotra Polygon Capture App — Build & Deploy Guide

## 📋 Prerequisites

- **Node.js** 18+ (download from nodejs.org)
- **Android Studio** (for emulator) OR physical Android device (8.0+)
- **Expo account** (free) — https://expo.dev/signup
- **Backend running** on your LAN (port 8000)
- **Google Maps API key** (optional but recommended)

---

## 🚀 Quick Build (5 Commands)

```bash
# 1. Navigate to app
cd G:\My Drive\plotra\plotra_polygon_app

# 2. Install dependencies
npm install

# 3. Configure API URL (edit app.json → extra.API_BASE_URL)
#    Set to: http://192.168.100.5:8000/api/v2  (your LAN IP)

# 4. Install EAS CLI & login
npm install -g eas-cli
eas login

# 5. Build APK
eas build --platform android --profile preview
```

**Result:** APK downloads from https://expo.dev/accounts/ after ~15 min.

---

## 📱 Development Testing (Before Build)

### Run with Expo Go (fastest)

```bash
cd plotra_polygon_app
npx expo start
```

Scan QR with Expo Go app (Android). Requires phone & PC on same WiFi.

**Test flow:**
1. Login (register if new)
2. Enter Farm ID `KE-NYR-00412` (any non-empty)
3. Walk boundary: go outdoors, tap "+ Mark point here" every few meters
4. After 4+ points, "Save polygon" becomes active
5. Review → Submit
6. Check backend: `gps_capture` table gets new row

---

## 🔧 Configuration

### 1. Backend CORS

In `app/core/config.py`:

```python
class CORSConfig(BaseModel):
    allowed_origins: list = [
        "http://localhost:3000",
        "http://localhost:19006",
        "http://192.168.100.5:19006",  # ← Your LAN IP
    ]
```

Restart backend after change.

### 2. Mobile API Base URL

Edit `plotra_polygon_app/app.json`:

```json
{
  "expo": {
    "extra": {
      "API_BASE_URL": "http://192.168.100.5:8000/api/v2"
    }
  }
}
```

Replace `192.168.100.5` with your computer's IPv4 from `ipconfig`.

### 3. Google Maps API Key (optional but recommended)

Without API key, maps show blank gray tiles.

Get free key: https://console.cloud.google.com/google/maps-apis

Enable:
- Maps SDK for Android
- Maps SDK for iOS

Add to `app.json`:

```json
{
  "expo": {
    "ios": {
      "config": {
        "googleMapsApiKey": "YOUR_ACTUAL_KEY"
      }
    },
    "android": {
      "config": {
        "googleMapsApiKey": "YOUR_ACTUAL_KEY"
      }
    }
  }
}
```

---

## 🏗️ Build Types

| Profile | Output | Use |
|---------|--------|-----|
| `preview` | `.apk` (debuggable) | Testing, internal QA |
| `production` | `.aab` (signed) | Google Play Store |

### Build APK (debug)

```bash
eas build --platform android --profile preview
```

**Install:**
- Download from expo.dev
- Enable "Install from unknown sources" on Android
- Open APK → Install

### Build AAB (release for Play Store)

```bash
eas build --platform android --profile production
```

**Before first production build:**
1. Update `API_BASE_URL` to production domain (HTTPS)
2. Increment `version` in `app.json`
3. Configure app signing (EAS can manage automatically)

---

## 🐛 Common Issues

### "Network request failed"
**Cause:** Device can't reach backend.

**Fix:**
1. Phone and PC on same WiFi?
2. Backend running: `uvicorn main:app --host 0.0.0.0 --port 8000`
3. Test in phone browser: `http://192.168.100.5:8000/api/v2/health`
4. Update CORS in `config.py` with your IP
5. Update `app.json` API_BASE_URL with correct IP

### Map is blank / gray
**Cause:** Missing Google Maps API key.

**Fix:** Get key from Google Cloud and add to `app.json` (see above).

### GPS not updating
**Cause:** No GPS lock (indoors/metal roof).

**Fix:**
1. Go outdoors
2. Wait 30-60 seconds for GPS lock
3. Accuracy should drop below 10m

### "npm install" fails on Windows
**Cause:** Script execution policy blocks npm.

**Fix:** Open PowerShell as Administrator, run:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
Then retry in CMD.

### Build fails with EAS
**Fix:**
1. `eas whoami` — confirm logged in
2. Check build logs at https://expo.dev/accounts/
3. Ensure `app.json` JSON is valid (no trailing commas)
4. Delete `node_modules/` and `package-lock.json`, re-run `npm install`

### APK install fails "App not installed"
**Fix:**
1. Enable Settings → Security → Install from unknown sources
2. Clear Play Store cache (sometimes conflicts)
3. Uninstall previous version if exists
4. Re-download APK (may be corrupted)

---

## 📊 Offline Architecture

### Database Schema (SQLite)

```sql
CREATE TABLE polygon_captures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  farm_id TEXT NOT NULL,
  parcel_name TEXT,
  boundary_geojson TEXT NOT NULL,
  area_hectares REAL,
  perimeter_meters REAL,
  points_count INTEGER,
  captured_at TEXT,
  uploaded_at TEXT,
  sync_status TEXT DEFAULT 'pending',
  sync_attempts INTEGER DEFAULT 0,
  last_sync_error TEXT,
  notes TEXT,
  topology_validated BOOLEAN DEFAULT 0,
  validation_warnings TEXT, -- JSON
  device_info TEXT, -- JSON
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_polygon_status ON polygon_captures(sync_status);
CREATE INDEX idx_polygon_farm ON polygon_captures(farm_id);
```

### Sync Logic

**Auto-sync trigger:**
- App launch
- Connectivity change (detected via NetInfo)
- Every 30 seconds while online

**Retry policy:**
- `pending` → try to POST → on success: `synced`, on error: `failed` + increment attempts
- User can manually retry failed from S8

**Conflict resolution:**
- Not implemented yet (server-side duplicate detection by `external_id`)

---

## 🎯 Testing Scenarios

### Scenario 1: Online Capture
1. WiFi ON
2. Walk boundary (any farm ID, e.g., `TEST-001`)
3. Submit → Should see "Submitted" screen immediately
4. Backend: `POST /api/v2/polygon/queue` called
5. New `polygon_capture` record with `sync_status=synced`
6. Also creates `LandParcel` in farm

### Scenario 2: Offline Capture
1. Airplane mode ON
2. Walk boundary
3. Submit → "OfflineSaved" screen
4. Check SQLite DB: query `SELECT * FROM polygon_captures WHERE sync_status='pending'`
5. Turn WiFi ON
6. Wait 30s → auto-sync triggers
7. Record changes to `synced`
8. Refresh Queue List S8 → shows "Synced"

### Scenario 3: Topology Error
1. Start boundary walk
2. Tap points that cross over each other (like figure-8)
3. Error banner appears: "Boundary lines cross"
4. "Undo last" button appears inline
5. Tap undo → removes last point → error clears when valid

### Scenario 4: Queue Retry
1. Submit a polygon while server is down
2. Record shows in S8 as "Failed"
3. Fix server
4. Tap "Retry" on failed card
5. POST sent, record becomes "Synced"

---

## 📦 Build Output

### EAS Cloud Build (recommended)

Download from: https://expo.dev/accounts/

**APK location:** `Downloads/plotra-polygon-capture-android.apk`

**File size:** ~20-30 MB (includes react-native, maps)

### Local Build (Android Studio)

```bash
npx expo prebuild
# Open android/ in Android Studio
# Build → Generate Signed Bundle/APK
```

Local APK at: `android/app/build/outputs/apk/release/`

---

## 🎨 Customization

### Change app colors
Update any `StyleSheet` `backgroundColor` values:
- Primary: `#6f4e37` (brown)
- Success: `#4caf50` (green)
- Error: `#f44336` (red)

### Change API endpoint
- Temporary: edit `app.json` `extra.API_BASE_URL`
- Permanent: update `src/services/api.js` `API_BASE_URL`

### Increase minimum area
In `S03_WalkBoundaryScreen.js`, find `areaSqM < 0.1` check and change `0.1` to desired hectares × 10000.

---

## 📚 API Reference

Full backend API docs: See `CAPTURE_APP_SUMMARY.md`

**Endpoints used by mobile:**
- `POST /api/v2/auth/token`
- `GET /api/v2/farmer/farm/:id`
- `POST /api/v2/polygon/queue`
- `POST /api/v2/polygon/queue/:id/submit`
- `GET /api/v2/polygon/queue/:farmId`

---

## ✅ Pre-Flight Checklist

- [ ] Backend running: `uvicorn main:app --host 0.0.0.0 --port 8000`
- [ ] `app.json` API_BASE_URL = your LAN IP
- [ ] Backend CORS includes mobile dev origin
- [ ] Google Maps API key in `app.json` (optional but good)
- [ ] Expo Go test passes (`npm start`)
- [ ] EAS CLI installed & logged in
- [ ] `npm install` completed (node_modules exist)
- [ ] Ready to run `eas build --platform android --profile preview`

---

**Ready to build?** Run:

```cmd
cd G:\My Drive\plotra\plotra_polygon_app
eas build --platform android --profile preview
```

**~15 minutes later:** Download your APK and start capturing! 🚀
