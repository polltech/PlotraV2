# Plotra Mobile App

Flutter mobile application for Plotra EUDR Compliance & Traceability Platform.

## Features

- **Authentication**: Secure login with JWT tokens
- **Farm Management**: View, add, and edit farm polygons
- **Interactive Map**: Draw farm boundaries with Google/OpenStreet maps
- **Offline Support**: SQLite/Hive local storage with sync
- **Real-time Updates**: Live farm verification status
- **Role-based Access**: Different dashboards for farmers, officers, admins
- **Modern UI**: Material 3 design with dark theme

## Tech Stack

- **Framework**: Flutter 3.x
- **State Management**: Provider
- **Maps**: flutter_map (OpenStreetMap)
- **Location**: geolocator + location
- **Storage**: Hive, SQLite, SharedPreferences
- **HTTP Client**: Dio
- **UI**: Material 3

## Prerequisites

- Flutter SDK 3.3+ ([Download](https://flutter.dev/docs/get-started/install))
- Android Studio (for Android) or Xcode (for Mac/iOS)
- Backend API running at `http://your-server.com:8000`

## Quick Start

### 1. Install Flutter

**Windows:**
```powershell
winget install Flutter
```

**Mac:**
```bash
brew install flutter
```

**Linux:**
```bash
sudo snap install flutter --classic
```

Verify:
```bash
flutter doctor
```

### 2. Create Project

```bash
flutter create plotra_mobile --org ai.plotra --platforms android,ios
cd plotra_mobile
```

### 3. Copy Project Files

Copy all files from `app/plotra_mobile/` directory into your Flutter project:
```
lib/
├── main.dart
├── screens/
├── services/
├── models/
├── widgets/
└── utils/
pubspec.yaml (replace existing)
```

### 4. Install Dependencies

```bash
flutter pub get
```

### 5. Generate Hive Adapters

```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

### 6. Configure API URL

Edit `lib/services/api_service.dart`:
```dart
static const String baseUrl = 'http://YOUR-SERVER-IP:8000/api/v1';
```

**For DigitalOcean/Cloud server:**
```dart
static const String baseUrl = 'http://your-domain.com:8000/api/v1';
```

**For Android emulator (localhost):**
```dart
static const String baseUrl = 'http://10.0.2.2:8000/api/v1';
```

**For iOS emulator:**
```dart
static const String baseUrl = 'http://localhost:8000/api/v1';
```

### 7. Run the App

```bash
# Android emulator
flutter run -d android

# iOS simulator (Mac only)
flutter run -d ios

# Chrome web
flutter run -d chrome
```

### 8. Build APK

```bash
# Debug
flutter build apk --debug

# Release
flutter build apk --release

# App Bundle (Google Play)
flutter build appbundle --release
```

Output: `build/app/outputs/flutter-apk/app-release.apk`

## Project Structure

```
plotra_mobile/
├── lib/
│   ├── main.dart                    # App entry point
│   ├── screens/                     # UI screens
│   │   ├── splash_screen.dart
│   │   ├── login_screen.dart
│   │   ├── dashboard_screen.dart
│   │   ├── farm_map_screen.dart     # Polygon drawing
│   │   └── profile_screen.dart
│   ├── services/                    # Business logic
│   │   ├── api_service.dart         # API calls to FastAPI
│   │   └── auth_service.dart        # Auth state management
│   ├── models/                      # Data models
│   │   ├── user.dart                # User model with Hive
│   │   ├── farm.dart                # Farm model with Hive
│   │   └── latlng_data.dart         # LatLng for polygons
│   ├── widgets/                     # Reusable components
│   │   ├── farm_card.dart
│   │   └── stat_card.dart
│   └── utils/                       # Helpers
│       └── app_theme.dart           # Colors & theme
├── assets/                          # Images, fonts, icons
│   ├── images/
│   └── fonts/
├── pubspec.yaml                     # Dependencies
└── android/                         # Android config
```

## Backend API Integration

The app uses your existing FastAPI backend. Ensure these endpoints exist:

```
POST   /api/v1/auth/token-form     # Login (form-urlencoded)
GET    /api/v1/farms/              # List farms
POST   /api/v1/farms/              # Create farm
PUT    /api/v1/farms/{id}          # Update farm
DELETE /api/v1/farms/{id}          # Delete farm
GET    /api/v1/users/me            # Current user
```

## Configuration

### Change Colors (Branding)

Edit `lib/utils/app_theme.dart`:
```dart
static const Color primaryGreen = Color(0xFF2d5016);
static const Color gold = Color(0xFFd4a853);
```

### Enable Location Permissions (Android)

Edit `android/app/src/main/AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
```

### Enable Location Permissions (iOS)

Edit `ios/Runner/Info.plist`:
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>We need your location to map your farm</string>
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>We need your location to map your farm</string>
```

## Tips for Offline Mode

The app stores data in Hive (local NoSQL DB). To implement full offline sync:

```dart
// In api_service.dart, add:
Future<Farm> createFarmOffline(Farm farm) async {
  final box = await Hive.openBox('plotra_cache');
  final pending = box.get('pending_sync', defaultValue: []) as List;
  pending.add({'type': 'create_farm', 'data': farm.toJson()});
  await box.put('pending_sync', pending);
  return farm;
}

// Background sync:
Future<void> syncPendingChanges() async {
  final box = await Hive.openBox('plotra_cache');
  final pending = box.get('pending_sync', defaultValue: []) as List;
  
  for (var item in pending) {
    try {
      if (item['type'] == 'create_farm') {
        await _api.createFarm(Farm.fromJson(item['data']));
      }
    } catch (e) {
      // Keep in queue
    }
  }
}
```

## Testing on Real Device

### Android
```bash
# Enable USB debugging on phone
# Connect via USB
flutter devices  # Should show your device
flutter run
```

### iOS
```bash
# Open in Xcode
open ios/Runner.xcworkspace

# Connect iPhone, select device in Xcode, run
flutter run
```

## Troubleshooting

### "Gradle task assembleDebug failed"
```bash
flutter clean
flutter pub get
```

### "Location permission denied"
- Android: Check AndroidManifest.xml permissions
- iOS: Open in Xcode and enable location in "Signing & Capabilities"

### "Cannot connect to backend"
```bash
# Check server is running
curl http://localhost:8000/docs

# Use correct IP:
# Android emulator: 10.0.2.2
# iOS simulator: localhost or host.docker.internal
```

### "Hive adapter not found"
```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

## Deploy to Google Play Store

1. Create signed APK:
```bash
flutter build appbundle --release
```

2. Upload to [Google Play Console](https://play.google.com/console)

3. Fill listing, screenshots, content rating, pricing

4. Submit for review (typically 2-7 days)

## Deploy to Apple App Store

1. Build iOS release:
```bash
flutter build ios --release
```

2. Open Xcode:
```bash
open ios/Runner.xcworkspace
```

3. Archive and upload via Xcode or Transporter app

**Note**: Requires Apple Developer account ($99/year)

## Customization

### Update API Endpoints

Edit `lib/services/api_service.dart`:
```dart
static const String baseUrl = 'https://api.plotra.ai/api/v1';
```

### Change Theme

Edit `lib/utils/app_theme.dart` - modify colors to match your brand.

### Add New Fonts

Add font files to `assets/fonts/` and update `pubspec.yaml`:
```yaml
flutter:
  fonts:
    - family: YourFont
      fonts:
        - asset: assets/fonts/YourFont-Regular.ttf
```

## Support

- Issues: https://github.com/plotra/plotra-mobile/issues
- Email: support@plotra.ai

## License

MIT License - see LICENSE file
