@echo off
REM Plotra Capture App - Windows Build Script
REM Run this file as Administrator for best results

echo =========================================
echo Plotra Capture App - Build Script
echo =========================================
echo.

REM Check Node.js
echo [1/5] Checking Node.js...
node --version
if errorlevel 1 (
    echo ERROR: Node.js not found. Install from https://nodejs.org/
    pause
    exit /b 1
)
echo.

REM Check npm
echo [2/5] Checking npm...
npm --version
if errorlevel 1 (
    echo ERROR: npm not found. Reinstall Node.js.
    pause
    exit /b 1
)
echo.

REM Install dependencies
echo [3/5] Installing dependencies...
cd /d "%~dp0"
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed. Check permissions or network.
    pause
    exit /b 1
)
echo.

REM Check EAS CLI
echo [4/5] Checking EAS CLI...
eas --version >nul 2>&1
if errorlevel 1 (
    echo EAS CLI not found. Installing...
    call npm install -g eas-cli
    if errorlevel 1 (
        echo ERROR: Failed to install EAS CLI. Run as Administrator.
        pause
        exit /b 1
    )
)
echo EAS CLI found.
echo.

REM Configuration check
echo [5/5] Configuration Check
if exist "app.json" (
    echo app.json exists.
    echo.
    echo IMPORTANT: Verify API_BASE_URL in app.json is set to your LAN IP.
    Example: "http://192.168.100.5:8000/api/v2"
    echo.
    echo Your current LAN IP appears to be: 192.168.100.5
    echo If that's correct, you're ready to build!
    echo.
) else (
    echo WARNING: app.json not found!
)

echo.
echo =========================================
echo Ready to build!
echo =========================================
echo.
echo To build APK, run:
echo   eas build --platform android --profile preview
echo.
echo Or use the interactive builder:
echo   eas build
echo.
pause
