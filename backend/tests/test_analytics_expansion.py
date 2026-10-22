from models import ButtonClickData, TrackingData
from routers.analytics import (
    event_category,
    is_bot,
    parse_user_agent,
    referrer_domain,
    sanitize_metadata,
    traffic_source,
)


def test_user_agent_classification_is_coarse_and_useful():
    iphone = "Mozilla/5.0 (iPhone) AppleWebKit/605.1 Mobile Safari/604.1"
    desktop_edge = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit Chrome/120 Safari/537 Edg/120"
    assert parse_user_agent(iphone) == ("mobile", "Safari")
    assert parse_user_agent(desktop_edge) == ("desktop", "Edge")
    assert parse_user_agent("") == ("unknown", "unknown")


def test_sources_referrers_and_bots_are_normalized():
    assert referrer_domain("https://www.google.com/search?q=lakeview") == "www.google.com"
    assert traffic_source("Facebook", None) == "facebook"
    assert traffic_source(None, "https://lakeviewburgersandseafood.com/menu") == "internal"
    assert traffic_source(None, None) == "direct"
    assert is_bot("Mozilla/5.0 Googlebot/2.1") is True
    assert is_bot("Mozilla/5.0 Safari/605.1") is False


def test_event_categories_cover_restaurant_conversions():
    assert event_category("order_online_header") == "order_pickup"
    assert event_category("delivery_click") == "delivery"
    assert event_category("call_visit_click") == "phone"
    assert event_category("directions_click") == "directions"
    assert event_category("catering_inquiry_submit") == "catering"
    assert event_category("menu_category_view") == "menu_interest"
    assert event_category("mobile_nav_home") == "navigation"


def test_metadata_is_bounded_and_nested_values_are_rejected():
    cleaned = sanitize_metadata({
        "duration_seconds": 12,
        "scroll_depth": 83.5,
        "placement": "h" * 500,
        "nested": {"customer": "must not be stored"},
        "items": ["must not be stored"],
    })
    assert cleaned["duration_seconds"] == 12
    assert cleaned["scroll_depth"] == 83.5
    assert len(cleaned["placement"]) == 200
    assert "nested" not in cleaned
    assert "items" not in cleaned


def test_tracking_models_accept_new_anonymous_context():
    page = TrackingData(
        page="/menu",
        session_id="session-1",
        visitor_id="visitor-1",
        utm_source="instagram",
        utm_campaign="fall-special",
    )
    event = ButtonClickData(
        button_name="menu_category_view",
        visitor_id="visitor-1",
        page="/menu",
        metadata={"category": "Burgers"},
    )
    assert page.visitor_id == "visitor-1"
    assert page.utm_campaign == "fall-special"
    assert event.metadata == {"category": "Burgers"}
