# Quick Start - Plotra Capture App

## Step 1: Install Dependencies

```bash
cd plotra_capture_app
npm install
```

## Step 2: Configure Backend URL

Edit `app.json`:
```json
{
  "expo": {
    "extra": {
      "API_BASE_URL": "http://YOUR-IP:8000/api/v2"
    }
  }
}
```

**For Android emulator:** Use `http://10.0.2.2:8000/api/v2`
**For physical device:** Use your computer's LAN IP, e.g., `http://192.168.1.100:8000/api/v2`

## Step 3: Update Backend CORS

In your backend `settings.py` or config, add your mobile dev URL:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",          # Web frontend
    "http://localhost:8000",          # API docs
    "http://localhost:19006",         # Expo dev
    "http://192.168.1.100:19006",     # LAN dev
]
```

## Step 4: Start Development Server

```bash
npm start
```

Scan QR code with Expo Go app (Android/iOS) or press `a` for Android emulator.

## Step 5: Generate APK

### Using EAS Build (easiest):

```bash
# Install EAS CLI
npm install -g eas-cli

# Login
eas login

# Build APK
eas build --platform android --profile preview
```

APK download link appears when build completes (~15 min).

### Using `expo run:android` (debug):

```bash
npx expo run:android
```

Generates debug APK at `android/app/build/outputs/apk/debug/`

---

## Test Credentials

For testing, register a new account in the app or use backend seed data.

## Need Help?

- Ensure backend is accessible from mobile (same network)
- Test API: `http://YOUR-IP:8000/api/v2/health`
- Check server logs for errors
