# Desktop launcher script (Windows)
# Run this to start the Plotra mobile API bridge

@echo off
echo Starting Plotra Mobile Backend Bridge...
echo.
echo Make sure your Docker containers are running:
echo   docker-compose up -d
echo.
echo Press any key to start the backend proxy...
pause

REM Check if backend is running
curl -s http://localhost:8000/docs >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Backend is not running!
    echo Please start your Docker containers first:
    echo   cd backend
    echo   docker-compose up -d
    pause
    exit /b 1
)

echo.
echo Backend is running. The mobile app will connect to:
echo   http://your-computer-ip:8000
echo.
echo For Android emulator, use: http://10.0.2.2:8000
echo.
echo Press any key to open build folder...
pause

explorer build\app\outputs\flutter-apk
