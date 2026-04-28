# Quick Start Guide for Plotra Mobile

## Setup (5 minutes)

```bash
# 1. Navigate to mobile folder
cd app/plotra_mobile

# 2. Install Flutter (if not installed)
# Windows: winget install Flutter
# Mac: brew install flutter
# Verify: flutter doctor

# 3. Install dependencies
flutter pub get

# 4. Generate Hive adapters (database models)
flutter pub run build_runner build --delete-conflicting-outputs

# 5. Connect your device/emulator
# Android: Start Android Studio emulator OR connect phone via USB
# Mac iOS: Open iOS simulator

# 6. Run the app
flutter run

# 7. Build APK
flutter build apk --release
```

## Configure Backend URL

Edit: `lib/services/api_service.dart`
```dart
static const String baseUrl = 'http://YOUR-IP:8000/api/v1';
```

Examples:
- **Local emulator**: `http://10.0.2.2:8000/api/v1`
- **Your DO server**: `http://your-domain.com:8000/api/v1`
- **Local network**: `http://192.168.1.100:8000/api/v1`

## Folder Structure

All files are in `app/plotra_mobile/`:

```
app/plotra_mobile/
├── lib/
│   ├── main.dart                      ✅ App entry + routing
│   ├── utils/app_theme.dart           ✅ Colors + theme
│   ├── models/
│   │   ├── user.dart                  ✅ User + Hive adapter
│   │   ├── farm.dart                  ✅ Farm + Hive adapter
│   │   └── latlng_data.dart           ✅ GPS points
│   ├── services/
│   │   ├── api_service.dart           ✅ HTTP + error handling
│   │   └── auth_service.dart          ✅ Login state
│   ├── screens/
│   │   ├── splash_screen.dart         ✅ Animated logo
│   │   ├── login_screen.dart          ✅ Login form
│   │   ├── dashboard_screen.dart      ✅ Farm list + stats
│   │   ├── farm_map_screen.dart       ✅ Draw polygons
│   │   └── profile_screen.dart        ✅ User profile
│   └── widgets/
│       ├── farm_card.dart             ✅ Farm list item
│       └── stat_card.dart             ✅ Stats card
├── pubspec.yaml                       ✅ Dependencies
├── README.md                          ✅ Full docs
├── android/                           ✅ Android config
└── build_and_run.bat/.sh             ✅ Helper scripts
```

## What's Included

### Modern UI Features
- Dark theme matching Plotra brand colors
- Smooth animations (fade, slide, scale)
- Material 3 design components
- Glassmorphism cards
- Gold accent gradients
- Shimmer loading effects

### Core Functionality
- JWT authentication
- Farm CRUD operations
- Interactive polygon drawing on map
- Real-time area calculation
- Offline storage with Hive
- Error handling + retry logic
- Pull-to-refresh ready

### Ready for Production
- Secure token storage (flutter_secure_storage)
- Network timeout handling
- Input validation
- Responsive layout
- Accessibility labels

## Next Steps

1. **Replace mock data** in `dashboard_screen.dart` line 57:
```dart
// Replace mock farms with real API call:
final farms = await Provider.of<AuthService>(context, listen: false)
    .api
    .getFarms();
```

2. **Add offline sync** (see `README.md` section "Tips for Offline Mode")

3. **Add satellite image layer** to map (see `farm_map_screen.dart` comments)

4. **Implement push notifications** (use firebase_messaging package)

5. **Add photo upload** per farm (use image_picker + multipart)

## Troubleshooting

**"Missing Android SDK"**
```bash
flutter config --android-sdk C:\Users\YourName\AppData\Local\Android\sdk
```

**"No devices found"**
- Android: `flutter emulators --create` then `flutter emulators --launch Pixel_5`
- iPhone (Mac): `open -a Simulator`

**"Build failed"**
```bash
flutter clean
flutter pub get
```

**"Hive adapter not generated"**
```bash
flutter pub add hive_generator build_runner --dev
flutter pub run build_runner build --delete-conflicting-outputs
```

## Production Build

```bash
# Android
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk

# iOS (Mac only)
flutter build ios --release
# Then open in Xcode and archive

# Web
flutter build web --release
# Output: build/web/
```

## Connect to Your Backend

The app is configured to connect to your FastAPI backend at:
- **Default**: `http://10.0.2.2:8000/api/v1` (Android emulator)
- **Production**: Update to your DigitalOcean IP

The API expects these endpoints:
```
POST   /api/v1/auth/token-form
GET    /api/v1/farms/
POST   /api/v1/farms/
PUT    /api/v1/farms/{id}
GET    /api/v1/users/me
```

## Files are Ready to Use

All files are individual, ready to copy into a fresh Flutter project:
1. Run `flutter create plotra_mobile --org ai.plotra`
2. Copy folders from `app/plotra_mobile/` over
3. Run `flutter pub get`
4. Run `flutter pub run build_runner build`
5. Configure API URL
6. Run `flutter run`

---

**All files created in: `app/plotra_mobile/`**
