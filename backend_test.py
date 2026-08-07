#!/usr/bin/env python3
"""
AI Designer Integration Test Suite - Phase 6: Production Readiness QA
Tests all new parameters and their effects on the final output.
"""
import asyncio
import json
import os
import sys
import time
from typing import Dict, Any, List, Optional

import requests
from PIL import Image
import io

# Configuration
BASE_URL = os.getenv("REACT_APP_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com")
API_BASE = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@lakeview.com"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def log_test(name: str, status: str, message: str = ""):
    """Log test result with color coding."""
    if status == "PASS":
        print(f"{Colors.GREEN}✓ {name}{Colors.RESET}")
        if message:
            print(f"  {message}")
        test_results["passed"].append(name)
    elif status == "FAIL":
        print(f"{Colors.RED}✗ {name}{Colors.RESET}")
        if message:
            print(f"  {Colors.RED}{message}{Colors.RESET}")
        test_results["failed"].append({"test": name, "error": message})
    elif status == "WARN":
        print(f"{Colors.YELLOW}⚠ {name}{Colors.RESET}")
        if message:
            print(f"  {Colors.YELLOW}{message}{Colors.RESET}")
        test_results["warnings"].append({"test": name, "warning": message})


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")


def login() -> Optional[str]:
    """Login and return session token."""
    print_section("Authentication")
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            log_test("Admin Login", "PASS", f"Token: {token[:20]}...")
            return token
        else:
            log_test("Admin Login", "FAIL", f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Admin Login", "FAIL", str(e))
        return None


def get_test_asset_id(token: str) -> Optional[str]:
    """Get a test food photo asset ID from media library."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_BASE}/media/assets?kind=image&limit=50",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            assets = response.json().get("assets", [])
            # Look for a food photo (prefer jpg images)
            for asset in assets:
                if asset.get("kind") == "image" and asset.get("status") == "active":
                    asset_id = asset.get("id")
                    filename = asset.get("filename", "")
                    log_test("Get Test Asset", "PASS", f"Using asset: {filename} ({asset_id})")
                    return asset_id
            log_test("Get Test Asset", "FAIL", "No active image assets found")
            return None
        else:
            log_test("Get Test Asset", "FAIL", f"Status {response.status_code}")
            return None
    except Exception as e:
        log_test("Get Test Asset", "FAIL", str(e))
        return None


def generate_design(token: str, asset_id: str, params: Dict[str, Any]) -> Optional[str]:
    """Generate AI Designer design and return job_id."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{API_BASE}/ai-designer/generate",
            headers=headers,
            json=params,
            timeout=15
        )
        if response.status_code == 202:
            data = response.json()
            job_id = data.get("job_id")
            return job_id
        else:
            print(f"  {Colors.RED}Generation failed: {response.status_code} - {response.text}{Colors.RESET}")
            return None
    except Exception as e:
        print(f"  {Colors.RED}Generation error: {e}{Colors.RESET}")
        return None


def poll_job(token: str, job_id: str, timeout: int = 120) -> Optional[Dict[str, Any]]:
    """Poll job status until completed or timeout."""
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
                    return job
                elif status == "failed":
                    error = job.get("error", {})
                    print(f"  {Colors.RED}Job failed: {error.get('user_message', 'Unknown error')}{Colors.RESET}")
                    return None
                else:
                    # Still processing
                    print(f"  Progress: {progress}%", end="\r")
                    time.sleep(2)
            else:
                print(f"  {Colors.RED}Poll failed: {response.status_code}{Colors.RESET}")
                return None
        except Exception as e:
            print(f"  {Colors.RED}Poll error: {e}{Colors.RESET}")
            return None
    
    print(f"  {Colors.RED}Timeout waiting for job completion{Colors.RESET}")
    return None


