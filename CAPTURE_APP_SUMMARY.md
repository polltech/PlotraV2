# CAPTURE APP - FINAL SUMMARY

## Completed Components

### ✅ Backend (FastAPI)
- GPS capture database model (`app/models/gps.py`)
- API schemas (`GpsCaptureCreate`, `GpsCaptureResponse`, `CaptureAnalysisResponse`)
- Capture endpoints (`/api/v2/capture/*`) with full PostGIS analysis
- Point-in-polygon detection using `ST_Contains`
- Risk scoring and compliance engine
- Spatial indexes for performance

### ✅ Mobile App (React Native + Expo)
**Folder:** `plotra_capture_app/`

**Screens:**
1. `LoginScreen.js` - Email/password JWT login
2. `RegisterScreen.js` - New user registration
3. `FarmListScreen.js` - Shows only logged-in user's farms
4. `ParcelSelectionScreen.js` - Choose parcel or skip
5. `CaptureScreen.js` - GPS capture with real-time accuracy + analysis results

**Infrastructure:**
- `AuthContext.js` - Global auth state with SecureStore persistence
- `AppNavigator.js` - Protected routes (requires login)
- `api.js` - All API calls with JWT interceptor
- `config.js` - Backend URL and GPS thresholds

## How to Build APK (Step-by-Step)

### Step 1: Prepare Backend
Your backend must be running and accessible from the internet (for EAS cloud builds).

```bash
# Ensure backend is running
cd app
uvicorn main:app --host 0.0.0.0 --port 8000

# ApplyGPS capture migration
alembic upgrade head
```

### Step 2: Install Expo CLI
```bash
npm install -g eas-cli
eas login  # Login with Expo account
```

### Step 3: Configure App
Edit `plotra_capture_app/app.json`:
- Change `extra.API_BASE_URL` to your **publicly accessible** backend URL
- Example: `https://api.plotra.africa/api/v2`

**Note:** EAS builds run in the cloud, so your backend must be reachable from the internet, not just localhost.

### Step 4: Build APK
```bash
cd plotra_capture_app
eas build --platform android --profile preview
```

This creates a **signable APK** downloadable from expo.dev.

**Build time:** ~10-20 minutes
**APK size:** ~15-25 MB
**Output:** Download link in Expo dashboard

### Step 5: Install on Device
1. Download APK from Expo build page
2. Enable "Install from unknown sources" on Android
3. Open APK file → Install
4. Launch app, login, start capturing

## Testing Before APK Build

### Development Mode (Quick Test)
```bash
cd plotra_capture_app
npm install
npm start
```
- Scan QR with **Expo Go** app
- Works on same WiFi network
- Live reload enabled

### Android Emulator
```bash
npx expo run:android
```
- Requires Android Studio
- Uses emulator's simulated GPS (limited)
- Generates debug APK locally

## Production Deployment

### For Google Play Store
```bash
eas build --platform android --profile production
```

This generates a signed **AAB** (Android App Bundle) ready for Play Console.

**Before production:**
1. Update API_BASE_URL in `app.json` to your live backend
2. Create production keystore (EAS can manage)
3. Update app version in `package.json`
4. Test thoroughly with production backend

### App Icons & Branding
Replace placeholder assets in `plotra_capture_app/assets/`:
- `icon.png` (1024x1024)
- `splash.png` (1284x2778)
- `adaptive-icon.png` (1024x1024 with safe zone)

Generate at: https://expo.dev/pixel-fit

## Backend CORS Configuration

Must allow your mobile app's origin:

```python
# app/core/config.py or settings.py
CORS_ALLOWED_ORIGINS = [
    # Existing
    "http://localhost:3000",
    # Add mobile dev URLs
    "http://localhost:19006",        # Expo dev web
    "http://192.168.1.100:19006",    # Your LAN IP
    "http://10.0.2.2:19006",         # Android emulator
    "exp://192.168.1.100:19000",     # Expo tunnel
]
```

Also update Nginx/proxy if using reverse proxy.

## Database Schema

New table created by migration:
```sql
CREATE TABLE gps_capture (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL REFERENCES farm(id),
    parcel_id INTEGER REFERENCES land_parcel(id),
    captured_by_id VARCHAR(36) REFERENCES users(id),

    -- GPS coords
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    altitude FLOAT,
    accuracy_meters FLOAT,

    -- Metadata
    capture_type VARCHAR(20) DEFAULT 'boundary_point',
    capture_method VARCHAR(20) DEFAULT 'phone_gps',
    gps_fix_type VARCHAR(20),
    satellites_used INTEGER,

    -- Device info
    device_id VARCHAR(100),
    device_model VARCHAR(100),
    app_version VARCHAR(20),

    -- Timestamps
    captured_at TIMESTAMP DEFAULT NOW(),
    uploaded_at TIMESTAMP DEFAULT NOW(),

    -- Additional
    notes TEXT,
    photo_url VARCHAR(500),

    -- Analysis results
    is_outside_parcel BOOLEAN DEFAULT FALSE,
    analysis_completed BOOLEAN DEFAULT FALSE,
    analysis_timestamp TIMESTAMP
);

CREATE INDEX idx_gps_capture_farm ON gps_capture(farm_id);
CREATE INDEX idx_gps_capture_parcel ON gps_capture(parcel_id);
CREATE INDEX idx_gps_capture_coordinates ON gps_capture(latitude, longitude);

-- Ensure PostGIS is enabled, boundary_geometry has GIST index (already in farm model)
```

## API Response Examples

### Successful Capture Response
```json
{
  "capture": {
    "id": 123,
    "latitude": -1.292065,
    "longitude": 36.821946,
    "accuracy_meters": 5.2,
    "captured_at": "2026-01-15T10:30:00Z"
  },
  "analysis": {
    "point_in_parcel": true,
    "risk_level": "low",
    "risk_score": 10.0,
    "compliance_status": "Compliant",
    "distance_to_boundary_meters": null
  },
  "parcel_info": {
    "id": 45,
    "name": "Parcel A",
    "area_hectares": 2.5
  },
  "farm_info": {
    "name": "My Coffee Farm",
    "deforestation_risk_score": 12.5
  },
  "recommendations": [
    "GPS point verified inside registered parcel boundary.",
    "Location complies with EUDR boundary requirements."
  ]
}
```

## Security & Privacy

- **JWT tokens** stored in SecureStore (encrypted)
- **HTTPS enforced** in production (configure backend SSL)
- **No local data** except auth tokens
- **GPS accuracy** shown for user verification
- **User owners hip** enforced (farm_id belongs to user)

## File List (Generated)

See `plotra_capture_app/FILE_LIST.md` for complete file listing with descriptions.

## Support

**Backend Issues:** Check FastAPI logs (`uvicorn` console)
**Mobile Issues:** Use `adb logcat` for Android crash logs
**API Debug:** Test endpoints with curl/Postman first

---

**App is ready to build!** 🚀

To generate APK, run:
```bash
cd plotra_capture_app
eas build --platform android --profile preview
```
