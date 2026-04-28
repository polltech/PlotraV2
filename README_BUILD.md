# 📦 Plotra Capture App — Ready to Build

## 📍 Current Configuration

✅ **Backend CORS** includes: `http://192.168.100.5:19006` (mobile dev)
✅ **Mobile API URL** set: `http://192.168.100.5:8000/api/v2`
✅ **GPS capture API** implemented with analysis
✅ **Authentication** working (JWT)

---

## 🎯 What to Do Now (3 Minutes)

### **Option A: Quick Test First (Recommended)**

**1. Start your backend** (if not already running):

```cmd
cd G:\My Drive\plotra\app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**2. Open new CMD window, test the app:**

```cmd
cd G:\My Drive\plotra\plotra_capture_app
npm install
npx expo start
```

**3. On phone:**
- Install **Expo Go** (Play Store)
- Scan QR code from terminal
- Test: Register → Login → Capture GPS

**If working → Build APK (Step 4).**

---

### **Option B: Build Directly (if you're confident)**

```cmd
REM 1. Open Command Prompt as Administrator
REM 2. Navigate to app:
cd /d G:\My Drive\plotra\plotra_capture_app

REM 3. Install dependencies:
npm install

REM 4. Install EAS CLI (first time only):
npm install -g eas-cli

REM 5. Login to Expo:
eas login

REM 6. Build APK:
eas build --platform android --profile preview
```

**Get APK:** Check terminal for download link or visit https://expo.dev/accounts/

---

## 🔧 Important Notes

### Backend Must Be Accessible During Build

**EAS cloud build** runs on Expo's servers — they need to reach your backend API to bundle it. But actually, the mobile app code doesn't call the backend at build time; it only needs the API URL. So **public access is NOT required for build**, only for running the app.

**However:** If your backend is `localhost`, the app will fail on device. That's why we set it to your LAN IP (`192.168.100.5`). Works on same WiFi.

**For distro** (Google Play): You'll need a **public backend URL** (domain + HTTPS).
Update `app.json` before production build:
```json
"extra": {
  "API_BASE_URL": "https://api.plotra.africa/api/v2"
}
```

---

### CORS Configuration

Already updated in `app/core/config.py`:

```python
"CORS allowed_origins": [
    "http://192.168.100.5:19006",  # ← mobile dev
    ...
]
```

**If you change LAN IP**, update both:
1. `plotra_capture_app/app.json` — `API_BASE_URL`
2. `app/core/config.py` — CORS allowed_origins

Then restart backend.

---

### If `npm install` Fails

**PowerShell error "running scripts disabled":**
1. Close PowerShell
2. Open **Command Prompt** (cmd.exe)
3. Run `npm install` there

**Or fix PowerShell permanently** (Admin PowerShell):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

### If `eas build` Fails

**Common fixes:**

1. **"Not logged in"** → `eas login`
2. **"Project not found"** → Use `eas build` (not `--project`), let it prompt
3. **"Bundle failed"** → Ensure `app.json` is valid JSON (no trailing commas)
4. **"Gradle error"** → EAS handles this; check build log on expo.dev

**View detailed logs:**
- Terminal output
- expo.dev → Your Account → Builds → (failed build) → View Logs

---

## 📱 Testing the APK

After installing:

1. **Launch app** → Login
2. **Check farm list** — Should show your farms from backend
3. **Tap "Capture GPS"** → Select parcel → Capture
4. **Verify analysis** — Risk score, status, recommendations appear
5. **Check backend** — New row in `gps_capture` table

```sql
SELECT * FROM gps_capture ORDER BY id DESC LIMIT 1;
```

---

## 📂 Files Created

```
plotra_capture_app/
├── src/
│   ├── screens/          (5 screens)
│   ├── context/          (AuthContext)
│   ├── navigation/       (AppNavigator)
│   ├── services/         (api.js)
│   └── config/           (config)
├── package.json          (dependencies)
├── app.json              (Expo config + API URL)
├── eas.json              (build profiles)
├── build.bat             (Windows build script)
├── BUILD_GUIDE.md        (detailed guide)
├── QUICKSTART.md
└── README.md

Backend:
├── app/models/gps.py           ← New GPS capture model
├── app/api/v2/capture.py       ← New capture endpoints
├── app/api/schemas.py          ← New schemas
└── app/core/config.py          ← CORS updated
```

---

## 🎨 Customization Before Build

**App name:** Edit `app.json` → `"name": "Plotra Capture"`
**Bundle ID:** `"package": "africa.plotra.capture"` (change if needed)
**Version:** `"version": "1.0.0"` (bump for Play Store)
**Icons:** Add PNG files to `assets/` folder (icon.png, splash.png)

Defaults are fine for testing.

---

## 🚀 Distribution Options

### **1. Direct APK Share**
- Send APK via email/WhatsApp/Telegram
- Users enable "Unknown sources" → Install
- Best for internal testing (max 100 installs/day)

### **2. Google Play Store**
- Requires **AAB** (not APK)
- Account fee: $25 one-time
- Review process: few hours to days
- Build AAB: `eas build --platform android --profile production`

### **3. Internal Testing Track**
- Upload APK to Play Console → Internal testing
- Up to 100 testers
- Faster rollout

---

## 🐛 Emergency Fixes

### "Network request failed" at runtime
→ CORS issue. Ensure `API_BASE_URL` is **not** `localhost`. Use your LAN IP.

### "GPS accuracy poor"
→ Use physical device outdoors. Emulator GPS is simulated and inaccurate.

### "Login failed"
→ Backend `/auth/token` must work. Test with curl:
```bash
curl -X POST http://192.168.100.5:8000/api/v2/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"test@plotra.africa","password":"secret"}'
```

### "Farm list empty"
→ No farms in DB for that user. Create farm via:
- Web UI (if you have one)
- Or API: `POST /api/v2/farmer/farm` with auth
- Or seed database

---

## 🎯 Success Criteria

✅ **APK builds** on EAS (no errors)
✅ **APK downloads** from expo.dev
✅ **APK installs** on Android device
✅ **App launches** → Login screen appears
✅ **Login works** → Token stored
✅ **Farms load** (even if empty)
✅ **GPS capture** → Analysis returned

If all above pass → **mission accomplished!** 🎉

---

## 📞 Emergency Commands Reference

```cmd
REM --- Development ---
cd G:\My Drive\plotra\plotra_capture_app
npm start                    REM Expo dev server
npx expo run:android         REM Local debug build

REM --- Build ---
npm install -g eas-cli        REM Install EAS
eas login                     REM Login
eas build --platform android --profile preview  REM Build APK
eas build:list               REM View builds
eas build:download --id XYZ  REM Download specific build

REM --- Debug ---
adb logcat | findstr "plotra"   REM Android logs
npx expo start --clear          REM Clear cache
```

---

## 📚 Documentation Index

- `README.md` — Full API + app documentation
- `BUILD_GUIDE.md` — Detailed build instructions
- `QUICKSTART.md` — Quick commands
- `CAPTURE_APP_SUMMARY.md` — Architecture overview
- `MOBILE_APP_FILES.md` — File listing

---

**You're 3 commands away from an APK:**

```cmd
cd G:\My Drive\plotra\plotra_capture_app
npm install
eas build --platform android --profile preview
```

**Go!** 🚀