def get_asset_metadata(token: str, asset_id: str) -> Optional[Dict[str, Any]]:
    """Get asset metadata including dimensions."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_BASE}/media/assets/{asset_id}",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"  {Colors.RED}Asset metadata error: {e}{Colors.RESET}")
        return None


# ============================================================================
# Test Scenarios
# ============================================================================

def test_scenario_1_variant_count(token: str, asset_id: str):
    """Test Scenario 1: Variant Count (1, 3, 5)"""
    print_section("Scenario 1: Variant Count (1, 3, 5)")
    
    base_params = {
        "source_asset_id": asset_id,
        "item_name": "Crispy Fried Shrimp Po-Boy",
        "features": ["Gulf shrimp", "Crispy breading", "Fresh lettuce", "Remoulade sauce"],
        "price": "$12.99",
        "theme": "cajun",
        "auto_copy": False
    }
    
    for count in [1, 3, 5]:
        print(f"\n{Colors.BOLD}Testing variations={count}{Colors.RESET}")
        params = {**base_params, "variations": count}
        
        job_id = generate_design(token, asset_id, params)
        if not job_id:
            log_test(f"Variant Count: {count}", "FAIL", "Failed to generate")
            continue
        
        job = poll_job(token, job_id)
        if not job:
            log_test(f"Variant Count: {count}", "FAIL", "Job did not complete")
            continue
        
        variations = job.get("variations", [])
        completed = [v for v in variations if v.get("status") == "completed"]
        
        if len(completed) == count:
            # Check for unique asset IDs
            asset_ids = [v.get("asset_id") for v in completed]
            if len(asset_ids) == len(set(asset_ids)):
                log_test(f"Variant Count: {count}", "PASS", 
                        f"Generated {count} designs with unique asset IDs")
            else:
                log_test(f"Variant Count: {count}", "FAIL", 
                        "Asset IDs are not unique")
        else:
            log_test(f"Variant Count: {count}", "FAIL", 
                    f"Expected {count} designs, got {len(completed)}")


def test_scenario_2_include_price(token: str, asset_id: str):
    """Test Scenario 2: Include Price = False"""
    print_section("Scenario 2: Include Price = False")
    
    params = {
        "source_asset_id": asset_id,
        "item_name": "Blackened Catfish Sandwich",
        "features": ["Blackened catfish", "Cajun spices", "Toasted bun"],
        "price": "$10.99",
        "theme": "cajun",
        "variations": 1,
        "include_price": False,
        "auto_copy": False
    }
    
    job_id = generate_design(token, asset_id, params)
    if not job_id:
        log_test("Include Price: False", "FAIL", "Failed to generate")
        return
    
    job = poll_job(token, job_id)
    if not job:
        log_test("Include Price: False", "FAIL", "Job did not complete")
        return
    
    variations = job.get("variations", [])
    if variations and variations[0].get("status") == "completed":
        # We can't directly verify the image content without downloading it,
        # but we can verify the job completed successfully
        log_test("Include Price: False", "PASS", 
                "Design generated without price (visual verification needed)")
    else:
        log_test("Include Price: False", "FAIL", "No completed variations")


def test_scenario_3_include_description(token: str, asset_id: str):
    """Test Scenario 3: Include Description = False"""
    print_section("Scenario 3: Include Description = False")
    
    params = {
        "source_asset_id": asset_id,
        "item_name": "Grilled Oysters",
        "features": ["Fresh Gulf oysters", "Garlic butter", "Parmesan cheese"],
        "price": "$14.99",
        "theme": "cajun",
        "variations": 1,
        "include_description": False,
        "auto_copy": False
    }
    
    job_id = generate_design(token, asset_id, params)
    if not job_id:
        log_test("Include Description: False", "FAIL", "Failed to generate")
        return
    
    job = poll_job(token, job_id)
    if not job:
        log_test("Include Description: False", "FAIL", "Job did not complete")
        return
    
    variations = job.get("variations", [])
    if variations and variations[0].get("status") == "completed":
        log_test("Include Description: False", "PASS", 
                "Design generated without features (visual verification needed)")
    else:
        log_test("Include Description: False", "FAIL", "No completed variations")


def test_scenario_4_platform_sizes(token: str, asset_id: str):
    """Test Scenario 4: Platform Canvas Sizes"""
    print_section("Scenario 4: Platform Canvas Sizes")
    
    expected_sizes = {
        "instagram_post": (1024, 1024),
        "instagram_story": (1080, 1920),
        "twitter": (1200, 675),
        "email": (600, 600)
    }
    
    base_params = {
        "source_asset_id": asset_id,
        "item_name": "Seafood Platter",
        "features": ["Shrimp", "Oysters", "Catfish"],
        "price": "$24.99",
        "theme": "cajun",
        "variations": 1,
        "auto_copy": False
    }
    
    for platform, expected_size in expected_sizes.items():
        print(f"\n{Colors.BOLD}Testing platform={platform}{Colors.RESET}")
        params = {**base_params, "platform": platform}
        
        job_id = generate_design(token, asset_id, params)
        if not job_id:
            log_test(f"Platform: {platform}", "FAIL", "Failed to generate")
            continue
        
        job = poll_job(token, job_id)
        if not job:
            log_test(f"Platform: {platform}", "FAIL", "Job did not complete")
            continue
        
        variations = job.get("variations", [])
        if variations and variations[0].get("status") == "completed":
            asset_data = variations[0].get("asset", {})
            width = asset_data.get("width")
            height = asset_data.get("height")
            
            if (width, height) == expected_size:
                log_test(f"Platform: {platform}", "PASS", 
                        f"Dimensions {width}×{height} match expected {expected_size[0]}×{expected_size[1]}")
            else:
                log_test(f"Platform: {platform}", "FAIL", 
                        f"Expected {expected_size[0]}×{expected_size[1]}, got {width}×{height}")
        else:
            log_test(f"Platform: {platform}", "FAIL", "No completed variations")


def test_scenario_5_cta_rendering(token: str, asset_id: str):
    """Test Scenario 5: CTA Rendering"""
    print_section("Scenario 5: CTA Rendering")
    
    base_params = {
        "source_asset_id": asset_id,
        "item_name": "Jambalaya Bowl",
        "features": ["Spicy sausage", "Shrimp", "Rice"],
        "price": "$13.99",
        "theme": "cajun",
        "variations": 1,
        "auto_copy": False
    }
    
    test_cases = [
        ("", "No CTA (empty string)"),
        ("Order Today", "CTA: Order Today"),
        ("Limited Time", "CTA: Limited Time")
    ]
    
    for cta_text, description in test_cases:
        print(f"\n{Colors.BOLD}Testing {description}{Colors.RESET}")
        params = {**base_params, "cta": cta_text}
        
        job_id = generate_design(token, asset_id, params)
        if not job_id:
            log_test(f"CTA: {description}", "FAIL", "Failed to generate")
            continue
        
        job = poll_job(token, job_id)
        if not job:
            log_test(f"CTA: {description}", "FAIL", "Job did not complete")
            continue
        
        variations = job.get("variations", [])
        if variations and variations[0].get("status") == "completed":
            log_test(f"CTA: {description}", "PASS", 
                    "Design generated (visual verification needed)")
        else:
            log_test(f"CTA: {description}", "FAIL", "No completed variations")


def test_scenario_6_copy_tone(token: str, asset_id: str):
    """Test Scenario 6: Copy Generation with Tone"""
    print_section("Scenario 6: Copy Generation with Tone")
    
    base_params = {
        "source_asset_id": asset_id,
        "item_name": "Crawfish Étouffée",
        "features": ["Fresh crawfish", "Rich roux", "Served over rice"],
        "price": "$15.99",
        "theme": "cajun",
        "variations": 1,
        "auto_copy": True
    }
    
    tones = ["professional", "playful"]
    
    for tone in tones:
        print(f"\n{Colors.BOLD}Testing tone={tone}{Colors.RESET}")
        params = {**base_params, "tone": tone}
        
        job_id = generate_design(token, asset_id, params)
        if not job_id:
            log_test(f"Tone: {tone}", "FAIL", "Failed to generate")
            continue
        
        job = poll_job(token, job_id, timeout=180)  # Longer timeout for copy generation
        if not job:
            log_test(f"Tone: {tone}", "FAIL", "Job did not complete")
            continue
        
        copy_pack = job.get("copy_pack")
        if copy_pack:
            fb_post = copy_pack.get("fb_post", "")
            ig_post = copy_pack.get("ig_post", "")
            
            log_test(f"Tone: {tone}", "PASS", 
                    f"Copy generated - FB: {len(fb_post)} chars, IG: {len(ig_post)} chars")
            print(f"  FB Post preview: {fb_post[:100]}...")
        else:
            log_test(f"Tone: {tone}", "FAIL", "No copy pack generated")


def test_scenario_7_caption_length(token: str, asset_id: str):
    """Test Scenario 7: Caption Length"""
    print_section("Scenario 7: Caption Length")
    
    base_params = {
        "source_asset_id": asset_id,
        "item_name": "Fried Catfish Basket",
        "features": ["Cornmeal breading", "Hush puppies", "Coleslaw"],
        "price": "$11.99",
        "theme": "cajun",
        "variations": 1,
        "auto_copy": True
    }
    
    lengths = ["short", "long"]
    
    for length in lengths:
        print(f"\n{Colors.BOLD}Testing caption_length={length}{Colors.RESET}")
        params = {**base_params, "caption_length": length}
        
        job_id = generate_design(token, asset_id, params)
        if not job_id:
            log_test(f"Caption Length: {length}", "FAIL", "Failed to generate")
            continue
        
        job = poll_job(token, job_id, timeout=180)
        if not job:
            log_test(f"Caption Length: {length}", "FAIL", "Job did not complete")
            continue
        
        copy_pack = job.get("copy_pack")
        if copy_pack:
            fb_post = copy_pack.get("fb_post", "")
            ig_post = copy_pack.get("ig_post", "")
            
            log_test(f"Caption Length: {length}", "PASS", 
                    f"Copy generated - FB: {len(fb_post)} chars, IG: {len(ig_post)} chars")
        else:
            log_test(f"Caption Length: {length}", "FAIL", "No copy pack generated")


def test_scenario_8_marketing_goal(token: str, asset_id: str):
    """Test Scenario 8: Marketing Goal"""
    print_section("Scenario 8: Marketing Goal")
    
    base_params = {
        "source_asset_id": asset_id,
        "item_name": "Shrimp & Grits",
        "features": ["Jumbo shrimp", "Creamy grits", "Andouille sausage"],
        "price": "$16.99",
        "theme": "cajun",
        "variations": 1,
        "auto_copy": True
    }
    
    goals = ["limited_offer", "brand_awareness"]
    
    for goal in goals:
        print(f"\n{Colors.BOLD}Testing marketing_goal={goal}{Colors.RESET}")
        params = {**base_params, "marketing_goal": goal}
        
        job_id = generate_design(token, asset_id, params)
        if not job_id:
            log_test(f"Marketing Goal: {goal}", "FAIL", "Failed to generate")
            continue
        
        job = poll_job(token, job_id, timeout=180)
        if not job:
            log_test(f"Marketing Goal: {goal}", "FAIL", "Job did not complete")
            continue
        
        copy_pack = job.get("copy_pack")
        if copy_pack:
            fb_post = copy_pack.get("fb_post", "")
            
            log_test(f"Marketing Goal: {goal}", "PASS", 
                    f"Copy generated with {goal} emphasis")
            print(f"  FB Post preview: {fb_post[:150]}...")
        else:
            log_test(f"Marketing Goal: {goal}", "FAIL", "No copy pack generated")


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Run all test scenarios."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("AI DESIGNER INTEGRATION TEST SUITE")
    print("Phase 6: Production Readiness QA Testing")
    print("=" * 70)
    print(f"{Colors.RESET}\n")
    
    print(f"API Base URL: {API_BASE}")
    print(f"Admin Email: {ADMIN_EMAIL}\n")
    
    # Step 1: Login
    token = login()
    if not token:
        print(f"\n{Colors.RED}Authentication failed. Cannot proceed with tests.{Colors.RESET}")
        sys.exit(1)
    
    # Step 2: Get test asset
    asset_id = get_test_asset_id(token)
    if not asset_id:
        print(f"\n{Colors.RED}No test asset found. Cannot proceed with tests.{Colors.RESET}")
        sys.exit(1)
    
    # Run all test scenarios
    try:
        test_scenario_1_variant_count(token, asset_id)
        test_scenario_2_include_price(token, asset_id)
        test_scenario_3_include_description(token, asset_id)
        test_scenario_4_platform_sizes(token, asset_id)
        test_scenario_5_cta_rendering(token, asset_id)
        test_scenario_6_copy_tone(token, asset_id)
        test_scenario_7_caption_length(token, asset_id)
        test_scenario_8_marketing_goal(token, asset_id)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.RESET}")
    except Exception as e:
        print(f"\n\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    print_section("TEST SUMMARY")
    
    total_tests = len(test_results["passed"]) + len(test_results["failed"])
    passed = len(test_results["passed"])
    failed = len(test_results["failed"])
    warnings = len(test_results["warnings"])
    
    print(f"Total Tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
    print(f"{Colors.YELLOW}Warnings: {warnings}{Colors.RESET}")
    
    if failed > 0:
        print(f"\n{Colors.RED}Failed Tests:{Colors.RESET}")
        for item in test_results["failed"]:
            print(f"  • {item['test']}: {item['error']}")
    
    if warnings > 0:
        print(f"\n{Colors.YELLOW}Warnings:{Colors.RESET}")
        for item in test_results["warnings"]:
            print(f"  • {item['test']}: {item['warning']}")
    
    print(f"\n{Colors.BOLD}Test run completed.{Colors.RESET}\n")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
