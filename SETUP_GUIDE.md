# Plotra Mobile Capture App - Complete Setup Guide

## What Was Created

### Backend (FastAPI) Changes

1. **GPS Capture Model** (`app/models/gps.py`)
   - `GpsCapture` table with full GPS metadata
   - Spatial and regular indexes for performance
   - Relationships to Farm and Parcel

2. **API Schemas** (`app/api/schemas.py`)
   - `GpsCaptureCreate` - capture payload
   - `GpsCaptureResponse` - full capture record
   - `CaptureAnalysisResponse` - capture + analysis + recommendations

3. **Capture API Router** (`app/api/v2/capture.py`)
   - `GET /api/v2/capture/farms` - list all farms for selection
   - `GET /api/v2/capture/farms/{id}/parcels` - list farm parcels
   - `POST /api/v2/capture/capture` - capture point + instant analysis
   - `GET /api/v2/capture/capture/{id}` - retrieve capture with analysis

4. **Analysis Engine**
   - PostGIS `ST_Contains` to check point inside parcel
   - Automatic parcel detection from farm boundaries
   - Risk scoring (low/medium/high) with compliance status
   - Distance-to-boundary calculation
   - Accuracy and capture method adjustments
   - Actionable recommendations

5. **Model Relationships**
   - `Farm.gps_captures` added
   - `LandParcel.gps_captures` added

### Frontend (React Native + Expo) - Standalone App

**Folder:** `plotra_capture_app/`

**Key Files:**
```
plotra_capture_app/
├── App.js                          # App entry with providers
├── package.json                    # Dependencies & scripts
├── app.json                        # Expo config (Android/iOS bundle IDs)
├── eas.json                        # Build profiles (APK/AAB)
├── babel.config.js                 # Babel config
├── .env.example                    # Environment template
├── QUICKSTART.md                   # Quick start guide
├── README.md                       # Full documentation
│
└── src/
    ├── config/index.js             # API URL & GPS thresholds
    ├── context/AuthContext.js      # JWT auth state management
    ├── navigation/AppNavigator.js  # Stack navigator with auth guard
    │
    ├── services/api.js             # Axios instance + all API calls
    │
    └── screens/
        ├── LoginScreen.js          # Email/password login
        ├── RegisterScreen.js       # New user registration
        ├── FarmListScreen.js       # User's farms only (authenticated)
        ├── ParcelSelectionScreen.js # Select parcel or skip
        └── CaptureScreen.js        # GPS capture + real-time analysis
```

## Database Migration

Run these commands to create the `gps_capture` table:

```bash
cd /path/to/plotra/backend

# Generate migration
alembic revision --autogenerate -m "Add gps_capture table"

# Apply to database
alembic upgrade head
```

The migration will create:
- `gps_capture` table with all fields
- Spatial indexes on `land_parcel.boundary_geometry` (PostGIS)
- Foreign key constraints

## Quick Start: Run the App

### 1. Start Backend (if not running)

```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Install Mobile App Dependencies

```bash
cd plotra_capture_app
npm install
```

### 3. Configure API URL

Edit `plotra_capture_app/app.json`:
```json
{
  "expo": {
    "extra": {
      "API_BASE_URL": "http://192.168.1.100:8000/api/v2"
    }
  }
}
```

**Get your computer's LAN IP:**
- Windows: `ipconfig` → look for IPv4 address
- Mac/Linux: `ifconfig` or `ip addr`

**For Android emulator only:** Use `http://10.0.2.2:8000/api/v2`

### 4. Update Backend CORS

In your backend config, allow mobile dev URL:

```python
# settings.py or config.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://localhost:19006",        # Expo dev default
    "http://192.168.1.100:19006",    # Your LAN IP
    "http://10.0.2.2:19006",         # Android emulator
]
```

### 5. Run in Development

```bash
cd plotra_capture_app
npm start
```

- Scan QR with **Expo Go** app (Android/iOS)
- Or press `a` for Android emulator
- Or press `i` for iOS simulator

### 6. Test the Flow

1. **Register** new user (or login with existing)
2. **Farm List** shows only farms owned by logged-in user
3. Tap **"Capture GPS"** on a farm card
4. **Select Parcel** (optional) → or skip to auto-detect
5. **Capture Screen**:
   - Wait for GPS accuracy (green = good, red = poor)
   - Add optional field notes
   - Tap **"Capture & Analyze"**
6. **Results** show:
   - Compliance status (Compliant/Non-Compliant)
   - EUDR risk score %
   - Parcel detected (if inside)
   - Recommendations list

## Build APK for Distribution

### Prerequisites
- Node.js installed
- Expo account (free): https://expo.dev/signup
- EAS CLI: `npm install -g eas-cli`

### Build Commands

#### Development Debug APK
```bash
cd plotra_capture_app
npx expo run:android
```
- Generates debug APK at: `android/app/build/outputs/apk/debug/`
- For testing only (not for distribution)

#### Release APK (Signed)
```bash
cd plotra_capture_app
eas build --platform android --profile preview
```
- Uploads to Expo servers, builds in cloud
- Download APK from expo.dev dashboard (~15 min)
- APK can be installed on any Android device

#### Production AAB (Google Play Store)
```bash
eas build --platform android --profile production
```
- Generates signed Android App Bundle (.aab)
- Upload to Google Play Console

### Configure EAS Build Profiles

Edit `eas.json`:
```json
{
  "build": {
    "production": {
      "android": {
        "buildType": "app-bundle"
      }
    },
    "preview": {
      "android": {
        "buildType": "apk"
      }
    }
  }
}
```

First build will prompt to configure:
- Keystore (EAS can manage automatically)
- App version code
- Release notes

## Troubleshooting

### "Network request failed"
- Check backend URL in `app.json` matches your IP
- Verify CORS allows your dev URL
- Test: `curl http://YOUR-IP:8000/api/v2/health`

### GPS Accuracy Poor
- Use physical device (emulator GPS is simulated)
- Go outdoors, away from metal structures
- Wait for GPS to lock (can take 30-60 sec)
- Check device location settings (High Accuracy mode)

### Login/Token Issues
- Ensure backend `/api/v2/auth/token` endpoint works
- Check email/password correct
- Verify user exists in database
- Backend logs will show auth errors

### Build Fails
- Run `eas whoami` to confirm logged in
- Ensure `android/` folder isn't corrupted (delete and `npx expo prebuild`)
- Check Expo build logs online

### App Crashes on Launch
- Check device logs (`adb logcat` for Android)
- Common issue: missing API URL - double-check `app.json`
- Ensure `expo-location` plugin is in `app.json`

## File-by-File Reference

See `README.md` in `plotra_capture_app/` for complete documentation.

---

**Ready to build?** Run `npm start` and scan the QR code!
