import requests
import json

BASE_URL = "http://localhost:5000/api/v1"

# 1. Login
response = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "john@test.com",
    "password": "Patient123!"
})

if response.status_code == 200:
    data = response.json()
    token = data.get("access_token")
    print("Login successful, token:", token[:10] + "...")
    
    # 2. Fetch doctors
    docs_response = requests.get(f"{BASE_URL}/doctors/", headers={
        "Authorization": f"Bearer {token}"
    })
    
    print("Doctors Status Code:", docs_response.status_code)
    try:
        print("Doctors Response JSON:", json.dumps(docs_response.json(), indent=2))
    except Exception as e:
        print("Failed to parse JSON:", docs_response.text)
else:
    print("Login failed:", response.status_code, response.text)
