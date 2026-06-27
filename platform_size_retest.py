#!/usr/bin/env python3
"""
Platform Size Retest - Phase 6
Verify that non-square platform dimensions are now working correctly after HTML renderer fix.
"""
import json
import os
import sys
import time
import requests
from PIL import Image
import io

# Configuration
BASE_URL = os.getenv("REACT_APP_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com")
API_BASE = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@lakeview.com"
ADMIN_PASSWORD = "83CeLOZJQbOcopK0yYmNtdRQg4VPii8o"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(title):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")

def login():
    """Login and return session token."""
    print_header("Authentication")
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            print(f"{Colors.GREEN}✓ Login successful{Colors.RESET}")
            return token
        else:
            print(f"{Colors.RED}✗ Login failed: {response.status_code} - {response.text}{Colors.RESET}")
            return None
    except Exception as e:
        print(f"{Colors.RED}✗ Login error: {e}{Colors.RESET}")
        return None

def get_test_asset_id(token):
    """Get a test food photo asset ID."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_BASE}/media/assets?kind=image&limit=50",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            assets = response.json().get("assets", [])
            for asset in assets:
                if asset.get("kind") == "image" and asset.get("status") == "active":
                    asset_id = asset.get("id")
                    filename = asset.get("filename", "")
                    print(f"{Colors.GREEN}✓ Using test asset: {filename} ({asset_id}){Colors.RESET}")
                    return asset_id
            print(f"{Colors.RED}✗ No active image assets found{Colors.RESET}")
            return None
        else:
            print(f"{Colors.RED}✗ Failed to get assets: {response.status_code}{Colors.RESET}")
            return None
    except Exception as e:
        print(f"{Colors.RED}✗ Error getting asset: {e}{Colors.RESET}")
        return None

def generate_design(token, asset_id, platform):
    """Generate design for specific platform."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "source_asset_id": asset_id,
            "item_name": "Cajun Seafood Platter",
            "features": ["Fresh Gulf shrimp", "Grilled oysters", "Blackened catfish"],
            "price": "$24.99",
            "theme": "cajun",
            "variations": 1,
            "platform": platform,
            "auto_copy": False
        }
        
        response = requests.post(
            f"{API_BASE}/ai-designer/generate",
            headers=headers,
            json=params,
            timeout=15
        )
        
        if response.status_code == 202:
            data = response.json()
            job_id = data.get("job_id")
            print(f"  Job created: {job_id}")
            return job_id
        else:
            print(f"{Colors.RED}  Generation failed: {response.status_code} - {response.text}{Colors.RESET}")
            return None
    except Exception as e:
        print(f"{Colors.RED}  Generation error: {e}{Colors.RESET}")
        return None

def poll_job(token, job_id, timeout=120):
    """Poll job until completed."""
    headers = {"Authorization": f"Bearer {token}"}
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"{API_BASE}/ai-designer/job/{job_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                job = response.json()
                status = job.get("status")
                progress = job.get("progress", 0)
                
                if status == "completed":
                    print(f"  {Colors.GREEN}Job completed{Colors.RESET}")
                    return job
                elif status == "failed":
                    error = job.get("error", {})
                    print(f"{Colors.RED}  Job failed: {error.get('user_message', 'Unknown error')}{Colors.RESET}")
                    return None
                else:
                    print(f"  Progress: {progress}%", end="\r")
                    time.sleep(2)
            else:
                print(f"{Colors.RED}  Poll failed: {response.status_code}{Colors.RESET}")
                return None
        except Exception as e:
            print(f"{Colors.RED}  Poll error: {e}{Colors.RESET}")
            return None
    
    print(f"{Colors.RED}  Timeout waiting for job{Colors.RESET}")
    return None

