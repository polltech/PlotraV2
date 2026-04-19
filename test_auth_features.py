"""
Test phone login and optional email registration features
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v2"

def test_register_email_only():
    """Test registration with email only"""
    payload = {
        "email": "testemailonly@example.com",
        "password": "TestPass123!",
        "first_name": "Email",
        "last_name": "Only",
        "role": "farmer",
        "country": "Kenya"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Register email-only: {response.status_code}")
    if response.status_code != 201:
        print(f"  Error: {response.text[:200]}")
    return response.status_code == 201

def test_register_phone_only():
    """Test registration with phone only (Kenya)"""
    payload = {
        "phone_number": "+254712345678",
        "password": "TestPass123!",
        "first_name": "Phone",
        "last_name": "Only",
        "role": "farmer",
        "country": "Kenya"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Register phone-only: {response.status_code}")
    if response.status_code != 201:
        print(f"  Error: {response.text[:200]}")
    return response.status_code == 201

def test_register_both():
    """Test registration with both email and phone"""
    payload = {
        "email": "testboth@example.com",
        "phone_number": "+255712345678",
        "password": "TestPass123!",
        "first_name": "Both",
        "last_name": "Fields",
        "role": "farmer",
        "country": "Tanzania"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Register both: {response.status_code}")
    if response.status_code != 201:
        print(f"  Error: {response.text[:200]}")
    return response.status_code == 201

def test_register_no_contact():
    """Test registration with neither email nor phone should fail"""
    payload = {
        "password": "TestPass123!",
        "first_name": "No",
        "last_name": "Contact",
        "role": "farmer",
        "country": "Kenya"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Register no-contact: {response.status_code} (expected 422)")
    if response.status_code != 422:
        print(f"  Expected 422 validation error")
        return False
    return True

def test_register_invalid_country():
    """Test registration with invalid country"""
    payload = {
        "phone_number": "+254712345678",
        "password": "TestPass123!",
        "first_name": "Invalid",
        "last_name": "Country",
        "role": "farmer",
        "country": "Rwanda"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Register invalid country: {response.status_code} (expected 422)")
    if response.status_code != 422:
        print(f"  Expected 422 validation error")
        return False
    return True

def test_register_invalid_phone_prefix():
    """Test registration with phone not from allowed countries"""
    payload = {
        "phone_number": "+257712345678",  # Rwanda prefix
        "password": "TestPass123!",
        "first_name": "Invalid",
        "last_name": "Prefix",
        "role": "farmer",
        "country": "Kenya"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Register invalid phone prefix: {response.status_code} (expected 422)")
    if response.status_code != 422:
        print(f"  Expected 422 validation error")
        return False
    return True

def test_login_email():
    """Test login with email"""
    payload = {
        "username": "testemailonly@example.com",
        "password": "TestPass123!"
    }
    response = requests.post(f"{BASE_URL}/auth/token", data=payload)
    print(f"Login email: {response.status_code}")
    return response.status_code == 200

def test_login_phone():
    """Test login with phone"""
    payload = {
        "username": "+255712345678",
        "password": "TestPass123!"
    }
    response = requests.post(f"{BASE_URL}/auth/token", data=payload)
    print(f"Login phone: {response.status_code}")
    return response.status_code == 200

if __name__ == "__main__":
    print("=== Testing Phone Login & Optional Email ===\n")
    
    tests = [
        ("Email-only registration", test_register_email_only),
        ("Phone-only registration", test_register_phone_only),
        ("Both email and phone registration", test_register_both),
        ("No contact method (should fail)", test_register_no_contact),
        ("Invalid country (should fail)", test_register_invalid_country),
        ("Invalid phone prefix (should fail)", test_register_invalid_phone_prefix),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  Exception: {e}")
            results.append((name, False))
    
    print("\n\n=== Summary ===")
    for name, passed in results:
        status = "✓" if passed else "✗"
        print(f"{status} {name}")
