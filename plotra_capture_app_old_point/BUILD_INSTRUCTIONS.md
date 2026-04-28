# Plotra Capture App - APK Build Instructions

## **IMPORTANT: Read Before Building**

The APK build has **two phases**:
1. **Development build** (Expo Go) - quick test
2. **Production APK** (standalone) - for distribution

---

## Phase 1: Quick Test (No Build Required)

### Option A: Expo Go (Fastest - 5 min)
```bash
cd plotra_capture_app
npm install
npm start
```
1. Install **Expo Go** app on your Android phone from Play Store
2. Scan QR code withExpo Go
3. App runs live with hot reload

**Pros:** Instant, no build time  
**Cons:** Requires Expo Go app, slower performance

### Option B: Development Build (Standalone debug APK)
```bash
cd plotra_capture_app
npx expo run:android
```
Generates debug APK at: `android/app/build/outputs/apk/debug/`

**Pros:** Real APK, no Expo Go needed  
**Cons:** Debug version, not signed for release

---

## Phase 2: Production APK (Cloud Build - Recommended for Distribution)

### Prerequisites Checklist

- [ ] Node.js 18+ installed
- [ ] Expo account created (https://expo.dev/signup)
- [ ] Backend server is **publicly accessible** (not localhost) for cloud build
- [ ] `app.json` has correct `API_BASE_URL` with public domain
- [ ] EAS CLI installed: `npm install -g eas-cli`
- [ ] Logged in: `eas login`

### Step-by-Step Build

#### Step 1: Update Backend URL in `app.json`

**For local network testing (same WiFi):**
```json
"extra": {
  "API_BASE_URL": "http://192.168.1.100:8000/api/v2"
}
```
Replace `192.168.1.100` with your computer's LAN IP.

**Get your LAN IP:**
- **Windows:** `ipconfig` → look for "IPv4 Address"
- **Mac/Linux:** `ifconfig` or `ip addr`

**For production/cloud build:**
```json
"extra": {
  "API_BASE_URL": "https://api.yourdomain.com/api/v2"
}
```

#### Step 2: Update Backend CORS

Your backend must accept requests from the mobile app. In `app/core/config.py`, add your mobile dev IP:

```python
class CORSConfig(BaseModel):
    allowed_origins: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:19006",          # Expo dev
        "http://192.168.1.100:19006",      # YOUR LAN IP HERE
        "http://10.0.2.2:19006",           # Android emulator
    ]
```

Restart backend after changes.

#### Step 3: Install Dependencies

**IMPORTANT:** Run this in **Command Prompt** or **Git Bash** (not PowerShell if scripts are blocked).

```bash
cd plotra_capture_app
npm install
```

If you get permission errors, run as Administrator or use:
```bash
# Windows: Use cmd.exe or Git Bash
# Mac/Linux: sudo npm install -g eas-cli (for global installs)
```

#### Step 4: Login to EAS

```bash
eas login
```
Opens browser for OAuth login.

#### Step 5: Build APK

```bash
cd plotra_capture_app
eas build --platform android --profile preview
```

**What happens:**
1. Source code zipped and uploaded to Expo
2. Expo cloud builder creates native Android project
3. Downloads dependencies, compiles, signs APK
4. Takes ~10-20 minutes
5. Download link appears in terminal & expo.dev dashboard

**APK size:** ~15-25 MB

#### Step 6: Download & Install

1. Go to https://expo.dev/accounts/
2. Open your account → Builds
3. Download the `.apk` file
4. On Android device:
   - Settings → Security → Enable "Install from unknown sources"
   - Open APK file → Install
5. Launch app and test

---

## Troubleshooting Build Issues

### "npm command not recognized"
- Node.js not installed or not in PATH
- Reinstall Node.js from https://nodejs.org/ (check "Add to PATH")

### "eas: command not found"
```bash
npm install -g eas-cli
# May need sudo on Mac/Linux
```

### "Cannot find module 'expo'"
```bash
cd plotra_capture_app
npm install
```

### Build fails with "gradle" errors
- Ensure `JAVA_HOME` set (Android SDK)
- Or use EAS cloud build (handles everything)

### "Backend URL not accessible"
During cloud build, Expo's servers need to reach your backend. If using `localhost`, it will fail.

**Solution:**
1. For testing: Use LAN IP and install via Expo Go (Phase 1)
2. For distribution: Deploy backend to public server (VPS/cloud)

### CORS errors in app
Check:
1. Backend `config.py` includes mobile dev URL
2. Backend restart after config change
3. No firewall blocking port 8000

Test with curl:
```bash
curl http://192.168.1.100:8000/api/v2/health
```

### APK install fails "App not installed"
- Enable "Unknown sources" in Android settings
- Ensure enough storage
- Check APK not corrupted (re-download)

### GPS not working in emulator
Emulators don't have real GPS. Use:
- Physical device with Expo Go
- Or mock location in emulator settings

---

## Build Profiles Explained

### `preview` profile (debug APK)
```bash
eas build --platform android --profile preview
```
- Unsigned debug build
- For testing only
- Faster build time

### `production` profile (release AAB for Play Store)
```bash
eas build --platform android --profile production
```
- Signed with your keystore
- Ready for Google Play Store
- Requires keystore configuration

**First production build:**
EAS will prompt to:
1. Create new keystore (auto-generated)
2. Set app version code
3. Add release notes

---

## Alternative: Local Gradle Build (No EAS)

If you prefer local builds without EAS:

```bash
cd plotra_capture_app

# Generate native Android project
npx expo prebuild

# Opens Android Studio - from there:
# 1. Build → Generate Signed Bundle/APK
# 2. Choose APK
# 3. Create keystore or use existing
# 4. Select release build
# 5. APK saved to: android/app/build/outputs/apk/release/
```

**Requires:** Android Studio installed, JAVA_HOME set, Android SDK

---

## Quick Commands Reference

```bash
# Development (Expo Go)
cd plotra_capture_app && npm install && npm start

# Development (Local APK)
npx expo run:android

# Cloud Build (Preview APK)
eas build --platform android --profile preview

# Cloud Build (Production AAB)
eas build --platform android --profile production

# View build status
eas build:list

# Download APK (replace with your build ID)
eas build:download --id <build-id> --platform android
```

---

## Before First Production Build

- [ ] Update `app.json`:
  - `version`: bump (e.g., "1.0.1")
  - `versionCode`: increment in Android config (or EAS auto-increments)
- [ ] Replace placeholder assets in `assets/` folder
- [ ] Test thoroughly with production backend
- [ ] Configure Google Play Store listing
- [ ] Set up app signing (Google Play App Signing recommended)

---

## Need Help?

- **EASDocs:** https://docs.expo.dev/build/introduction/
- **Expo Forums:** https://forums.expo.dev/
- **FastAPI logs:** Check `uvicorn` console for API errors
- **Mobile logs:** `adb logcat *:E` for Android errors

---

**Ready?** Start with the quick test:

```bash
cd plotra_capture_app
npm install
npm start
```

Then scan QR with Expo Go to verify everything works before committing to a 15-minute cloud build.
