# Plotra Polygon Capture App — Offline-First Mobile Application

**Kenya Cooperative Pilot** · Android 8.0+ · Offline-first

Complete React Native mobile app for walking farm boundaries and submitting polygon data to Plotra backend with offline queue support.

---

## 📱 Screens Flow (Prototype Sections)

```
S1 → Farm ID Entry
  ↓
S2 → Farm Confirmation (details check)
  ↓
S3 → Walk Boundary (map + polygon draw)
  ├─ S4: Topology error (inline, not separate screen)
  ↓
S5 → Review Polygon (area, submit)
  ↓
S6 / S7 → OfflineSaved / Submitted (depending on connectivity)
  ↓
S8 → Queue List (view all captures)
```

**Navigation:**
- Back button available on S2, S3, S5
- Queue accessible from S1 (top) and from success screens

---

## ✨ Features

- **Offline-first architecture** — Capture without internet, auto-sync later
- **Map-based polygon capture** — Walk boundary, tap to mark points
- **Real-time GPS accuracy indicator** — Green (good), Red (poor)
- **Turf.js topology validation** — Self-intersection, area minimum, closed ring
- **Local SQLite queue** — Persists across app restarts
- **Auto-sync on reconnect** — Background sync when online
- **Retry failed submissions** — Manual retry button
- **Farm confirmation check** — Prevents wrong farm selection
- **Area calculation** — Automatic (turf.js)
- **4+ points required** — Min boundary complexity

---

## 🔧 Tech Stack

- **React Native 0.73** with Expo SDK 50
- **React Navigation** (Native Stack)
- **react-native-maps** — Map display & polygon drawing
- **expo-location** — High-accuracy GPS
- **expo-sqlite** — Local offline storage
- **expo-network** — Connectivity detection
- **expo-secure-store** — JWT token storage
- **@turf/turf** — Polygon area, topology validation
- **axios** — API calls

---

## 🏗️ Project Structure

```
plotra_polygon_app/
├── App.js                          # App entry (providers)
├── package.json                    # Dependencies
├── app.json                        # Expo config + API URL
├── eas.json                        # Build profiles
├── babel.config.js
├── .gitignore
│
├── README.md                       # This file
├── QUICKSTART.md
└── BUILD_GUIDE.md
│
└── src/
    ├── config/
    │   └── index.js                # API_BASE_URL export
    │
    ├── context/
    │   └── AuthContext.js          # JWT auth (SecureStore)
    │
    ├── navigation/
    │   └── AppNavigator.js         # Stack navigator + auth guard
    │
    ├── services/
    │   ├── api.js                  # Axios + sync service
    │   └── database.js             # SQLite CRUD for offline queue
    │
    ├── utils/
    │   └── helpers.js              # formatDate, calculateDistance, debounce
    │
    └── screens/
        ├── S01_FarmIDEntryScreen.js
        ├── S02_FarmConfirmationScreen.js
        ├── S03_WalkBoundaryScreen.js     ← polygon drawing
        ├── S05_ReviewPolygonScreen.js    ← area, submit
        ├── S06_OfflineSavedScreen.js
        ├── S07_SubmittedScreen.js
        └── S08_QueueListScreen.js
```

---

## 📊 Mockups & UX Specs

### S1 — Farm ID Entry
- Single text input (FR-01)
- CTA enabled when non-empty (FR-03)
- Validation: required field (FR-02)
- Inline red border + "Farm ID required" (FR-02)

### S2 — Farm Confirmation
- Shows: Farm ID, Farm name, Cooperative (FR-04)
- Check details match before proceeding
- "Start polygon walk" primary CTA
- "Wrong farm" back link
- Online fetch if connected, skip gracefully if offline

### S3 — Walk Boundary
**Full-screen map:**
- Real-time blue dot (user location)
- Tapped points shown as numbered markers
- Live polygon fill as you walk
- GPS accuracy indicator (FR-12): dot color + "GPS accuracy: X m"

**Controls:**
- "+ Mark point here" (FAB) — adds current GPS as vertex
- "Undo last" — removes last point
- "Clear and restart walk" — clears all

