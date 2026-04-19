import requests
import json

url = "http://localhost:8000/api/openapi.json"
response = requests.get(url)
openapi = response.json()

print("=== API Paths ===")
for path in sorted(openapi['paths'].keys()):
    print(path)