def download_and_verify_dimensions(token, asset_id, expected_width, expected_height):
    """Download PNG and verify actual dimensions."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_BASE}/media/file/{asset_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            # Open image with PIL
            img = Image.open(io.BytesIO(response.content))
            actual_width, actual_height = img.size
            
            if actual_width == expected_width and actual_height == expected_height:
                print(f"{Colors.GREEN}  ✓ Dimensions verified: {actual_width}×{actual_height}{Colors.RESET}")
                return True, actual_width, actual_height
            else:
                print(f"{Colors.RED}  ✗ Dimension mismatch!{Colors.RESET}")
                print(f"    Expected: {expected_width}×{expected_height}")
                print(f"    Actual:   {actual_width}×{actual_height}")
                return False, actual_width, actual_height
        else:
            print(f"{Colors.RED}  Failed to download: {response.status_code}{Colors.RESET}")
            return False, None, None
    except Exception as e:
        print(f"{Colors.RED}  Download error: {e}{Colors.RESET}")
        return False, None, None

def test_platform(token, asset_id, platform, expected_width, expected_height):
    """Test a single platform."""
    print(f"\n{Colors.BOLD}Testing {platform} (expected: {expected_width}×{expected_height}){Colors.RESET}")
    
    # Generate design
    job_id = generate_design(token, asset_id, platform)
    if not job_id:
        return False, None, None
    
    # Poll until complete
    job = poll_job(token, job_id)
    if not job:
        return False, None, None
    
    # Get asset ID from variations
    variations = job.get("variations", [])
    if not variations or variations[0].get("status") != "completed":
        print(f"{Colors.RED}  No completed variations{Colors.RESET}")
        return False, None, None
    
    generated_asset_id = variations[0].get("asset_id")
    if not generated_asset_id:
        print(f"{Colors.RED}  No asset ID in variation{Colors.RESET}")
        return False, None, None
    
    # Download and verify
    return download_and_verify_dimensions(token, generated_asset_id, expected_width, expected_height)

def main():
    """Run platform size retest."""
    print_header("Platform Size Retest - Phase 6")
    print("Testing non-square platform dimensions after HTML renderer fix\n")
    
    # Login
    token = login()
    if not token:
        print(f"\n{Colors.RED}Authentication failed. Exiting.{Colors.RESET}")
        sys.exit(1)
    
    # Get test asset
    asset_id = get_test_asset_id(token)
    if not asset_id:
        print(f"\n{Colors.RED}No test asset found. Exiting.{Colors.RESET}")
        sys.exit(1)
    
    print_header("Critical Retest Scenarios")
    
    # Test platforms
    results = {}
    
    # Scenario 1: Instagram Story (Non-Square)
    success, w, h = test_platform(token, asset_id, "instagram_story", 1080, 1920)
    results["instagram_story"] = {"success": success, "expected": (1080, 1920), "actual": (w, h)}
    
    # Scenario 2: Twitter (Non-Square)
    success, w, h = test_platform(token, asset_id, "twitter", 1200, 675)
    results["twitter"] = {"success": success, "expected": (1200, 675), "actual": (w, h)}
    
    # Scenario 3: Sanity Check - Square Platforms
    print(f"\n{Colors.BOLD}Sanity Check: Square Platforms{Colors.RESET}")
    
    success, w, h = test_platform(token, asset_id, "instagram_post", 1024, 1024)
    results["instagram_post"] = {"success": success, "expected": (1024, 1024), "actual": (w, h)}
    
    success, w, h = test_platform(token, asset_id, "facebook", 1200, 1200)
    results["facebook"] = {"success": success, "expected": (1200, 1200), "actual": (w, h)}
    
    # Print summary
    print_header("Test Results Summary")
    
    all_passed = True
    for platform, result in results.items():
        expected = result["expected"]
        actual = result["actual"]
        success = result["success"]
        
        if success:
            print(f"{Colors.GREEN}✓ {platform}: {actual[0]}×{actual[1]} (expected {expected[0]}×{expected[1]}){Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ {platform}: {actual[0]}×{actual[1] if actual[0] else 'FAILED'} (expected {expected[0]}×{expected[1]}){Colors.RESET}")
            all_passed = False
    
    print()
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}SUCCESS: All platform sizes are correct!{Colors.RESET}")
        print(f"{Colors.GREEN}✓ Non-square platforms (instagram_story, twitter) now generate correct dimensions{Colors.RESET}")
        print(f"{Colors.GREEN}✓ Square platforms (instagram_post, facebook) still work correctly{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}FAILURE: Some platforms have incorrect dimensions{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
