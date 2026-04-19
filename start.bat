@echo off
REM Kipawa Platform - Start Script for Windows

echo ========================================
echo Kipawa Platform - Docker Setup
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

echo Docker is running...
echo.

REM Stop existing containers
echo Stopping existing containers...
docker-compose down >nul 2>&1
echo Done.

REM Build and start containers
echo Building and starting containers...
echo This may take a few minutes on first run...
echo.

docker-compose build --no-cache
docker-compose up -d

echo.
echo ========================================
echo Services Started!
echo ========================================
echo.
echo API:       http://localhost:8000/docs
echo Dashboard: http://localhost:8080
echo.
echo To view logs:
echo   docker-compose logs -f backend
echo.
echo To stop:
echo   docker-compose down
echo.
pause
