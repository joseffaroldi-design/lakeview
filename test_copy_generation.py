#!/usr/bin/env python3
"""Quick test for copy generation timeout issue."""
import requests
import time
import os

BASE_URL = os.getenv("REACT_APP_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com")
API_BASE = f"{BASE_URL}/api"

# Login
print("Logging in...")
response = requests.post(
    f"{API_BASE}/auth/login",
    json={"email": "admin@lakeview.com", "password": "[REDACTED]"},
    timeout=10
)
token = response.json()["token"]
print(f"Token: {token[:20]}...")

# Get test asset
print("\nGetting test asset...")
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{API_BASE}/media/assets?kind=image&limit=10", headers=headers, timeout=10)
assets = response.json().get("assets", [])
asset_id = assets[0]["id"] if assets else None
print(f"Asset ID: {asset_id}")

# Test with auto_copy=True
print("\nGenerating design with auto_copy=True...")
params = {
    "source_asset_id": asset_id,
    "item_name": "Test Burger",
    "features": ["Juicy patty", "Fresh lettuce"],
    "price": "$9.99",
    "theme": "modern",
    "variations": 1,
    "auto_copy": True,
    "tone": "professional"
}

response = requests.post(f"{API_BASE}/ai-designer/generate", headers=headers, json=params, timeout=30)
print(f"Generate response: {response.status_code}")
if response.status_code == 202:
    job_id = response.json()["job_id"]
    print(f"Job ID: {job_id}")
    
    # Poll for completion
    print("\nPolling job status...")
    for i in range(60):  # 2 minutes max
        time.sleep(2)
        response = requests.get(f"{API_BASE}/ai-designer/job/{job_id}", headers=headers, timeout=10)
        job = response.json()
        status = job.get("status")
        progress = job.get("progress", 0)
        print(f"  [{i*2}s] Status: {status}, Progress: {progress}%")
        
        if status == "completed":
            print("\n✓ Job completed!")
            copy_pack = job.get("copy_pack")
            if copy_pack:
                print("✓ Copy pack generated!")
                print(f"  FB Post: {len(copy_pack.get('fb_post', ''))} chars")
                print(f"  IG Post: {len(copy_pack.get('ig_post', ''))} chars")
            else:
                print("✗ No copy pack in response")
            break
        elif status == "failed":
            print(f"\n✗ Job failed: {job.get('error')}")
            break
else:
    print(f"Failed to generate: {response.text}")
