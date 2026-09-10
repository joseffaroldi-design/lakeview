from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_public_pages_send_page_view_beacons():
    src = (ROOT / "frontend/src/PublicSite.jsx").read_text()
    assert "const usePageViewBeacon = (page) =>" in src
    assert "sessionStorage.getItem(\"visitor_session\")" in src
    assert "axios.post(`${API}/analytics/track`" in src
    assert "usePageViewBeacon(\"/\")" in src
    assert "usePageViewBeacon(\"/menu\")" in src


def test_analytics_retention_covers_page_views_and_button_clicks():
    router = (ROOT / "backend/routers/analytics.py").read_text()
    server = (ROOT / "backend/server.py").read_text()
    assert "doc['expires_at'] = datetime.now(timezone.utc) + timedelta(days=180)" in router
    assert router.count("doc['expires_at'] = datetime.now(timezone.utc) + timedelta(days=180)") >= 2
    assert "db.button_clicks.create_index" in server
    assert 'name="bc_ttl"' in server
