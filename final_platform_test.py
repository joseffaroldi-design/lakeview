import os
#!/usr/bin/env python3
"""Final comprehensive platform size test with proper timeouts."""
import requests
import time
from PIL import Image
import io

BASE_URL = "https://upload-stage-two.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@lakeview.com"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def test_platform(token, asset_id, platform, expected_width, expected_height):
    """Test a single platform with proper timeout."""
    print(f"\n{Colors.BOLD}Testing {platform} (expected: {expected_width}×{expected_height}){Colors.RESET}")
    
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "source_asset_id": asset_id,
        "item_name": "Cajun Seafood Platter",
        "features": ["Fresh Gulf shrimp", "Grilled oysters"],
        "price": "$24.99",
        "theme": "cajun",
        "variations": 1,
        "platform": platform,
        "auto_copy": False
    }
    
    try:
        # Generate
        response = requests.post(f"{BASE_URL}/ai-designer/generate", headers=headers, json=params, timeout=20)
        if response.status_code != 202:
            print(f"{Colors.RED}✗ Generation failed: {response.status_code}{Colors.RESET}")
            return False
        
        job_id = response.json()["job_id"]
        print(f"  Job ID: {job_id}")
        
        # Poll with longer timeout
        for i in range(60):
            time.sleep(3)
            job_response = requests.get(f"{BASE_URL}/ai-designer/job/{job_id}", headers=headers, timeout=10)
            job = job_response.json()
            status = job.get("status")
            
            if status == "completed":
                # Download and verify
                asset_id = job["variations"][0]["asset_id"]
                file_response = requests.get(f"{BASE_URL}/media/file/{asset_id}", headers=headers, timeout=30)
                img = Image.open(io.BytesIO(file_response.content))
                width, height = img.size
                
                if width == expected_width and height == expected_height:
                    print(f"{Colors.GREEN}✓ Dimensions verified: {width}×{height}{Colors.RESET}")
                    return True
                else:
                    print(f"{Colors.RED}✗ Dimension mismatch: {width}×{height} (expected {expected_width}×{expected_height}){Colors.RESET}")
                    return False
            elif status == "failed":
                error = job.get("error", {})
                print(f"{Colors.RED}✗ Job failed: {error.get('user_message', 'Unknown error')}{Colors.RESET}")
                return False
        
        print(f"{Colors.RED}✗ Timeout waiting for job{Colors.RESET}")
        return False
        
    except Exception as e:
        print(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        return False

def main():
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}Final Platform Size Test - Phase 6{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    
    # Login
    print("\nAuthenticating...")
    response = requests.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = response.json()["token"]
    print(f"{Colors.GREEN}✓ Login successful{Colors.RESET}")
    
    # Get test asset
    headers = {"Authorization": f"Bearer {token}"}
    assets = requests.get(f"{BASE_URL}/media/assets?kind=image&limit=1", headers=headers).json()["assets"]
    asset_id = assets[0]["id"]
    print(f"{Colors.GREEN}✓ Using test asset: {asset_id}{Colors.RESET}")
    
    # Test all platforms
    results = {}
    
    print(f"\n{Colors.BOLD}Critical Retest Scenarios:{Colors.RESET}")
    results["instagram_story"] = test_platform(token, asset_id, "instagram_story", 1080, 1920)
    results["twitter"] = test_platform(token, asset_id, "twitter", 1200, 675)
    
    print(f"\n{Colors.BOLD}Sanity Check - Square Platforms:{Colors.RESET}")
    results["instagram_post"] = test_platform(token, asset_id, "instagram_post", 1024, 1024)
    results["facebook"] = test_platform(token, asset_id, "facebook", 1200, 1200)
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}Test Results Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")
    
    all_passed = all(results.values())
    
    for platform, passed in results.items():
        status = f"{Colors.GREEN}✓" if passed else f"{Colors.RED}✗"
        print(f"{status} {platform}{Colors.RESET}")
    
    print()
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}SUCCESS: All platform sizes are correct!{Colors.RESET}")
        print(f"{Colors.GREEN}✓ instagram_story generates 1080×1920 PNG{Colors.RESET}")
        print(f"{Colors.GREEN}✓ twitter generates 1200×675 PNG{Colors.RESET}")
        print(f"{Colors.GREEN}✓ Square platforms still work (1024×1024, 1200×1200){Colors.RESET}")
        print(f"{Colors.GREEN}✓ No backend errors during generation{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}FAILURE: Some platforms have incorrect dimensions{Colors.RESET}")
        return 1

if __name__ == "__main__":
    exit(main())
