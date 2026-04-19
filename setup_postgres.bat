@echo off
REM Setup PostgreSQL for Plotra Platform
REM Run this script to configure the database

echo Configuring PostgreSQL for Plotra Platform...
echo.

REM Check if psql is available
where psql >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PostgreSQL is not installed or not in PATH
    echo Please install PostgreSQL and try again
    pause
    exit /b 1
)

REM Try to set password and create database
echo Setting up PostgreSQL user and database...

REM Try with default password first, then with configured password
psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Password set to 'postgres'
) else (
    echo [SKIP] Password already set or access denied
)

REM Create database
psql -U postgres -c "CREATE DATABASE plotra_db;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Database 'plotra_db' created
) else (
    echo [SKIP] Database may already exist
)

REM Grant privileges
psql -U postgres -d plotra_db -c "GRANT ALL ON DATABASE plotra_db TO postgres;" 2>nul
echo [OK] Privileges granted

echo.
echo ========================================
echo PostgreSQL setup complete!
echo ========================================
echo.
echo You can now start the server with:
echo   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
echo.
pause
