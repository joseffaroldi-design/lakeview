"""Regression tests for /api/media/usage and /api/media/bulk-delete."""
import io
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _fresh_ip() -> str:
    return f"203.0.113.{uuid.uuid4().int % 250 + 1}"


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=15,
    )
    assert r.status_code == 200
    return r.json()["token"]


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _upload_marker_image(token: str) -> str:
    """Upload a tiny 1x1 PNG so we have a real asset to play with."""
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
        b"\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc"
        b"\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x9a\x87\xa4\xa9\x00\x00\x00"
        b"\x00IEND\xaeB`\x82"
    )
    files = {"file": (f"regression-{uuid.uuid4().hex}.png", io.BytesIO(png), "image/png")}
    data = {"folder": "Custom"}
    r = requests.post(f"{BASE_URL}/api/media/upload", files=files, data=data,
                      headers=_hdr(token), timeout=30)
    assert r.status_code == 200, r.text[:200]
    return r.json()["id"]


class TestAuth:
    def test_usage_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/media/usage", json={}, timeout=10)
        assert r.status_code == 401

    def test_bulk_delete_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/media/bulk-delete", json={}, timeout=10)
        assert r.status_code == 401


class TestUsage:
    def test_usage_reports_site_image_reference(self, admin_token):
        aid = _upload_marker_image(admin_token)
        # Assign to a site-image slot
        requests.put(
            f"{BASE_URL}/api/site-images/catering",
            json={"asset_id": aid},
            headers=_hdr(admin_token),
            timeout=10,
        ).raise_for_status()
        try:
            r = requests.post(
                f"{BASE_URL}/api/media/usage",
                json={"asset_ids": [aid]},
                headers=_hdr(admin_token),
                timeout=10,
            )
            assert r.status_code == 200
            usage = r.json()["usage"]
            assert aid in usage
            refs = usage[aid]
            assert any(x["type"] == "site_image" and x["label"] == "catering" for x in refs)
        finally:
            requests.post(
                f"{BASE_URL}/api/site-images/catering/reset",
                headers=_hdr(admin_token),
                timeout=10,
            )
            requests.post(
                f"{BASE_URL}/api/media/bulk-delete",
                json={"asset_ids": [aid], "force": True},
                headers=_hdr(admin_token),
                timeout=10,
            )

    def test_usage_reports_menu_item_reference(self, admin_token):
        aid = _upload_marker_image(admin_token)

        # Attach to the first menu category's first item.
        cats = requests.get(f"{BASE_URL}/api/menu", timeout=10).json()
        assert cats, "No menu categories in DB"
        cat = cats[0]
        original_items = cat.get("items") or []
        assert original_items, "First category has no items"

        # Preserve everything else exactly — only append a `photos` field.
        new_items = [dict(it) for it in original_items]
        new_items[0]["photos"] = [aid]

        requests.put(
            f"{BASE_URL}/api/menu/{cat['id']}",
            json={
                "display_name": cat.get("display_name"),
                "subtitle": cat.get("subtitle"),
                "columns": cat.get("columns"),
                "items": new_items,
            },
            headers=_hdr(admin_token),
            timeout=10,
        ).raise_for_status()

        try:
            r = requests.post(
                f"{BASE_URL}/api/media/usage",
                json={"asset_ids": [aid]},
                headers=_hdr(admin_token),
                timeout=10,
            )
            assert r.status_code == 200
            usage = r.json()["usage"]
            assert aid in usage
            assert any(x["type"] == "menu_item" for x in usage[aid])
        finally:
            # Restore original items exactly.
            requests.put(
                f"{BASE_URL}/api/menu/{cat['id']}",
                json={
                    "display_name": cat.get("display_name"),
                    "subtitle": cat.get("subtitle"),
                    "columns": cat.get("columns"),
                    "items": original_items,
                },
                headers=_hdr(admin_token),
                timeout=10,
            )
            requests.post(
                f"{BASE_URL}/api/media/bulk-delete",
                json={"asset_ids": [aid], "force": True},
                headers=_hdr(admin_token),
                timeout=10,
            )


class TestBulkDelete:
    def test_only_unused_skips_referenced(self, admin_token):
        used = _upload_marker_image(admin_token)
        unused = _upload_marker_image(admin_token)
        requests.put(
            f"{BASE_URL}/api/site-images/about",
            json={"asset_id": used},
            headers=_hdr(admin_token),
            timeout=10,
        ).raise_for_status()
        try:
            r = requests.post(
                f"{BASE_URL}/api/media/bulk-delete",
                json={"asset_ids": [used, unused], "only_unused": True, "force": False},
                headers=_hdr(admin_token),
                timeout=10,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["deleted"] == 1
            assert used in body["skipped_referenced"]
            assert unused not in body["skipped_referenced"]
        finally:
            requests.post(
                f"{BASE_URL}/api/site-images/about/reset",
                headers=_hdr(admin_token),
                timeout=10,
            )
            requests.post(
                f"{BASE_URL}/api/media/bulk-delete",
                json={"asset_ids": [used], "force": True},
                headers=_hdr(admin_token),
                timeout=10,
            )

    def test_force_deletes_referenced_and_slot_falls_back(self, admin_token):
        aid = _upload_marker_image(admin_token)
        requests.put(
            f"{BASE_URL}/api/site-images/tacos",
            json={"asset_id": aid},
            headers=_hdr(admin_token),
            timeout=10,
        ).raise_for_status()
        # Force delete
        r = requests.post(
            f"{BASE_URL}/api/media/bulk-delete",
            json={"asset_ids": [aid], "force": True},
            headers=_hdr(admin_token),
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["deleted"] == 1
        # Site-images GET must now return null for that slot
        r2 = requests.get(f"{BASE_URL}/api/site-images", timeout=10)
        assert r2.json()["slots"]["tacos"] is None
        # Cleanup
        requests.post(
            f"{BASE_URL}/api/site-images/tacos/reset",
            headers=_hdr(admin_token),
            timeout=10,
        )

    def test_refuses_force_without_explicit_ids(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/media/bulk-delete",
            json={"asset_ids": [], "force": True},
            headers=_hdr(admin_token),
            timeout=10,
        )
        assert r.status_code == 400
