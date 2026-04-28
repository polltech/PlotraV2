# Plotra Capture App - Complete Build Guide

## 📦 What You Have

**Backend APIs** (already running on your server):
- `POST /api/v2/auth/token` — Login
- `GET /api/v2/farmer/farm` — Get user's farms (auth required)
- `GET /api/v2/capture/farms` — Get all farms for selection
- `GET /api/v2/capture/farms/{id}/parcels` — Get farm parcels
- `POST /api/v2/capture/capture` — Submit GPS + instant analysis
- `GET /api/v2/capture/capture/{id}` — Retrieve capture

**Mobile App** (`plotra_capture_app/`):
- React Native + Expo
- Full auth flow (login/register)
- Farm listing (user's farms only)
- GPS capture with analysis display

---

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies

Open **Command Prompt** or **PowerShell** (as Administrator if needed):

```cmd
cd plotra_capture_app
npm install
```

**If npm fails with "running scripts disabled":**
```powershell
# Run PowerShell as Administrator, then:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# Then retry npm install
```

### Step 2: Configure Backend URL

Edit `plotra_capture_app\app.json` in a text editor:

Find line 39:
```json
"API_BASE_URL": "http://192.168.1.100:8000/api/v2"
```

**Change `192.168.1.100` to your PC's LAN IP address:**

**Windows:**
1. Open Command Prompt
2. Type `ipconfig`
3. Find "IPv4 Address" (usually `192.168.1.x` or `10.0.0.x`)
4. Use that IP in `app.json`

Example:
```json
"API_BASE_URL": "http://192.168.1.105:8000/api/v2"
```

**Save file.**

### Step 3: Update Backend CORS

In your backend `app/core/config.py`, add your mobile dev IP:

```python
class CORSConfig(BaseModel):
    allowed_origins: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://192.168.1.105:19006",   # ← ADD YOUR IP HERE
        "http://10.0.2.2:19006",        # Android emulator
    ]
```

Restart your FastAPI backend:
```bash
# If using uvicorn:
Ctrl+C to stop, then:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📱 Test Before Building APK

### Run with Expo Go (Live Development)

```bash
cd plotra_capture_app
npx expo start
```

**On your Android phone:**
1. Install **Expo Go** from Play Store
2. Connect phone to **same WiFi** as your computer
3. Scan QR code with Expo Go app
4. App launches with live reload

**Emulator:**
```bash
npx expo run:android
```
(Requires Android Studio)

**Test the flow:**
1. Register a new account
2. Login
3. Should see your farms (from backend)
4. Tap "Capture GPS" → Select parcel (or skip)
5. Go outdoors, wait for GPS lock (green accuracy)
6. Tap "Capture & Analyze"
7. See analysis results with risk score and recommendations

If it works → proceed to build APK.

---

## 🔨 Build APK

### Option A: EAS Cloud Build (Recommended)

EAS builds in the cloud — no Android Studio required.

#### Install EAS CLI

```bash
npm install -g eas-cli
```

**If permission denied:**
```powershell
# Run PowerShell as Administrator, then:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
npm install -g eas-cli
```

#### Login to Expo

```bash
eas login
```
Browser opens — log in with your Expo account.

**Don't have an account?** Sign up free at https://expo.dev

#### Build APK

```bash
cd plotra_capture_app
eas build --platform android --profile preview
```

**What you'll see:**
```
? Who will you submit this build as? → Select your username
? Project slug → plotra-capture
✓ Build initialized
```

**Build progress:** View at https://expo.dev/accounts/

**Time:** 10-20 minutes

**When complete:**
- Terminal shows: `✅  Download link: https://expo.dev/artifacts/...`
- APK downloaded automatically (or click link)

**APK location:** `plotra_capture_app/android/app/build/outputs/apk/release/` (if using local build)

---

### Option B: Local Build with Android Studio

If you have Android Studio installed:

```bash
cd plotra_capture_app

# Generate native Android project
npx expo prebuild

# Opens a prompt to install expo-device
# Say yes

# Then open in Android Studio:
# File → Open → Select the 'android' folder

# In Android Studio:
# Build → Generate Signed Bundle / APK
# Choose APK
# Create new keystore (or use existing)
# Select release build type
# Finish wizard
```

APK saved to: `android/app/build/outputs/apk/release/`

**Note:** Local builds require Android SDK, JAVA_HOME configured.

---

## 📋 Build Configuration Files

### `eas.json` — Build Profiles

Already created for you:
```json
{
  "build": {
    "development": { "developmentClient": true, "distribution": "internal" },
    "preview": { "android": { "buildType": "apk" } },
    "production": { "android": { "buildType": "app-bundle" } }
  }
}
```

- `preview` → Debug APK (test on device)
- `production` → Signed AAB for Google Play Store

### `app.json` — App Configuration

Already includes:
- Package name: `africa.plotra.capture`
- Location permissions
- API URL in `extra` field

---

## 🎯 Full Build Command Cheat Sheet

```bash
# 1. DEVELOPMENT — Live test with Expo Go (no build)
cd plotra_capture_app
npm install
npm start
# Scan QR → done

# 2. DEBUG APK — Local build
npx expo run:android

# 3. RELEASE APK — EAS cloud build
npx expo prebuild  # Only needed once for native code
eas build --platform android --profile preview

# 4. PRODUCTION AAB — For Play Store
eas build --platform android --profile production

# View all builds
eas build:list

# Download specific build
eas build:download --id <build-id> --platform android
```

---

## 🔧 Troubleshooting Builds

### "eas: command not found"
```bash
npm install -g eas-cli
```

### "Cannot find module 'expo'"
```bash
cd plotra_capture_app
npm install
```

### Build fails: "Network request failed" (during install)
- Check internet connection
- Use different npm registry: `npm config set registry https://registry.npmjs.org/`

### "You need to install Android Studio"
- Use EAS cloud build instead (no local SDK needed)
- Or install Android Studio: https://developer.android.com/studio

### "No APK downloaded automatically"
Manual download from expo.dev:
1. Go to https://expo.dev/accounts/
2. Your account → Builds
3. Find build → Download APK

### APK install fails "App not installed"
1. Enable **Settings → Security → Unknown sources**
2. Re-download APK (corrupted download)
3. Check storage space
4. Uninstall previous version first

### GPS doesn't work on device
- Test with Expo Go first (`npm start`) — GPS works there?
- Ensure location permission granted (Android Settings → Apps → Plotra Capture → Permissions)
- Use device with GPS hardware (not emulator)

### API calls fail with "Network Error"
1. Verify backend is running: `curl http://YOUR-IP:8000/api/v2/health`
2. Check `app.json` `API_BASE_URL` uses correct IP
3. Ensure CORS includes mobile dev URL
4. Phone and computer on **same WiFi network**
5. Disable firewall temporarily for testing

---

## 📲 Install APK on Device

### Method 1: Direct Install
1. Copy APK to phone (USB, email, or download from expo.dev)
2. On phone: Settings → Security → Enable "Install from unknown sources"
3. Open APK file → Install
4. Open app → Login → Test

### Method 2: Using ADB (from computer)
```bash
# Connect phone via USB with USB debugging enabled
adb install plotra_capture_app/android/app/build/outputs/apk/debug/app-debug.apk
```

---

## 🎨 Customize the App

### Change App Name/Icon
Edit `app.json`:
```json
{
  "expo": {
    "name": "Plotra Capture",
    "slug": "plotra-capture",
    "icon": "./assets/my-icon.png"
  }
}
```

### Change Primary Color
Screens use `#6f4e37` (brown). Update in each `styles.js` file.

### Add More Fields to Capture
Edit `src/screens/CaptureScreen.js` and `src/services/api.js`.

---

## ✅ Pre-Build Checklist

- [ ] Dependencies installed (`npm install` complete)
- [ ] `app.json` API_BASE_URL updated to your LAN IP or public domain
- [ ] Backend CORS includes mobile dev URL
- [ ] Backend is running and reachable from mobile device
- [ ] Tested with Expo Go (`npm start`) successfully
- [ ] EAS CLI installed (`eas --version`)
- [ ] Logged in to EAS (`eas login`)
- [ ] App icons added to `assets/` folder (optional)

---

## 🎉 After Build

**APK file is ready!**

Distribute via:
- Google Play Store (requires `production` AAB build)
- Internal testing (send APK directly)
- Email/cloud storage download link

---

## 📚 Additional Resources

- **Expo Docs:** https://docs.expo.dev/
- **EAS Build:** https://docs.expo.dev/build/introduction/
- **React Native:** https://reactnative.dev/
- **Plotra Backend API:** See `CAPTURE_APP_SUMMARY.md`

---

**Need help?** Check the logs:
- Backend: Terminal running `uvicorn`
- Mobile: `adb logcat | grep -i expo` (Android)

**Start now:**
```bash
cd plotra_capture_app
npm install
npm start
```
