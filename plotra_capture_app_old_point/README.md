# Plotra Capture App

A lightweight React Native mobile app for capturing GPS coordinates and performing instant EUDR compliance analysis. Designed for field officers to verify farm boundaries and get immediate risk assessment.

## Features

- **Secure Authentication** - JWT-based login/registration
- **Farm Selection** - View only farms assigned to your account
- **Parcel Selection** - Choose specific parcel or skip for auto-detection
- **High-Accuracy GPS Capture** - Uses device GPS with accuracy indicator
- **Instant Analysis** - Server-side EUDR risk scoring and compliance check
- **Field Notes** - Add optional observations to each capture
- **Compliance Recommendations** - Actionable insights based on capture result

## Tech Stack

- **React Native** with Expo SDK 50
- **React Navigation** for screen management
- **Expo Location** for GPS access
- **Expo SecureStore** for secure token storage
- **Axios** for API communication
- **Context API** for authentication state

## Prerequisites

1. **Node.js** 18+ and npm
2. **Expo CLI** (optional for development): `npm install -g expo-cli`
3. **Android Studio** (for Android builds)
4. **Expo EAS** account (for APK builds): `npm install -g eas-cli`

## Setup Instructions

1. **Clone/download** the mobile app folder `plotra_capture_app`

2. **Install dependencies:**
   ```bash
   cd plotra_capture_app
   npm install
   ```

3. **Configure Backend API:**
   - Edit `app.json` → `extra.API_BASE_URL` with your backend URL
   - Or create `.env` file:
     ```
     EXPO_PUBLIC_API_BASE_URL=https://your-backend.com/api/v2
     ```

4. **Run in development (Expo Go):**
   ```bash
   npm start
   ```
   - Scan QR code with Expo Go app on your phone
   - Or press `a` to run on Android emulator

5. **Configure Backend CORS** (in your backend settings):
   - Ensure mobile app origin is allowed: `http://localhost:19006` (dev) or your domain

## Building APK

### Option 1: Using EAS Build (Recommended)

EAS Build generates signed APKs/AABs for distribution.

1. **Install EAS CLI:**
   ```bash
   npm install -g eas-cli
   ```

2. **Login to Expo:**
   ```bash
   eas login
   ```

3. **Configure build profile** in `eas.json` (auto-generated on first build)

4. **Build APK:**
   ```bash
   cd plotra_capture_app
   eas build --platform android --profile apk
   ```
   - APK will be downloadable from Expo build dashboard
   - Build can take 10-20 minutes

5. **For production release** (Google Play Store):
   ```bash
   eas build --platform android --profile production
   ```
   Creates signed AAB (Android App Bundle)

### Option 2: Local Gradle Build (requires Android Studio)

1. **Generate Android project:**
   ```bash
   npx expo prebuild
   ```
   Generates `android/` folder with native code

2. **Open in Android Studio:**
   ```bash
   open -a "Android Studio" android
   ```

3. **Generate signed APK:**
   - Build → Generate Signed Bundle/APK
   - Follow wizard to create keystore
   - Select APK option

4. **APK location:** `android/app/build/outputs/apk/release/app-release.apk`

## Running on Physical Device

### Development Build (Expo Go)
1. Install **Expo Go** app from Play Store
2. Run `npm start` and scan QR code
3. GPS requires physical device (not emulator)

### Standalone Build
- Install APK directly on device
- Enable "Install from unknown sources" in Android settings
- Location permission will be requested on first run

## API Integration

The app connects to your Plotra backend at `/api/v2`:

### Endpoints Used
- `POST /api/v2/auth/token` - Login
- `GET /api/v2/auth/me` - Get current user
- `GET /api/v2/farmer/farm` - Get user's farms
- `GET /api/v2/capture/farms/{id}/parcels` - Get farm parcels
- `POST /api/v2/capture/capture` - Submit GPS capture + analysis

### Authentication
- JWT tokens stored securely in Expo SecureStore
- Tokens auto-refresh on 401 errors
- User session persists across app launches

## App Flow

```
Login/Register
     ↓
Farm List (user's farms only)
     ↓
Parcel Selection (optional - can skip)
     ↓
GPS Capture Screen
  - Real-time GPS accuracy
  - Location coordinates
  - Add field notes
     ↓
Submit → Backend Analysis
     ↓
Results Screen
  - Compliance status
  - Risk score %
  - Recommendations
```

## Configuration

### Backend URL
- **Development:** `http://10.0.2.2:8000/api/v2` (Android emulator) or `http://localhost:8000/api/v2` (Expo Go)
- **Physical device:** Your computer's LAN IP, e.g., `http://192.168.1.x:8000/api/v2`
- **Production:** Full domain with HTTPS

### GPS Accuracy Settings
Adjust in `src/config/index.js`:
- `GPS_ACCURACY_THRESHOLD` - Green/red indicator threshold (default 10m)
- `MIN_ACCURACY_FOR_CAPTURE` - Warning threshold (default 30m)

## File Structure

```
plotra_capture_app/
├── App.js                    # Main app entry
├── package.json              # Dependencies
├── app.json                  # Expo config
├── babel.config.js           # Babel config
├── __DEV__.gitignore         # Git ignore
├── src/
│   ├── config/               # Environment config
│   ├── context/              # Auth context
│   ├── navigation/           # App navigator
│   ├── screens/              # UI screens
│   │   ├── LoginScreen.js
│   │   ├── RegisterScreen.js
│   │   ├── FarmListScreen.js
│   │   ├── ParcelSelectionScreen.js
│   │   └── CaptureScreen.js
│   ├── services/             # API layer
│   │   └── api.js
│   └── components/           # Reusable UI
└── assets/                   # Images (add icon.png, splash.png)
```

## Security Notes

- **JWT tokens** stored in secure storage (encrypted on device)
- **HTTPS required** in production (configure backend with SSL)
- **Location permission** only requested when needed
- **No sensitive data** logged or cached

## Troubleshooting

### GPS not working on emulator
- Use physical device or mock location in emulator settings
- Emulators often return 0m accuracy

### "Network request failed"
- Check backend CORS allows your dev URL: `http://localhost:8000`
- Ensure backend is running on correct port
- For physical device, use LAN IP not localhost

### Build fails with EAS
- Ensure `eas-cli` is logged in
- Check `eas.json` build profile
- Review build logs on Expo dashboard

### "Permission denied" for location
- Android: Check app permissions in Settings
- iOS: Add location usage description to `app.json`

## Customization

- **Colors:** Update style constants in screen files (primary: `#6f4e37`)
- **API endpoints:** Modify in `src/services/api.js`
- **UI layout:** Edit screens in `src/screens/`

## Future Enhancements

- Offline capture queue with sync
- Photo capture integration
- Batch capture mode
- Map view with parcel overlays
- Dark mode support

---

**Questions?** Contact the Plotra dev team or open an issue in the repository.