**Topology error (S4) as inline state** — not separate screen:
- Warning banner: "Boundary lines cross. Walk the boundary in one direction without backtracking."
- Button: "Undo last point and fix" (FR-11)
- Button: "Clear and restart walk"
- Plain language only, no raw errors
- Turf.js checks in <2 seconds (NF-03)

**Minimum 4 points required** to enable Save button.

### S5 — Review Polygon
- Large area display: `1.4320 hectares — calculated area` (FR-10)
- Static map preview with polygon
- Stats: points count, perimeter (optional)
- "Submit to Plotra" primary button (FR-13)
- "Re-walk boundary" secondary button

### S6 — Offline Saved
- Warning icon: `📡`
- Status: "Offline"
- Message: "Saved locally. Will sync automatically when connectivity is restored."
- Shows farm ID, area, points
- "Capture another farm" primary
- "View all queued" secondary
- Persists across restarts (NF-04)

### S7 — Submitted
- Success icon: `✓`
- Message: "Polygon received by Plotra"
- "KE-NYR-00412 is ready for satellite review"
- Status badge: "Synced"
- "Capture another farm" CTA
- "View all records"

### S8 — Queue List
- All records table (FR-16):
  - Status badge (Synced/Pending/Failed)
  - Farm ID
  - Area (2 dp)
  - Points count
  - Timestamp
- Filter tabs: All / Pending / Synced / Failed
- Failed rows show "Retry" button (FR-17)
- FAB "+" to start new capture
- Persists across app restarts (NF-04)

---

## 📡 API Integration

### Backend API Endpoints (new)

```
POST   /api/v2/polygon/queue           # Add to offline queue (or submit if online)
GET    /api/v2/polygon/queue/:farmId   # List pending captures (for S8)
POST   /api/v2/polygon/queue/:id/submit  # Sync single capture to server
POST   /api/v2/polygon/queue/:id/retry   # Retry failed sync
```

### Existing endpoints still used
```
GET    /api/v2/farmer/farm/:id         # Get farm details (S2)
POST   /api/v2/auth/token               # Login
GET    /api/v2/auth/me                  # Current user
```

### Payload format

**Submit polygon:**
```json
{
  "farm_id": 1,
  "parcel_name": "North Field",
  "boundary_geojson": {
    "type": "Polygon",
    "coordinates": [[
      [36.821946, -1.292065],
      [36.822100, -1.292200],
      [36.822300, -1.292050],
      [36.822050, -1.291900],
      [36.821946, -1.292065]  // close ring
    ]]
  },
  "area_hectares": 1.4320,
  "perimeter_meters": 567.8,
  "points_count": 5,
  "captured_at": "2026-01-15T10:30:00Z",
  "device_info": {
    "model": "Samsung Galaxy S23",
    "app_version": "1.0.0"
  }
}
```

**Local SQLite queue record:**
```json
{
  "id": 1,
  "farm_id": "KE-NYR-00412",
  "parcel_name": null,
  "boundary_geojson": { ... },
  "area_hectares": 1.4320,
  "points_count": 5,
  "sync_status": "pending",  // or "synced", "failed"
  "created_at": "2026-01-15 09:14:00",
  "synced_at": null
}
```

---

## 🗄️ Offline Storage (SQLite)

**Table:** `polygon_captures`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `farm_id` | TEXT | Farm identifier |
| `boundary_geojson` | TEXT | GeoJSON string |
| `area_hectares` | REAL | Calculated area |
| `points_count` | INTEGER | Number of vertices |
| `captured_at` | TEXT | ISO timestamp |
| `sync_status` | TEXT | `pending` \| `synced` \| `failed` |
| `sync_attempts` | INTEGER | Retry counter |
| `last_sync_error` | TEXT | Error message if failed |

**Indexes:** on `sync_status`, `farm_id`

**Migrations:** Expo SQLite auto-creates on first run.

---

## 🌍 Connectivity & Sync

### Online Behavior
- User taps "Submit" → POST to `/api/v2/polygon/queue`
- Server creates LandParcel immediately
- UI shows → "Submitted" screen (S7) with "Synced" badge
- Record saved locally with status `synced`

### Offline Behavior
- User taps "Submit" → save to local SQLite with status `pending`
- UI shows → "OfflineSaved" screen (S6) with orange warning
- Record persists in local DB (NF-04)
- Background task checks connectivity every 30s
- When online: auto-syncs all `pending` → POST to server
- On success: updates local record to `synced`
- On failure: updates to `failed` with error message

