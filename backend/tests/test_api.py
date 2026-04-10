"""
Backend API Tests for Lakeview Burgers & Seafood
Tests: Auth, Analytics, Specials CRUD, Tracking endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndRoot:
    """Basic health check and root endpoint tests"""
    
    def test_root_returns_hello_world(self):
        """GET /api/ returns Hello World"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Hello World"
        print("✓ Root endpoint returns Hello World")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_with_correct_password(self):
        """POST /api/auth/login with password 'Lakeview872' returns token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0
        print(f"✓ Login successful, token received: {data['token'][:20]}...")
    
    def test_login_with_wrong_password(self):
        """POST /api/auth/login with wrong password returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "wrongpassword"}
        )
        assert response.status_code == 401
        print("✓ Login with wrong password returns 401")
    
    def test_verify_with_valid_token(self):
        """GET /api/auth/verify with valid Bearer token returns authenticated:true"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        token = login_response.json()["token"]
        
        # Verify with token
        response = requests.get(
            f"{BASE_URL}/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "authenticated" in data
        assert data["authenticated"] == True
        print("✓ Auth verify with valid token returns authenticated:true")
    
    def test_verify_without_token(self):
        """GET /api/auth/verify without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/verify")
        assert response.status_code == 401
        print("✓ Auth verify without token returns 401")


class TestAnalytics:
    """Analytics endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        return response.json()["token"]
    
    def test_analytics_requires_auth(self):
        """GET /api/analytics without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/analytics")
        assert response.status_code == 401
        print("✓ Analytics endpoint requires authentication")
    
    def test_analytics_returns_complete_data(self, auth_token):
        """GET /api/analytics with valid Bearer token returns complete analytics JSON"""
        response = requests.get(
            f"{BASE_URL}/api/analytics",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check all expected fields exist
        expected_fields = [
            "total_views", "views_today", "views_this_week", "views_this_month",
            "unique_sessions", "unique_sessions_today", "page_breakdown",
            "device_breakdown", "browser_breakdown", "hourly_views_today",
            "daily_views_week", "top_referrers", "avg_pages_per_session",
            "button_clicks", "button_clicks_today"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate data types
        assert isinstance(data["total_views"], int)
        assert isinstance(data["views_today"], int)
        assert isinstance(data["views_this_week"], int)
        assert isinstance(data["views_this_month"], int)
        assert isinstance(data["unique_sessions"], int)
        assert isinstance(data["unique_sessions_today"], int)
        assert isinstance(data["page_breakdown"], dict)
        assert isinstance(data["device_breakdown"], dict)
        assert isinstance(data["browser_breakdown"], dict)
        assert isinstance(data["hourly_views_today"], dict)
        assert isinstance(data["daily_views_week"], dict)
        assert isinstance(data["top_referrers"], dict)
        assert isinstance(data["avg_pages_per_session"], (int, float))
        assert isinstance(data["button_clicks"], dict)
        assert isinstance(data["button_clicks_today"], dict)
        
        print("✓ Analytics returns complete data with all expected fields")


class TestTracking:
    """Analytics tracking endpoint tests"""
    
    def test_track_pageview(self):
        """POST /api/analytics/track correctly tracks a pageview"""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/analytics/track",
            json={
                "page": "test_page",
                "user_agent": "Mozilla/5.0 (Test Browser)",
                "referrer": "https://test-referrer.com",
                "session_id": session_id,
                "screen_width": 1920,
                "screen_height": 1080
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Page view tracked"
        print("✓ Page view tracking works correctly")
    
    def test_track_button_click(self):
        """POST /api/analytics/button-click correctly tracks button click"""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/analytics/button-click",
            json={
                "button_name": "test_button",
                "session_id": session_id
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Button click tracked"
        print("✓ Button click tracking works correctly")


class TestSpecials:
    """Specials CRUD endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        return response.json()["token"]
    
    def test_get_specials_public(self):
        """GET /api/specials returns array (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/specials")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/specials returns array with {len(data)} items")
    
    def test_create_and_delete_special(self, auth_token):
        """POST /api/specials with auth creates a special, DELETE /api/specials/{id} deletes it"""
        # Create a special
        special_data = {
            "title": "TEST_Special_" + uuid.uuid4().hex[:8],
            "description": "Test special description for automated testing",
            "price": "$9.99"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/specials",
            json=special_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 200
        created_special = create_response.json()
        
        # Validate created special
        assert "id" in created_special
        assert created_special["title"] == special_data["title"]
        assert created_special["description"] == special_data["description"]
        assert created_special["price"] == special_data["price"]
        print(f"✓ Created special with id: {created_special['id']}")
        
        special_id = created_special["id"]
        
        # Verify it exists via GET
        get_response = requests.get(f"{BASE_URL}/api/specials/{special_id}")
        assert get_response.status_code == 200
        fetched_special = get_response.json()
        assert fetched_special["title"] == special_data["title"]
        print("✓ Verified special exists via GET")
        
        # Delete the special
        delete_response = requests.delete(
            f"{BASE_URL}/api/specials/{special_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert delete_response.status_code == 200
        print("✓ Deleted special successfully")
        
        # Verify it's deleted
        verify_response = requests.get(f"{BASE_URL}/api/specials/{special_id}")
        assert verify_response.status_code == 404
        print("✓ Verified special is deleted (404)")
    
    def test_create_special_requires_auth(self):
        """POST /api/specials without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/specials",
            json={
                "title": "Unauthorized Special",
                "description": "Should fail"
            }
        )
        assert response.status_code == 401
        print("✓ Create special requires authentication")
    
    def test_update_special(self, auth_token):
        """PUT /api/specials/{id} updates a special"""
        # Create a special first
        special_data = {
            "title": "TEST_Update_" + uuid.uuid4().hex[:8],
            "description": "Original description",
            "price": "$5.99"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/specials",
            json=special_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        special_id = create_response.json()["id"]
        
        # Update the special
        update_data = {"title": "Updated Title", "price": "$7.99"}
        update_response = requests.put(
            f"{BASE_URL}/api/specials/{special_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert update_response.status_code == 200
        updated_special = update_response.json()
        assert updated_special["title"] == "Updated Title"
        assert updated_special["price"] == "$7.99"
        print("✓ Updated special successfully")
        
        # Cleanup - delete the special
        requests.delete(
            f"{BASE_URL}/api/specials/{special_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print("✓ Cleaned up test special")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
