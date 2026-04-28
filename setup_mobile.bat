@echo off
echo ========================================
echo   Plotra Mobile Setup Script
echo ========================================
echo.

REM Check Flutter installation
flutter --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Flutter not found in PATH
    echo Please install Flutter first:
    echo 1. Download from: https://flutter.dev/docs/get-started/install/windows
    echo 2. Extract to: C:\src\flutter
    echo 3. Add C:\src\flutter\bin to System PATH
    echo 4. Restart PowerShell and run this script again
    pause
    exit /b 1
)

echo [1/6] Flutter found! Continuing...
echo.

REM Create project
echo [2/6] Creating Flutter project...
if not exist "plotra_mobile" (
    flutter create plotra_mobile --org ai.plotra --platforms android,ios
    if errorlevel 1 (
        echo ERROR: Failed to create Flutter project
        pause
        exit /b 1
    )
    echo Project created successfully.
) else (
    echo Project folder already exists. Skipping creation.
)

REM Copy our files
echo [3/6] Copying Plotra mobile files...
xcopy /E /I /Y "app\plotra_mobile\lib" "plotra_mobile\lib"
if errorlevel 1 (
    echo ERROR: Failed to copy lib folder. Make sure app/plotra_mobile/ exists
    pause
    exit /b 1
)

xcopy /Y "app\plotra_mobile\pubspec.yaml" "plotra_mobile\pubspec.yaml"
xcopy /Y "app\plotra_mobile\android\app\src\main\AndroidManifest.xml" "plotra_mobile\android\app\src\main\" 2>nul
echo Files copied.

REM Install dependencies
echo [4/6] Installing dependencies...
cd plotra_mobile
flutter pub get
if errorlevel 1 (
    echo ERROR: flutter pub get failed
    cd ..
    pause
    exit /b 1
)

REM Generate Hive adapters
echo [5/6] Generating Hive database adapters...
flutter pub run build_runner build --delete-conflicting-outputs
if errorlevel 1 (
    echo WARNING: Build runner had issues, but continuing...
)

REM Configure API URL
echo [6/6] Configuration:
echo.
echo IMPORTANT: Edit lib/services/api_service.dart
echo Change baseUrl to your backend:
echo   Android emulator: http://10.0.2.2:8000/api/v1
echo   Real device:      http://YOUR-IP:8000/api/v1
echo.
echo ========================================
echo Setup complete! Next steps:
echo 1. Start backend: docker-compose up -d
echo 2. Connect Android device/emulator
echo 3. Run: flutter run
echo ========================================
pause