### Manual Retry
- In Queue List (S8), failed records show "Retry" button (FR-17)
- Tapping triggers immediate sync attempt

---

## 🗺️ Map & Capture Logic

### Coordinate System
- WGS84 (EPSG:4326) — standard GPS
- All coordinates stored as `[longitude, latitude]` per GeoJSON spec

### Point Capture
- User taps map: captures current GPS location (blue dot)
- Points must be ≥5m apart (prevents duplicates)
- Minimum 4 points required for closed polygon (FR-06)

### Area Calculation
Uses Turf.js:
```javascript
const polygon = turf.polygon([coordsForTurf]);
const areaSqM = turf.area(polygon);      // m²
const hectares = areaSqM / 10000;
```

### Topology Validation (run after every point addition)
1. `turf.booleanValid(polygon)` — valid geometry
2. `turf.kinks(polygon)` — self-intersection detection
3. Area > 0.1 ha minimum
4. Closed ring check

Errors shown in inline banner (FR-11) with plain language messages.

---

## 🎨 Color Scheme (per prototype)

| State | Color | Hex |
|-------|-------|-----|
| Primary action | Green | `#4caf50` |
| Primary brand (Plotra brown) | Brown | `#6f4e37` |
| Offline/warning | Orange | `#ff9800` |
| Error | Red | `#f44336` |
| Success | Green | `#4caf50` |
| Background | Light gray | `#f5f5f5` |

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
cd plotra_polygon_app
npm install
```

### 2. Configure Backend URL

Edit `app.json` → `extra.API_BASE_URL`:
```json
{
  "expo": {
    "extra": {
      "API_BASE_URL": "http://192.168.100.5:8000/api/v2"
    }
  }
}
```

Use your computer's LAN IP (same as `ipconfig`).

### 3. Update Backend CORS

In `app/core/config.py`, add mobile dev origin:
```python
CORSConfig.allowed_origins = [
    "http://localhost:19006",
    "http://192.168.100.5:19006",  # ← your IP
]
```

Restart backend.

### 4. Quick Test (Expo Go)

```bash
npx expo start
```

- Install **Expo Go** on Android
- Scan QR (same WiFi)
- Login → Test boundary walk (go outside for GPS)
- Verify polygon submission

### 5. Build APK

```bash
# Install EAS CLI (one-time)
npm install -g eas-cli

# Login
eas login

# Build
eas build --platform android --profile preview
```

Download APK from expo.dev when complete (~15 min).

---

## 📦 Build Configuration

### `package.json` highlights
Dependencies: expo, react-native-maps, turf, expo-sqlite, expo-location, axios

### `eas.json` build profiles
- **preview** → APK (debuggable, for testing)
- **production** → AAB (Google Play Store)

### Permissions (Android)
```json
"permissions": ["ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION"]
```

iOS info.plist includes location usage descriptions.

---

## 🧪 Testing Checklist

### Offline Mode
- [ ] Airplane mode ON
- [ ] Capture polygon → "OfflineSaved" screen appears
- [ ] Close app, reopen → record still in Queue List (S8)
- [ ] Turn on WiFi → auto-sync should happen
- [ ] Record status changes to "Synced"

### Online Mode
- [ ] WiFi ON
- [ ] Capture polygon → "Submitted" screen appears immediately
- [ ] Backend receives POST → creates LandParcel
- [ ] GPS accuracy indicator shows green (< 5m) under open sky

### Topology Validation
- [ ] Walk boundary in consistent direction → no error
- [ ] Deliberately cross lines → error banner appears
- [ ] Undo fixes error

### Map Interaction
- [ ] Blue dot follows real location
- [ ] Tapping "Mark point" adds vertex
- [ ] Points connected in order with polygon fill
- [ ] Undo removes last point
- [ ] Clear resets entire walk

---

## 🐛 Troubleshooting

### "npm install" fails
- Run CMD as Administrator
- Or PowerShell: `Set-ExecutionPolicy RemoteSigned`

### Map doesn't show
- Google Maps API key required (in `app.json` → `ios.config.googleMapsApiKey`)
- Get free key: https://console.cloud.google.com/google/maps-apis
- Add to `app.json`

### GPS poor accuracy
- Use physical device outdoors
- Enable "High accuracy" in Android Location settings
- Wait 30-60s for GPS lock
- Accuracy threshold: 10m green, >30m red

### Offline queue not persisting
- Expo SQLite uses app sandbox — persists across restarts
- Check `dbService.init()` called before any DB ops
- View DB: `adb shell "run-as africa.plotra.polygon cat files/./plotra_capture.db"`

### "Network request failed"
- Backend must be reachable from device (same WiFi)
- Test: phone browser → `http://192.168.100.5:8000/api/v2/health`
- CORS must include mobile dev origin
- Update `app.json` API_BASE_URL if IP changed

