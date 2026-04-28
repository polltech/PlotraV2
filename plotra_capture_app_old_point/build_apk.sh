#!/bin/bash
# Plotra Capture App - Build Script for APK
# Run this script to install dependencies and build the APK

set -e  # Exit on any error

echo "========================================="
echo "Plotra Capture App - APK Build Script"
echo "========================================="
echo ""

# Check Node.js
echo "1. Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "   ERROR: Node.js not installed. Install from https://nodejs.org/"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "   Node.js version: $NODE_VERSION"
echo ""

# Check npm
echo "2. Checking npm..."
if ! command -v npm &> /dev/null; then
    echo "   ERROR: npm not found. Reinstall Node.js."
    exit 1
fi
echo "   npm version: $(npm --version)"
echo ""

# Check EAS CLI
echo "3. Checking EAS CLI..."
if ! command -v eas &> /dev/null; then
    echo "   EAS CLI not found. Installing globally..."
    npm install -g eas-cli
fi
echo "   EAS CLI version: $(eas --version)"
echo ""

# Navigate to app directory
cd "$(dirname "$0")"
echo "4. Working in: $(pwd)"
echo ""

# Install dependencies
echo "5. Installing dependencies..."
npm install
echo ""

# Configuration check
echo "6. Configuration check..."
if [ -f "app.json" ]; then
    echo "   app.json exists ✓"
    CURRENT_URL=$(grep -o '"API_BASE_URL": "[^"]*"' app.json | cut -d'"' -f4)
    echo "   Current API_BASE_URL: $CURRENT_URL"
    echo ""
    echo "   IMPORTANT: Ensure API_BASE_URL is set to your backend's public URL."
    echo "   For local testing, use your LAN IP (e.g., http://192.168.1.100:8000/api/v2)"
    echo "   For EAS cloud build, use public domain (e.g., https://api.plotra.africa/api/v2)"
    echo ""
    read -p "   Continue with current URL? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Edit app.json and re-run this script."
        exit 1
    fi
fi
echo ""

# EAS Login check
echo "7. Checking EAS login..."
if ! eas whoami &> /dev/null; then
    echo "   Not logged in to EAS. Logging in..."
    eas login
fi
echo "   Logged in as: $(eas whoami)"
echo ""

# Build APK
echo "8. Building APK with EAS..."
echo "   This will upload source to Expo servers and build in the cloud."
echo "   Build time: ~10-20 minutes"
echo ""
read -p "   Start build now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Starting build..."
    eas build --platform android --profile preview
    echo ""
    echo "   Build submitted! Check progress at: https://expo.dev/accounts/"
    echo ""
fi

echo "========================================="
echo "Build script completed!"
echo "========================================="
