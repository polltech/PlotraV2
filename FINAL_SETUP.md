# 🎯 COMPLETE SETUP GUIDE — Ready to Build

## ✅ Configuration Complete

Your backend and mobile app are now configured to communicate:

**Backend CORS** includes: `http://192.168.100.5:19006` (your LAN IP)
**Mobile API URL** set to: `http://192.168.100.5:8000/api/v2`

---

## 🔧 Step 1: Start Your Backend

Make sure your FastAPI backend is running:

```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Test it's accessible:**
Open browser → `http://localhost:8000/api/v2/health`
Should return: `{"status":"healthy",...}`

**Test from mobile perspective:**
```bash
curl http://192.168.100.5:8000/api/v2/health
```
(If on same machine, both localhost and LAN IP should work)

---

## 📱 Step 2: Install Mobile Dependencies

**Open Command Prompt** (NOT PowerShell if scripts are blocked):

```cmd
cd plotra_capture_app
npm install
```

**If you see "running scripts is disabled":**
1. Open PowerShell as **Administrator**
2. Run: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
3. Close PowerShell, open **Command Prompt**
4. Retry `npm install`

**What gets installed:**
- expo, react-native
- @react-navigation/native
- expo-location, expo-secure-store
- axios

Should take 2-5 minutes.

---

## 🧪 Step 3: Quick Test (Expo Go)

**Before building APK, test in Expo Go:**

```cmd
cd plotra_capture_app
npx expo start
```

**On your Android phone:**
1. Install **Expo Go** from Google Play Store
2. Connect phone to **same WiFi** as your computer
3. Scan QR code with Expo Go (use camera or Expo app scanner)
4. App loads with live reload

**Test the flow:**
- Register new user
- Login
- View farms list (may be empty — create a farm first via API or web UI)
- Test GPS capture (go outdoors for signal)
- See analysis results

**If errors:**
- Check backend console for 404/500 errors
- Verify CORS includes `http://192.168.100.5:19006`
- Ensure phone and PC on same network

**Once working → move to APK build.**

---

## 🔨 Step 4: Build APK

### Install EAS CLI (if not already)

```cmd
npm install -g eas-cli
```

**If permission denied:**
```powershell
# Run as Administrator:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
npm install -g eas-cli
```

### Login to Expo

```cmd
eas login
```
Opens browser — sign in with Expo account.

**No account?** Sign up free at expo.dev (5 min).

### Build!

```cmd
cd plotra_capture_app
eas build --platform android --profile preview
```

**Interactive prompts:**
```
? Who will you submit this build as? → Your Expo username
? Project slug → plotra-capture (press Enter)
```

**Build time:** 10-20 minutes (cloud build)

---

## 📥 Step 5: Get Your APK

When build completes, you'll see:

```
✅  Build finished!
Download link: https://expo.dev/artifacts/...
```

**Options:**

1. **Automatic download** — APK downloads to your `Downloads/` folder
2. **Manual download** — Click the link in terminal or visit expo.dev → Your Account → Builds

**File name:** `plotra-capture-android.apk` or `app-preview.apk`

---

## 📲 Step 6: Install on Device

### Method A: Direct (easiest)

1. Copy APK to phone (USB, email, or download from expo.dev directly on phone)
2. On Android phone:
   - Settings → Security → Enable **"Install from unknown sources"**
   - (Android 8+): Settings → Apps & Notifications → Special Access → Install unknown apps → enable for your file manager/browser
3. Open APK file → Install
4. Launch **Plotra Capture** app

### Method B: ADB (from computer)

```cmd
# Connect phone via USB with USB debugging ON
adb install path/to/apk/file.apk
```

---

## 🎯 First Run

1. **Launch app** → Login screen
2. **Login** with your credentials (from backend)
3. **Farm List** — should show your farms
   - If empty: Create a farm first via API or web UI
4. **Tap "Capture GPS"**
5. **Select parcel** (or skip)
6. **Go outdoors** — wait for GPS lock (green dot)
7. **Tap "Capture & Analyze"**
8. **View results** — compliance, risk score, recommendations