### Build fails (EAS)
- Verify `eas whoami` shows logged in
- Check build logs at https://expo.dev/accounts/
- Ensure `app.json` valid JSON (no trailing commas)
- Expo account free tier has limits

---

## 📱 Device Requirements

- **Android 8.0+** (API 26+)
- **GPS hardware** required (no emulator for testing)
- **256 MB free storage** (for offline DB)
- **Location permission** granted on first launch

---

## 🔄 Sync Strategy

| Condition | Action |
|-----------|--------|
| Online + Pending records | Auto-sync every 30s |
| Capture submitted online | Immediate POST → success screen |
| Capture submitted offline | Save to SQLite → show "OfflineSaved" |
| User returns online | Retry all `pending` records |
| Sync fails (server error) | Mark `failed`, show retry button |
| User taps Retry | Re-attempt POST for that record |

**No duplicate submissions** — `external_id` stored on first successful sync.

---

## 📁 Data Flow

```
User taps "Mark point"
      ↓
GPS coordinate captured
      ↓
Added to local polygon array
      ↓
Polygon rendered on map (live)
      ↓
User taps "Save polygon"
      ↓
[If offline]
   → Save to SQLite (status=pending)
   → Show S6 (OfflineSaved)
[If online]
   → POST /api/v2/polygon/queue
   → Show S7 (Submitted)

Background sync (if pending records exist + online):
   → POST each pending
   → On success: update status=synced, store server ID
   → On failure: status=failed, store error
```

---

## 🎯 Requirements Coverage

| FR | Implemented |
|----|-------------|
| FR-01: Single farm ID input on launch | ✅ S01 |
| FR-02: Inline validation error | ✅ Red border + text |
| FR-03: farm_id carried to API | ✅ passed through all screens |
| FR-04: Optional farm details fetch | ✅ S02 (graceful offline fallback) |
| FR-05: Mark point via map tap | ✅ S03 "Mark point here" |
| FR-06: Min 4 points required | ✅ Button disabled until 4 |
| FR-07: Real-time polygon render | ✅ React Native Maps Polygon |
| FR-08: Blue dot GPS position | ✅ Map shows user location |
| FR-09: Undo last point | ✅ "Undo last" button |
| FR-10: Area in hectares (4 dp) | ✅ S05 shows 4 dp |
| FR-11: Topology validation | ✅ Turf.js inline error |
| FR-12: GPS accuracy indicator | ✅ Dot color + numeric |
| FR-13: Single-tap submit | ✅ S05 "Submit to Plotra" |
| FR-14: Online immediate send | ✅ POST + success screen |
| FR-15: Offline save to local queue | ✅ SQLite insert |
| FR-16: View all records + status | ✅ S08 Queue List |
| FR-17: Retry failed | ✅ Retry button on failed cards |
| FR-18: Prevent duplicate submit | ✅ `synced` status prevents resubmit |
| FR-19: Auto-sync on reconnect | ✅ Background 30s poll |
| NF-03: Validation < 2s | ✅ Turf runs in ~100ms |
| NF-04: Persists across restart | ✅ SQLite on device |

**ALL PROTOTYPE REQUIREMENTS COVERED** ✅

---

## 🚀 Next Steps After Build

1. **Deploy backend** with CORS for mobile IP
2. **Test with Expo Go** first (`npm start`)
3. **Configure Google Maps API key** (for map tiles)
4. **Build APK** with EAS
5. **Install on device** and test in field
6. **Iterate** based on field officer feedback

---

**Questions?** See `BUILD_GUIDE.md` for detailed build instructions.
