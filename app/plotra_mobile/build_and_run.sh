#!/bin/bash
# Desktop launcher script (macOS/Linux)

echo "Starting Plotra Mobile Backend Bridge..."
echo ""
echo "Make sure your Docker containers are running:"
echo "  docker-compose up -d"
echo ""

read -p "Press any key to start the backend proxy..." -n1 -s
echo ""

# Check if backend is running
if ! curl -s http://localhost:8000/docs > /dev/null; then
    echo ""
    echo "ERROR: Backend is not running!"
    echo "Please start your Docker containers first:"
    echo "  cd backend"
    echo "  docker-compose up -d"
    read -p "Press any key to continue..."
    exit 1
fi

echo ""
echo "Backend is running. The mobile app will connect to:"
echo "  http://your-computer-ip:8000"
echo ""
echo "For iOS simulator, use: http://localhost:8000"
echo ""

read -p "Press any key to open build folder..." -n1 -s
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    open build/app/outputs/flutter-apk 2>/dev/null || open build/app/outputs/flutter-apk/app-release.apk
else
    xdg-open build/app/outputs/flutter-apk 2>/dev/null || echo "Open: build/app/outputs/flutter-apk/"
fi
