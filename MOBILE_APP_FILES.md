# Complete File List - Plotra Capture App

## Backend Files (modified/created)

### New Files
- `app/models/gps.py` - GPS capture database model with PostGIS support
- `app/api/v2/capture.py` - Capture & analysis API endpoints

### Modified Files
- `app/models/farm.py` - Added `gps_captures` relationship to Farm and LandParcel
- `app/models/__init__.py` - Exported GpsCapture
- `app/api/schemas.py` - Added GPS capture schemas
- `app/api/v2/__init__.py` - Registered capture router

---

## Mobile App Files (standalone folder: `plotra_capture_app/`)

### Root Configuration
```
plotra_capture_app/
├── package.json           # Dependencies (expo, react-navigation, axios, expo-location)
├── app.json              # Expo config (bundle IDs, permissions, API URL)
├── eas.json              # EAS build profiles (preview, production)
├── babel.config.js       # Babel preset (expo)
├── .env.example          # Environment variables template
├── .gitignore           # Git ignore for node_modules, builds, secrets
├── README.md            # Full app documentation
├── QUICKSTART.md        # Quick start commands
└── SETUP_GUIDE.md       # Detailed setup with troubleshooting
```

### Source Code (`src/`)
```
src/
├── config/
│   ├── index.js         # Exports API_BASE_URL, GPS thresholds
│   └── config.js        # Config loader (reads from expo.extra)
│
├── context/
│   └── AuthContext.js   # JWT auth provider (SecureStore, token refresh)
│
├── navigation/
│   └── AppNavigator.js  # Stack navigator with auth guards
│
├── services/
│   └── api.js           # Axios instance, auth/farm/capture API functions
│
├── screens/
│   ├── LoginScreen.js          # Email/password form
│   ├── RegisterScreen.js       # Registration form
│   ├── FarmListScreen.js       # User's farms only (authenticated)
│   ├── ParcelSelectionScreen.js # Select parcel or skip
│   └── CaptureScreen.js        # GPS display, capture button, analysis results
│
└── components/
    └── LoadingSpinner.js   # Reusable loader component
```

### Assets (`assets/`)
```
assets/
├── icon.png           # App icon (1024x1024) - ADD YOUR OWN
├── splash.png         # Splash screen - ADD YOUR OWN
├── adaptive-icon.png  # Android adaptive icon - ADD YOUR OWN
└── favicon.png        # Web favicon - ADD YOUR OWN
```

## Screens Overview

### LoginScreen (src/screens/LoginScreen.js)
- Email & password inputs
- JWT token fetch from `/api/v2/auth/token`
- Stores token & user in AuthContext + SecureStore
- Navigation to Register on "Don't have account?"

### RegisterScreen (src/screens/RegisterScreen.js)
- First name, last name, email, password, country
- Calls `/api/v2/auth/register`
- Auto-login after registration
- Form validation (password length, match)

### FarmListScreen (src/screens/FarmListScreen.js)
- Fetches `GET /api/v2/farmer/farm` (only logged-in user's farms)
- Displays each farm card:
  - Farm name, area, compliance status
  - EUDR risk score bar
  - Number of parcels
  - "Capture GPS" button
- Pull-to-refresh
- Logout button

### ParcelSelectionScreen (src/screens/ParcelSelectionScreen.js)
- Called from FarmListScreen with selected `farm`
- Fetches parcels: `GET /api/v2/capture/farms/{id}/parcels`
- Renders parcel cards (number, area, boundary status)
- Select parcel → navigates to CaptureScreen with parcel
- "Skip" button → navigates without parcel (auto-detect)

### CaptureScreen (src/screens/CaptureScreen.js)
**Section 1: GPS Status**
- Real-time location watch via `expo-location`
- Accuracy indicator (green/red dot)
- Shows lat, lon, altitude, accuracy (meters)

**Section 2: Notes**
- Optional multiline text input

**Section 3: Capture Button**
- Validates accuracy (< 30m warning)
- Sends POST to `/api/v2/capture/capture`
- Shows loading spinner

**Section 4: Analysis Results**
- Compliance status card (color-coded)
- Risk score circle (percentage)
- Parcel detected info (if any)
- Capture details (coordinates, accuracy)
- Recommendations list
- "New Capture" button

## API Layer (`src/services/api.js`)

### Axios Instance
- Base URL from config
- Request interceptor: adds `Authorization: Bearer <token>`
- Response interceptor: handles 401 (auto-logout)

### Auth API
```javascript
authAPI.login(email, password) → /auth/token
authAPI.register(userData) → /auth/register
authAPI.getMe() → /auth/me
authAPI.refreshToken() → /auth/refresh
```

### Farm API
```javascript
farmAPI.getMyFarms() → /farmer/farm
farmAPI.getParcels(farmId) → /capture/farms/{farmId}/parcels
farmAPI.getAll() → /capture/farms (public list)
```

### Capture API
```javascript
captureAPI.capture(data) → POST /capture/capture
captureAPI.getCapture(id) → GET /capture/capture/{id}
```

## Auth Context (`src/context/AuthContext.js`)

**State:**
```javascript
{
  isAuthenticated: boolean,
  user: Object | null,
  token: string | null,
  isLoading: boolean,
  error: string | null
}
```

**Actions:**
- `login(email, password)` → fetches token + user, saves to SecureStore
- `register(userData)` → registers then logs in
- `logout()` → clears storage, resets state
- `updateUser(user)` → updates current user in state & storage

**Persistence:**
- Token stored in `expo-secure-store` (Keychain/Keystore)
- User profile stored as JSON
- Auto-loads on app start, verifies token validity

## Navigation Flow

```
Stack Navigator (unauthenticated)
├── Login
└── Register

Stack Navigator (authenticated)
├── FarmList (main screen)
├── ParcelSelection (optionally from farm card)
└── Capture (optionally from parcel selection)
```

**Auth guard in AppNavigator.js:**
- If `isAuthenticated === false` → show auth screens only
- If `isAuthenticated === true` → show main app screens

Back button behavior:
- ParcelSelection → FarmList
- Capture → ParcelSelection (or FarmList if skipped)

## Configuration Files

### `app.json`
- Android package: `africa.plotra.capture`
- iOS bundle: `africa.plotra.capture`
- Location permission plugin
- API_BASE_URL in `extra` field

### `eas.json`
- `development` → development client
- `preview` → APK build
- `production` → AAB for Play Store

### `package.json`
Main dependencies:
- `expo` ~50.0
- `react-native` 0.73
- `@react-navigation/native` + `native-stack`
- `expo-location` ~17
- `expo-secure-store` ~12
- `axios` ^1.6.0

Scripts:
- `npm start` → Expo dev server
- `npm run android` → `expo run:android`
- `npm run build:android` → `eas build --platform android --profile apk`
- `npm run build:android:aab` → `eas build --platform android --profile production`

## Next Steps After Creation

1. **Install dependencies:** `npm install` in `plotra_capture_app/`
2. **Add app icons** (optional): Place PNGs in `assets/`
3. **Configure API URL** in `app.json` or via `eas build --env`
4. **Update CORS** in backend to allow mobile dev origins
5. **Test in Expo Go** (`npm start` + scan QR)
6. **Build APK** (`eas build --platform android --profile preview`)
7. **Distribute** to testers or upload to Play Store

---

**All files are created and ready to use!** 🎉
