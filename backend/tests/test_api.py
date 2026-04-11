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


class TestNewsletter:
    """Newsletter subscription endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        return response.json()["token"]
    
    def test_subscribe_with_valid_email(self):
        """POST /api/newsletter/subscribe with valid email returns success"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(
            f"{BASE_URL}/api/newsletter/subscribe",
            json={"email": unique_email}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "already_subscribed" in data
        assert data["already_subscribed"] == False
        print(f"✓ Newsletter subscription successful for {unique_email}")
    
    def test_subscribe_duplicate_email(self):
        """POST /api/newsletter/subscribe with duplicate email returns already_subscribed:true"""
        # First subscribe
        unique_email = f"test_dup_{uuid.uuid4().hex[:8]}@example.com"
        requests.post(
            f"{BASE_URL}/api/newsletter/subscribe",
            json={"email": unique_email}
        )
        
        # Try to subscribe again
        response = requests.post(
            f"{BASE_URL}/api/newsletter/subscribe",
            json={"email": unique_email}
        )
        assert response.status_code == 200
        data = response.json()
        assert "already_subscribed" in data
        assert data["already_subscribed"] == True
        print(f"✓ Duplicate subscription returns already_subscribed:true")
    
    def test_subscribe_invalid_email(self):
        """POST /api/newsletter/subscribe with invalid email returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/newsletter/subscribe",
            json={"email": "invalid-email-no-at-sign"}
        )
        assert response.status_code == 400
        print("✓ Invalid email returns 400")
    
    def test_subscribe_empty_email(self):
        """POST /api/newsletter/subscribe with empty email returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/newsletter/subscribe",
            json={"email": ""}
        )
        assert response.status_code == 400
        print("✓ Empty email returns 400")
    
    def test_get_subscribers_requires_auth(self):
        """GET /api/newsletter/subscribers without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/newsletter/subscribers")
        assert response.status_code == 401
        print("✓ Get subscribers requires authentication")
    
    def test_get_subscribers_with_auth(self, auth_token):
        """GET /api/newsletter/subscribers with auth returns subscriber list"""
        response = requests.get(
            f"{BASE_URL}/api/newsletter/subscribers",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "subscribers" in data
        assert "total" in data
        assert isinstance(data["subscribers"], list)
        assert isinstance(data["total"], int)
        print(f"✓ Get subscribers returns list with {data['total']} subscribers")


class TestCateringInquiries:
    """Catering inquiry endpoint tests - NEW FEATURE"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        return response.json()["token"]
    
    def test_submit_catering_inquiry_valid(self):
        """POST /api/catering/inquiry with valid data returns success message"""
        inquiry_data = {
            "name": f"TEST_Catering_{uuid.uuid4().hex[:8]}",
            "email": f"test_catering_{uuid.uuid4().hex[:8]}@example.com",
            "phone": "(504) 555-1234",
            "event_date": "2026-03-15",
            "guest_count": "50",
            "message": "Test catering inquiry for automated testing"
        }
        response = requests.post(
            f"{BASE_URL}/api/catering/inquiry",
            json=inquiry_data
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "id" in data
        assert "24 hours" in data["message"].lower() or "thank you" in data["message"].lower()
        print(f"✓ Catering inquiry submitted successfully, id: {data['id']}")
    
    def test_submit_catering_inquiry_missing_name(self):
        """POST /api/catering/inquiry with missing name returns 400"""
        inquiry_data = {
            "name": "",
            "email": "test@example.com",
            "message": "Test message"
        }
        response = requests.post(
            f"{BASE_URL}/api/catering/inquiry",
            json=inquiry_data
        )
        assert response.status_code == 400
        print("✓ Missing name returns 400")
    
    def test_submit_catering_inquiry_missing_email(self):
        """POST /api/catering/inquiry with missing email returns 400"""
        inquiry_data = {
            "name": "Test Name",
            "email": "",
            "message": "Test message"
        }
        response = requests.post(
            f"{BASE_URL}/api/catering/inquiry",
            json=inquiry_data
        )
        assert response.status_code == 400
        print("✓ Missing email returns 400")
    
    def test_submit_catering_inquiry_missing_message(self):
        """POST /api/catering/inquiry with missing message returns 400"""
        inquiry_data = {
            "name": "Test Name",
            "email": "test@example.com",
            "message": ""
        }
        response = requests.post(
            f"{BASE_URL}/api/catering/inquiry",
            json=inquiry_data
        )
        assert response.status_code == 400
        print("✓ Missing message returns 400")
    
    def test_get_catering_inquiries_requires_auth(self):
        """GET /api/catering/inquiries without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/catering/inquiries")
        assert response.status_code == 401
        print("✓ Get catering inquiries requires authentication")
    
    def test_get_catering_inquiries_with_auth(self, auth_token):
        """GET /api/catering/inquiries with auth returns inquiry list"""
        response = requests.get(
            f"{BASE_URL}/api/catering/inquiries",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "inquiries" in data
        assert "total" in data
        assert isinstance(data["inquiries"], list)
        assert isinstance(data["total"], int)
        print(f"✓ Get catering inquiries returns list with {data['total']} inquiries")
    
    def test_update_catering_status_valid(self, auth_token):
        """PUT /api/catering/inquiries/{id}/status updates inquiry status"""
        # First create an inquiry
        inquiry_data = {
            "name": f"TEST_Status_{uuid.uuid4().hex[:8]}",
            "email": f"test_status_{uuid.uuid4().hex[:8]}@example.com",
            "message": "Test inquiry for status update"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/catering/inquiry",
            json=inquiry_data
        )
        inquiry_id = create_response.json()["id"]
        
        # Update status to 'contacted'
        update_response = requests.put(
            f"{BASE_URL}/api/catering/inquiries/{inquiry_id}/status",
            json={"status": "contacted"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert "message" in data
        print(f"✓ Updated catering inquiry status to 'contacted'")
        
        # Verify status was updated
        get_response = requests.get(
            f"{BASE_URL}/api/catering/inquiries",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        inquiries = get_response.json()["inquiries"]
        updated_inquiry = next((i for i in inquiries if i["id"] == inquiry_id), None)
        assert updated_inquiry is not None
        assert updated_inquiry["status"] == "contacted"
        print("✓ Verified status was persisted")
    
    def test_update_catering_status_invalid(self, auth_token):
        """PUT /api/catering/inquiries/{id}/status with invalid status returns 400"""
        # First create an inquiry
        inquiry_data = {
            "name": f"TEST_Invalid_{uuid.uuid4().hex[:8]}",
            "email": f"test_invalid_{uuid.uuid4().hex[:8]}@example.com",
            "message": "Test inquiry for invalid status"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/catering/inquiry",
            json=inquiry_data
        )
        inquiry_id = create_response.json()["id"]
        
        # Try to update with invalid status
        update_response = requests.put(
            f"{BASE_URL}/api/catering/inquiries/{inquiry_id}/status",
            json={"status": "invalid_status"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert update_response.status_code == 400
        print("✓ Invalid status returns 400")
    
    def test_update_catering_status_requires_auth(self):
        """PUT /api/catering/inquiries/{id}/status without auth returns 401"""
        response = requests.put(
            f"{BASE_URL}/api/catering/inquiries/some-id/status",
            json={"status": "contacted"}
        )
        assert response.status_code == 401
        print("✓ Update catering status requires authentication")
    
    def test_update_catering_status_not_found(self, auth_token):
        """PUT /api/catering/inquiries/{id}/status with non-existent id returns 404"""
        response = requests.put(
            f"{BASE_URL}/api/catering/inquiries/non-existent-id/status",
            json={"status": "contacted"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
        print("✓ Non-existent inquiry returns 404")


class TestSEOFiles:
    """SEO files accessibility tests - NEW FEATURE"""
    
    def test_robots_txt_accessible(self):
        """robots.txt is accessible at /robots.txt"""
        response = requests.get(f"{BASE_URL}/robots.txt")
        assert response.status_code == 200
        content = response.text
        assert "User-agent" in content
        assert "Disallow: /login" in content
        assert "Disallow: /dashboard" in content
        assert "Disallow: /api/" in content
        assert "Sitemap:" in content
        print("✓ robots.txt accessible with correct Disallow rules")
    
    def test_sitemap_xml_accessible(self):
        """sitemap.xml is accessible at /sitemap.xml"""
        response = requests.get(f"{BASE_URL}/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        assert "<?xml" in content
        assert "urlset" in content
        assert "loc" in content
        print("✓ sitemap.xml accessible with valid XML structure")


class TestCMSContent:
    """CMS Site Content endpoint tests - NEW CMS FEATURE"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        return response.json()["token"]
    
    def test_get_content_returns_site_content(self):
        """GET /api/content returns site content with hero, about, contact sections"""
        response = requests.get(f"{BASE_URL}/api/content")
        assert response.status_code == 200
        data = response.json()
        
        # Check all sections exist
        assert "hero" in data, "Missing hero section"
        assert "about" in data, "Missing about section"
        assert "contact" in data, "Missing contact section"
        
        # Validate hero section fields
        assert "tagline" in data["hero"], "Missing hero.tagline"
        assert "subtitle" in data["hero"], "Missing hero.subtitle"
        
        # Validate about section fields
        assert "accent_text" in data["about"], "Missing about.accent_text"
        assert "heading" in data["about"], "Missing about.heading"
        assert "paragraph1" in data["about"], "Missing about.paragraph1"
        assert "paragraph2" in data["about"], "Missing about.paragraph2"
        assert "paragraph3" in data["about"], "Missing about.paragraph3"
        assert "established_text" in data["about"], "Missing about.established_text"
        
        # Validate contact section fields
        assert "address_line1" in data["contact"], "Missing contact.address_line1"
        assert "address_line2" in data["contact"], "Missing contact.address_line2"
        assert "hours_weekday" in data["contact"], "Missing contact.hours_weekday"
        assert "hours_weekend" in data["contact"], "Missing contact.hours_weekend"
        assert "phone" in data["contact"], "Missing contact.phone"
        assert "email" in data["contact"], "Missing contact.email"
        
        print("✓ GET /api/content returns complete site content with all sections")
    
    def test_update_hero_with_auth(self, auth_token):
        """PUT /api/content/hero with auth updates hero tagline and subtitle"""
        # Get current content
        original = requests.get(f"{BASE_URL}/api/content").json()
        original_tagline = original["hero"]["tagline"]
        
        # Update hero
        new_hero = {
            "tagline": "TEST_Tagline_" + uuid.uuid4().hex[:8],
            "subtitle": "TEST_Subtitle for automated testing"
        }
        response = requests.put(
            f"{BASE_URL}/api/content/hero",
            json=new_hero,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hero"]["tagline"] == new_hero["tagline"]
        assert data["hero"]["subtitle"] == new_hero["subtitle"]
        print(f"✓ Updated hero tagline to: {new_hero['tagline']}")
        
        # Verify persistence via GET
        verify = requests.get(f"{BASE_URL}/api/content").json()
        assert verify["hero"]["tagline"] == new_hero["tagline"]
        print("✓ Verified hero update persisted")
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/content/hero",
            json={"tagline": original_tagline, "subtitle": original["hero"]["subtitle"]},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print("✓ Restored original hero content")
    
    def test_update_hero_requires_auth(self):
        """PUT /api/content/hero without auth returns 401"""
        response = requests.put(
            f"{BASE_URL}/api/content/hero",
            json={"tagline": "Unauthorized", "subtitle": "Should fail"}
        )
        assert response.status_code == 401
        print("✓ Update hero requires authentication")
    
    def test_update_about_with_auth(self, auth_token):
        """PUT /api/content/about with auth updates about section fields"""
        # Get current content
        original = requests.get(f"{BASE_URL}/api/content").json()
        
        # Update about
        new_about = {
            "accent_text": "TEST_Accent",
            "heading": "TEST_Heading_" + uuid.uuid4().hex[:8],
            "paragraph1": "TEST paragraph 1",
            "paragraph2": "TEST paragraph 2",
            "paragraph3": "TEST paragraph 3",
            "established_text": "TEST Est. 2026"
        }
        response = requests.put(
            f"{BASE_URL}/api/content/about",
            json=new_about,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["about"]["heading"] == new_about["heading"]
        print(f"✓ Updated about heading to: {new_about['heading']}")
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/content/about",
            json=original["about"],
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print("✓ Restored original about content")
    
    def test_update_contact_with_auth(self, auth_token):
        """PUT /api/content/contact with auth updates contact info"""
        # Get current content
        original = requests.get(f"{BASE_URL}/api/content").json()
        
        # Update contact
        new_contact = {
            "address_line1": "TEST_123 Test St",
            "address_line2": "Test City, TS 12345",
            "hours_weekday": "TEST Mon-Sat: 10am-10pm",
            "hours_weekend": "TEST Sun: Closed",
            "phone": "(555) 123-4567",
            "email": "test@test.com",
            "catering_text": "TEST catering text"
        }
        response = requests.put(
            f"{BASE_URL}/api/content/contact",
            json=new_contact,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["contact"]["phone"] == new_contact["phone"]
        print(f"✓ Updated contact phone to: {new_contact['phone']}")
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/content/contact",
            json=original["contact"],
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print("✓ Restored original contact content")
    
    def test_update_invalid_section(self, auth_token):
        """PUT /api/content/invalid returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/content/invalid_section",
            json={"field": "value"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400
        print("✓ Invalid section returns 400")


class TestCMSMenu:
    """CMS Menu endpoint tests - NEW CMS FEATURE"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"}
        )
        return response.json()["token"]
    
    def test_get_menu_returns_categories(self):
        """GET /api/menu returns array of menu categories with items"""
        response = requests.get(f"{BASE_URL}/api/menu")
        assert response.status_code == 200
        data = response.json()
        
        # Should be an array
        assert isinstance(data, list), "Menu should be an array"
        assert len(data) >= 10, f"Expected at least 10 categories, got {len(data)}"
        
        # Check first category structure
        first_cat = data[0]
        assert "id" in first_cat, "Missing category id"
        assert "slug" in first_cat, "Missing category slug"
        assert "display_name" in first_cat, "Missing category display_name"
        assert "items" in first_cat, "Missing category items"
        assert isinstance(first_cat["items"], list), "Items should be an array"
        
        # Check item structure if items exist
        if len(first_cat["items"]) > 0:
            first_item = first_cat["items"][0]
            assert "name" in first_item, "Missing item name"
            assert "price" in first_item, "Missing item price"
        
        print(f"✓ GET /api/menu returns {len(data)} categories")
        for cat in data:
            print(f"  - {cat['display_name']}: {len(cat.get('items', []))} items")
    
    def test_update_menu_category_with_auth(self, auth_token):
        """PUT /api/menu/{category_id} with auth updates category items"""
        # Get current menu
        menu = requests.get(f"{BASE_URL}/api/menu").json()
        first_cat = menu[0]
        cat_id = first_cat["id"]
        original_name = first_cat["display_name"]
        original_items = first_cat["items"]
        
        # Update category
        new_name = "TEST_Category_" + uuid.uuid4().hex[:8]
        response = requests.put(
            f"{BASE_URL}/api/menu/{cat_id}",
            json={"display_name": new_name},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == new_name
        print(f"✓ Updated category name to: {new_name}")
        
        # Verify persistence
        verify = requests.get(f"{BASE_URL}/api/menu").json()
        updated_cat = next((c for c in verify if c["id"] == cat_id), None)
        assert updated_cat is not None
        assert updated_cat["display_name"] == new_name
        print("✓ Verified category update persisted")
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/menu/{cat_id}",
            json={"display_name": original_name, "items": original_items},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print("✓ Restored original category")
    
    def test_update_menu_category_items(self, auth_token):
        """PUT /api/menu/{category_id} can update items array"""
        # Get current menu
        menu = requests.get(f"{BASE_URL}/api/menu").json()
        first_cat = menu[0]
        cat_id = first_cat["id"]
        original_items = first_cat["items"]
        
        # Add a test item
        new_items = original_items + [{"name": "TEST_Item", "description": "Test item", "price": "99.99"}]
        response = requests.put(
            f"{BASE_URL}/api/menu/{cat_id}",
            json={"items": new_items},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == len(new_items)
        assert any(item["name"] == "TEST_Item" for item in data["items"])
        print("✓ Added test item to category")
        
        # Restore original items
        requests.put(
            f"{BASE_URL}/api/menu/{cat_id}",
            json={"items": original_items},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print("✓ Restored original items")
    
    def test_update_menu_category_requires_auth(self):
        """PUT /api/menu/{category_id} without auth returns 401"""
        # Get a category id
        menu = requests.get(f"{BASE_URL}/api/menu").json()
        cat_id = menu[0]["id"]
        
        response = requests.put(
            f"{BASE_URL}/api/menu/{cat_id}",
            json={"display_name": "Unauthorized"}
        )
        assert response.status_code == 401
        print("✓ Update menu category requires authentication")
    
    def test_update_menu_category_not_found(self, auth_token):
        """PUT /api/menu/{category_id} with non-existent id returns 404"""
        response = requests.put(
            f"{BASE_URL}/api/menu/non-existent-id",
            json={"display_name": "Test"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
        print("✓ Non-existent category returns 404")
    
    def test_update_menu_category_no_valid_fields(self, auth_token):
        """PUT /api/menu/{category_id} with no valid fields returns 400"""
        menu = requests.get(f"{BASE_URL}/api/menu").json()
        cat_id = menu[0]["id"]
        
        response = requests.put(
            f"{BASE_URL}/api/menu/{cat_id}",
            json={"invalid_field": "value"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400
        print("✓ No valid fields returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
