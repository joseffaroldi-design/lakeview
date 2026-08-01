"""Phase 2G verification: Today's Featured rotation endpoint."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com").rstrip("/")
EP = f"{BASE_URL}/api/html-template/featured"


def test_default_returns_200_and_pool_gt_1():
    r = requests.get(EP, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pool_size"] > 1, f"pool_size={data['pool_size']} (fix regressed)"
    print(f"[default] pool_size={data['pool_size']} asset_id={data['asset_id']}")


def test_response_has_all_expected_keys():
    r = requests.get(EP, timeout=30)
    data = r.json()
    for k in ("asset_id", "item_name", "theme", "uploaded_at", "image_url", "pool_size", "rotated_for"):
        assert k in data, f"missing key {k}"
    assert data["image_url"] == f"/api/media/file/{data['asset_id']}"


def test_deterministic_same_day_same_pick():
    r1 = requests.get(EP, timeout=30).json()
    r2 = requests.get(EP, timeout=30).json()
    assert r1["asset_id"] == r2["asset_id"]
    assert r1["rotated_for"] == r2["rotated_for"]
    assert r1["pool_size"] == r2["pool_size"] > 1


def test_window_days_14_preserves_legacy_narrow_behavior():
    r = requests.get(EP, params={"window_days": 14}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    # With aged pool (>30d old), narrow window should collapse to fallback (1)
    # or at least be strictly smaller than default
    default = requests.get(EP, timeout=30).json()
    assert data["pool_size"] < default["pool_size"], (
        f"window_days=14 pool={data['pool_size']} not smaller than default={default['pool_size']}"
    )
    print(f"[window_days=14] pool_size={data['pool_size']}")


def test_window_days_0_equivalent_to_default():
    r_default = requests.get(EP, timeout=30).json()
    r_zero = requests.get(EP, params={"window_days": 0}, timeout=30).json()
    assert r_default["pool_size"] == r_zero["pool_size"]
    assert r_default["asset_id"] == r_zero["asset_id"]


def test_image_url_resolves():
    data = requests.get(EP, timeout=30).json()
    media_url = f"{BASE_URL}{data['image_url']}"
    r = requests.get(media_url, timeout=30, allow_redirects=True)
    assert r.status_code == 200, f"media file endpoint returned {r.status_code} for {media_url}"


def test_endpoint_is_public_no_auth():
    r = requests.get(EP, timeout=30)
    assert r.status_code == 200
