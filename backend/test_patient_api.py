import requests
import json

BASE_URL = "http://localhost:5000"
EMAIL = "dr.mehta@vitalmind.com"
PASSWORD = "Doctor123!"

def test_patient_detail():
    print(f"--- Logging in as {EMAIL} ---")
    login_res = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": EMAIL,
        "password": PASSWORD
    })
    
    if login_res.status_code != 200:
        print(f"Login failed: {login_res.text}")
        return
        
    token = login_res.json().get("token")
    print(f"Login successful. Token: {token[:20]}...")
    
    # Get patients list to find a valid ID
    print("\n--- Fetching patients list ---")
    patients_res = requests.get(f"{BASE_URL}/api/v1/patients/", headers={
        "Authorization": f"Bearer {token}"
    })
    
    if patients_res.status_code != 200:
        print(f"Fetch patients failed: {patients_res.text}")
        return
        
    patients = patients_res.json()
    if not patients:
        print("No patients found in DB.")
        return
        
    patient_id = patients[0]['id']
    print(f"Found patient ID: {patient_id}")
    
    # Test detail endpoint
    print(f"\n--- Fetching detail for {patient_id} ---")
    detail_res = requests.get(f"{BASE_URL}/api/v1/patients/{patient_id}", headers={
        "Authorization": f"Bearer {token}"
    })
    
    print(f"Status Code: {detail_res.status_code}")
    if detail_res.status_code == 200:
        print("Success! Data received:")
        print(json.dumps(detail_res.json(), indent=2)[:500] + "...")
    else:
        print(f"Failed! {detail_res.text}")

if __name__ == "__main__":
    test_patient_detail()
