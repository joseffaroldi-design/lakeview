"""Iteration 33: Sprint V1.0 Follow-up 2 backend verification."""
import os
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://upload-stage-two.preview.emergentagent.com').rstrip('/')
ADMIN_PASSWORD = '83CeLOZJQbOcopK0yYmNtdRQg4VPii8o'


@pytest.fixture(scope='module')
def admin_token():
    r = requests.post(f'{BASE_URL}/api/auth/login', json={'password': ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f'Login failed: {r.status_code} {r.text}'
    return r.json().get('token') or r.json().get('session_token') or r.json().get('access_token')


# ---- Public endpoints ----
@pytest.mark.parametrize('path', [
    '/api/content',
    '/api/menu',
    '/api/homepage/layout',
    '/api/specials?active_only=true',
    '/api/html-template/featured',
])
def test_public_endpoints_200(path):
    r = requests.get(f'{BASE_URL}{path}', timeout=15)
    assert r.status_code == 200, f'{path} => {r.status_code}'


# ---- Flyer share analytics ----
def test_flyer_share_track_and_list(admin_token):
    payload = {
        'item_key': 'testitem',
        'item_name': 'Test',
        'theme': 'burger_classic',
        'platform': 'instagram',
    }
    r = requests.post(f'{BASE_URL}/api/analytics/flyer-share', json=payload, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get('ok') is True
    assert data.get('tracked') is True

    # List
    headers = {'Authorization': f'Bearer {admin_token}'} if admin_token else {}
    r2 = requests.get(f'{BASE_URL}/api/analytics/flyer-shares', headers=headers, timeout=15)
    assert r2.status_code == 200, r2.text
    payload2 = r2.json()
    items = payload2.get('items', [])
    match = [i for i in items if i.get('item_key') == 'testitem']
    assert match, f'testitem not found in items list: {items[:5]}'
    assert match[0].get('share_count', 0) >= 1


def test_flyer_share_missing_item_key():
    r = requests.post(f'{BASE_URL}/api/analytics/flyer-share', json={}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get('ok') is True
    assert d.get('tracked') is False
