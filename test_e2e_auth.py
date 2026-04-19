"""
End-to-end test for phone login and optional email registration.
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v2"

def test_phone_only_registration_and_login():
    """Test full flow: register with phone only, then login with phone."""
    # Register with phone only (Kenya)
    payload = {
        "phone_number": "+254722999888",
        "password": "SecurePass123!",
        "first_name": "PhoneUser",
        "last_name": "Test",
        "role": "farmer",
        "country": "Kenya"
        # email omitted
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
    print(f"Registration (phone only): {resp.status_code}")
    if resp.status_code != 201:
        print(f"  Error: {resp.text[:300]}")
        return False

    user_data = resp.json()
    print(f"  User ID: {user_data.get('id')}")
    print(f"  Email: {user_data.get('email')}")
    print(f"  Phone: {user_data.get('phone_number')}")

    # Login with phone number
    login_data = {
        "username": "+254722999888",
        "password": "SecurePass123!"
    }
    # Form-encoded login
    form_data = {k: (None, v) for k, v in login_data.items()}
    resp = requests.post(f"{BASE_URL}/auth/token-form", data=login_data, timeout=10)
    print(f"Login (phone): {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text[:300]}")
        return False

    token_data = resp.json()
    token = token_data.get('access_token')
    print(f"  Token received: {token[:20]}...")
    print("  SUCCESS: Phone registration and login works!")
    return True

def test_email_only_registration_and_login():
    """Test registration with email only."""
    payload = {
        "email": "emailonly@example.com",
        "password": "SecurePass123!",
        "first_name": "EmailUser",
        "last_name": "Test",
        "role": "farmer",
        "country": "Uganda"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
    print(f"Registration (email only): {resp.status_code}")
    if resp.status_code != 201:
        print(f"  Error: {resp.text[:300]}")
        return False

    # Login with email
    login_data = {
        "username": "emailonly@example.com",
        "password": "SecurePass123!"
    }
    resp = requests.post(f"{BASE_URL}/auth/token-form", data=login_data, timeout=10)
    print(f"Login (email): {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text[:300]}")
        return False
    print("  SUCCESS: Email registration and login works!")
    return True

def test_invalid_country_rejected():
    """Test that registration with phone from invalid country fails."""
    payload = {
        "phone_number": "+254700000000",  # Kenya prefix but country=Rwanda
        "password": "SecurePass123!",
        "first_name": "Invalid",
        "last_name": "Country",
        "role": "farmer",
        "country": "Rwanda"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
    print(f"Registration (invalid country): {resp.status_code} (expected 422)")
    return resp.status_code == 422

def test_no_contact_rejected():
    """Test registration without email and phone fails."""
    payload = {
        "password": "SecurePass123!",
        "first_name": "NoContact",
        "last_name": "Test",
        "role": "farmer",
        "country": "Kenya"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
    print(f"Registration (no contact): {resp.status_code} (expected 422)")
    return resp.status_code == 422

if __name__ == "__main__":
    print("=== Phone Login & Optional Email - E2E Tests ===\n")
    
    tests = [
        ("Phone-only registration & login", test_phone_only_registration_and_login),
        ("Email-only registration & login", test_email_only_registration_and_login),
        ("Invalid country rejection", test_invalid_country_rejected),
        ("No contact rejection", test_no_contact_rejected),
    ]
    
    results = []
    for name, test in tests:
        print(f"\n--- {name} ---")
        try:
            result = test()
            results.append((name, result))
        except Exception as e:
            print(f"  Exception: {e}")
            results.append((name, False))
    
    print("\n=== Summary ===")
    ok = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            ok = False
    
    sys.exit(0 if ok else 1)
