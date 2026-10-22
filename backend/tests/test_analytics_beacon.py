from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_public_pages_send_page_view_beacons():
    src = (ROOT / "frontend/src/PublicSite.jsx").read_text()
    assert "const usePageViewBeacon = (page) =>" in src
    assert "sessionStorage.getItem(\"visitor_session\")" in src
    assert "localStorage.getItem(\"lakeview_visitor_id\")" in src
    assert "axios.post(`${API}/analytics/track`" in src
    assert "`${API}/analytics/event`" in src
    assert 'button_name: "page_engagement"' in src
    assert "usePageViewBeacon(\"/\")" in src
    assert "usePageViewBeacon(\"/menu\")" in src


def test_analytics_retention_covers_page_views_and_button_clicks():
    router = (ROOT / "backend/routers/analytics.py").read_text()
    server = (ROOT / "backend/server.py").read_text()
    retention_assignment = 'doc["expires_at"] = datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS)'
    assert "RETENTION_DAYS = 180" in router
    assert router.count(retention_assignment) >= 2
    assert "db.button_clicks.create_index" in server
    assert 'name="bc_ttl"' in server


def test_backend_analytics_reports_acquisition_engagement_and_conversions():
    router = (ROOT / "backend/routers/analytics.py").read_text()
    expected_sections = [
        '"daily_views"',
        '"landing_pages"',
        '"exit_pages"',
        '"source_breakdown"',
        '"campaign_breakdown"',
        '"viewport_breakdown"',
        '"event_category_breakdown"',
        '"conversion_funnel"',
        '"conversion_rates"',
        '"engagement"',
        '"business_outcomes"',
    ]
    for section in expected_sections:
        assert section in router
    assert '@router.post("/analytics/event")' in router
    assert 'BUSINESS_TIMEZONE = ZoneInfo("America/Chicago")' in router


def test_analytics_collection_remains_privacy_conscious():
    router = (ROOT / "backend/routers/analytics.py").read_text()
    models = (ROOT / "backend/models.py").read_text()
    assert "request.client.host" not in router
    assert "ip_address" not in router
    assert "referrer=referrer_domain(data.referrer)" in router
    assert "visitor_id" in models
    assert "utm_campaign" in models
    assert "metadata: Dict[str, Any]" in models
