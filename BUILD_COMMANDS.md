# 🚀 APK BUILD - EXACT COMMANDS TO RUN

## **Your Configuration**
- Backend IP: `192.168.100.5:8000`
- Mobile app folder: `plotra_capture_app/`
- CORS already updated in backend
- `app.json` already configured with your IP

---

## 📋 Step-by-Step Commands

### **Step 1: Terminal — Command Prompt (NOT PowerShell)**

Open **Command Prompt** (cmd.exe) — Start → "cmd" → Run as Administrator

**Why CMD?** PowerShell often blocks npm scripts. CMD works reliably.

### **Step 2: Navigate to mobile app**

```cmd
cd /d G:\My Drive\plotra\plotra_capture_app
```

### **Step 3: Install dependencies**

```cmd
npm install
```

**What you'll see:** Lots of `added X packages` messages.
**Time:** 2-5 minutes.

**If you get errors:**
- "EACCES" or permission denied → Run CMD as Administrator
- "running scripts disabled" → Use CMD not PowerShell
- Network timeout → Check internet, retry

### **Step 4: Test with Expo Go (optional but recommended)**

```cmd
npx expo start
```

**On your Android phone:**
1. Install **Expo Go** from Play Store (if not already)
2. Connect phone to **same WiFi** as PC
3. Scan QR code with Expo Go
4. Wait for app to load
5. **Test:** Register → Login → View farms → Try GPS capture (go outside)

**If this works → proceed to APK build.**

**If fails:** Check:
- Backend is running? (`uvicorn main:app --reload`)
- Phone and PC on same network?
- `app.json` has correct IP (192.168.100.5)?
- CORS includes `http://192.168.100.5:19006`?
- Windows Firewall allowing port 8000? Temporarily disable for test

### **Step 5: Install EAS CLI (one-time)**

```cmd
npm install -g eas-cli
```

**If permission denied:** Run CMD as Administrator, then retry.

### **Step 6: Login to Expo**

```cmd
eas login
```

Browser opens → Sign in with Expo account (free at expo.dev).

**No account?** Sign up now — takes 2 minutes.

### **Step 7: Build APK (cloud build)**

```cmd
eas build --platform android --profile preview
```

**First time?** You'll see prompts:

```
? Who will you submit this build as? [your-username]
? Project slug [plotra-capture]
```

Just press Enter for defaults.

**Build starts:** Uploads code to Expo, builds in cloud.
**Watch progress:** https://expo.dev/accounts/

**Time:** 10-20 minutes.

### **Step 8: Download APK**

When build completes, terminal shows:

```
✅  Build finished!
Download link: https://expo.dev/artifacts/...
```

**Copy that link → open in browser → download .apk file**

Or manually:
1. Go to https://expo.dev/accounts/
2. Your profile → Builds
3. Find "plotra-capture" build
4. Click "Download APK"

APK saved as: `plotra-capture-android.apk` (or `app-preview.apk`)

---

## 📲 Install APK on Phone

### **Method A: Easiest**
1. On phone, open the expo.dev build page (login)
2. Tap "Download APK"
3. After download, open "Downloads" → tap APK → Install
4. Enable "Unknown sources" if prompted (Settings → Security)

### **Method B: From PC**
1. Copy APK from PC to phone (USB cable)
2. On phone, open file manager → tap APK → Install

### **Method C: ADB (advanced)**
```cmd
adb install path/to/plotra-capture-android.apk
```

---

## 🎯 First Launch

1. **Open app** — See login screen
2. **Login** with your credentials (from backend)
3. **Farm list** — Should show your farms
   - Empty? → Need to create a farm first (via web UI or API)
4. **Tap "Capture GPS"** on any farm
5. **Parcel selection** — Choose parcel or Skip
6. **Go outdoors** — Wait for GPS (green accuracy dot)
7. **Tap "Capture & Analyze"**
8. **View results** — Compliance status, risk score, recommendations

---

## ✅ Verification Checklist

Before building, confirm:

- [x] Backend running (`uvicorn` terminal shows requests)
- [x] Backend health: `http://192.168.100.5:8000/api/v2/health` returns JSON
- [x] `plotra_capture_app/app.json` has `"API_BASE_URL": "http://192.168.100.5:8000/api/v2"`
- [x] Backend CORS in `config.py` includes `http://192.168.100.5:19006`
- [x] EAS CLI installed (`eas --version` works)
- [x] You have Expo account (free)
- [x] Android phone ready for testing

---

## 🐛 If Build Fails

### "npm: command not recognized"
- Node.js not installed correctly
- Reinstall from https://nodejs.org/ (check "Add to PATH")

### "eas: command not found"
```cmd
npm install -g eas-cli
```
Run as Administrator if needed.

### "Network request failed" during npm install
- Check internet connection
- Use different network
- Or use VPN if behind firewall

### "Build failed" on EAS
1. Visit https://expo.dev/accounts/ → your builds
2. Click failed build → View logs
3. Look for red error lines
4. Common fixes:
   - Invalid API_BASE_URL (uses localhost) → Update app.json
   - Backend unreachable from cloud → Use LAN IP only for Expo Go, public URL for EAS

**Note:** EAS cloud builders cannot reach `localhost` or LAN IPs. Your backend must be publicly accessible for EAS builds.

**For local testing only:** Use Expo Go (which runs on your device, same network).

---

## 🔄 Development Workflow (Fast)

During development, **don't rebuild APK each time**. Use:

```cmd
cd plotra_capture_app
npx expo start
```

→ Scan QR → changes reflect instantly (fast refresh).

Only build APK for:
- Final testing on device without Expo Go
- Distribution to other users
- Publishing to Play Store

---

## 📊 What Gets Built

**APK size:** ~15-25 MB
**Includes:**
- React Native runtime
- Expo modules (location, secure-store)
- Your JavaScript code bundles
- Native Android manifest with permissions

**What's NOT included (downloaded at runtime):**
- Google Play Services (if needed for GPS)

---

## 🎨 Customization (Before Build)

Optional — customize before first build:

**App name/icon:**
Edit `app.json`:
```json
{
  "expo": {
    "name": "Plotra Capture Pro",  // Change name
    "slug": "plotra-capture-pro",
    "icon": "./assets/icon.png"   // Add custom icon (1024x1024)
  }
}
```

**Version:**
```json
"version": "1.0.1"
```

**Android versionCode:** Increment for Play Store updates:
```json
"android": {
  "versionCode": 2
}
```

---

## 📁 Build Output Locations

- **EAS cloud build:** Download from expo.dev dashboard
- **Local debug:** `android/app/build/outputs/apk/debug/`
- **Local release:** `android/app/build/outputs/apk/release/`

---

## 🎬 Ready to Build?

**Run these EXACT commands now:**

```cmd
REM 1. Open Command Prompt as Administrator
REM 2. Navigate to app folder
cd /d G:\My Drive\plotra\plotra_capture_app

REM 3. Install dependencies
npm install

REM 4. Start Expo (test first)
npx expo start
REM Scan QR with Expo Go → verify it works
REM Press Ctrl+C to stop Expo

REM 5. Install EAS CLI (if not done)
npm install -g eas-cli

REM 6. Login to Expo
eas login

REM 7. BUILD APK!
eas build --platform android --profile preview
```

**Wait 10-20 minutes. Download APK. Install. Done!**

---

**Questions?** Check `BUILD_GUIDE.md` or `README.md` in the app folder.