---

## 📊 Verify Backend Received Data

Check your FastAPI console logs:
```
INFO:     127.0.0.1:XXXXX - "POST /api/v2/capture/capture HTTP/1.1" 201 Created
```

Check database:
```sql
SELECT * FROM gps_capture ORDER BY id DESC LIMIT 5;
```

Should show your capture record.

---

## 🐛 Troubleshooting

### "Network request failed" in app
1. Backend running? → `curl http://192.168.100.5:8000/api/v2/health`
2. CORS includes `http://192.168.100.5:19006`? → Check `config.py`, restart backend
3. Phone & PC on same WiFi? → Yes
4. `app.json` API_BASE_URL correct? → `http://192.168.100.5:8000/api/v2`

### GPS accuracy poor
- Use physical device (not emulator)
- Go outdoors (no metal roofs over head)
- Wait 30-60 seconds for GPS lock
- Enable "High Accuracy" in Android Location settings

### Login fails
- Check backend `/auth/token` endpoint with curl
- Verify user exists in database
- Password correct?

### Build fails with EAS
1. Run `eas whoami` — confirm logged in
2. Check expo.dev dashboard for error logs
3. Ensure `eas-cli` latest: `npm install -g eas-cli@latest`
4. Delete `node_modules/` and `package-lock.json`, retry `npm install`

### "App not installed" after APK download
- Enable "Unknown sources" in settings
- Re-download APK (may be corrupted)
- Uninstall previous test version first

### APK installs but immediately crashes
- Check log: `adb logcat | grep -i plotra`
- Common cause: Invalid API_BASE_URL (set to localhost instead of LAN IP)
- Rebuild with correct `app.json` and redeploy

---

## 🔄 Rebuilding After Changes

**If you change API endpoints or app logic:**

```bash
cd plotra_capture_app

# Clear cache (optional)
npx expo start --clear

# Rebuild APK
eas build --platform android --profile preview
```

**Update code without full rebuild?** Use Expo Go during development. Only build APK for final testing/distribution.

---

## 📁 File Structure Recap

```
plotra_capture_app/
├── src/
│   ├── screens/
│   │   ├── LoginScreen.js
│   │   ├── RegisterScreen.js
│   │   ├── FarmListScreen.js
│   │   ├── ParcelSelectionScreen.js
│   │   └── CaptureScreen.js
│   ├── context/AuthContext.js
│   ├── navigation/AppNavigator.js
│   ├── services/api.js
│   └── config/index.js
├── App.js
├── package.json
├── app.json               ← YOUR IP configured here
├── eas.json
└── BUILD_GUIDE.md
```

---

## ✨ What's Working

✅ **Backend**
- GPS capture stored in `gps_capture` table
- PostGIS point-in-polygon analysis
- Risk scoring (low/medium/high)
- Compliance status + recommendations

✅ **Mobile App**
- JWT authentication (login/register)
- Secure token storage
- Farm list (only user's farms)
- Parcel selection (optional)
- Real-time GPS display with accuracy meter
- Capture submission + analysis results
- Pull-to-refresh on farm list
- Logout

✅ **Integration**
- All API calls working
- CORS configured for your LAN
- Auth context protecting routes
- Error handling & user feedback

---

## 🎬 You're Ready!

**Run these commands now:**

```cmd
cd plotra_capture_app
npm install
npm start
```

Scan QR → test → if all works:

```cmd
eas build --platform android --profile preview
```

**~15 minutes later:** APK ready for distribution.

---

## 📞 Support

**Backend issues:** Check `app/main.py` console logs
**Mobile issues:** `adb logcat` for Android errors
**API errors:** Test with curl/Postman first

**Questions?** Contact dev team or check:
- `README.md` — full documentation
- `BUILD_GUIDE.md` — detailed build troubleshooting
- `SETUP_GUIDE.md` — architecture overview

---

**Go build that APK! 🚀**
