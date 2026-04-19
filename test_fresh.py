"""
Final validation: register fresh users with new phone/email.
"""
import requests
import random

BASE_URL = "http://localhost:8000/api/v2"

def random_phone():
    return f"+2547{random.randint(1000000, 9999999)}"

def random_email():
    return f"user{random.randint(10000,99999)}@example.com"

# Test 1: Register fresh phone-only user
payload = {
    "phone_number": random_phone(),
    "password": "TestPass123!",
    "first_name": "Fresh",
    "last_name": "PhoneUser",
    "role": "farmer",
    "country": "Kenya"
}
resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
print("Fresh phone-only reg:", resp.status_code)
if resp.status_code == 201:
    data = resp.json()
    print(f"  Created user id: {data['id']}, phone: {data.get('phone_number')}")
else:
    print(f"  Error: {resp.text[:200]}")
    exit(1)

# Login with that phone
phone = payload["phone_number"]
login_resp = requests.post(f"{BASE_URL}/auth/token-form", data={"username": phone, "password": "TestPass123!"})
print("Login with phone:", login_resp.status_code)
if login_resp.status_code == 200:
    token = login_resp.json()['access_token']
    print(f"  Token: {token[:30]}...")
else:
    print(f"  Error: {login_resp.text[:200]}")
    exit(1)

print("\nAll checks passed! Phone login and registration fully functional.")
