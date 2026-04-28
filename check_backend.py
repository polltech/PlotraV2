#!/usr/bin/env python3
"""
Quick verification script for Plotra Capture App setup.
Checks that backend is running and accessible from mobile network.
"""
import requests
import sys

BACKEND_URL = "http://192.168.100.5:8000"

def check_backend():
    print("🔍 Checking backend connectivity...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/v2/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Backend reachable at {BACKEND_URL}")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {BACKEND_URL}")
        print("   Is your backend running?")
        print("   Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_farms_endpoint():
    print("\n🔍 Testing /api/v2/capture/farms endpoint...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/v2/capture/farms", timeout=5)
        if response.status_code == 200:
            farms = response.json()
            print(f"✅ Farms endpoint works - {len(farms)} farms found")
            if farms:
                print(f"   Sample: {farms[0]}")
        else:
            print(f"❌ Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("=" * 50)
    print("Plotra Capture App - Pre-Build Check")
    print("=" * 50)
    print()

    if check_backend():
        check_farms_endpoint()
        print("\n✅ Backend is ready for mobile app!")
        print("\n📱 Next steps:")
        print("   1. cd plotra_capture_app")
        print("   2. npm install")
        print("   3. npx expo start")
        print("   4. Scan QR with Expo Go")
        sys.exit(0)
    else:
        print("\n❌ Backend not ready. Fix issues first.")
        sys.exit(1)

if __name__ == "__main__":
    main()
