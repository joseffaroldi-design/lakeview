"""Provider connection testers.

For each registered provider, a `test()` returns:
  {ok: bool, message: str, latency_ms: int, details: dict}

Test calls are READ-ONLY (no posts/sends). They only verify the credential
can authenticate against the platform.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx


def _missing(fields, creds):
    return [f for f in fields if not (creds.get(f) or "").strip()]


def _ok(message, t0, **details):
    return {"ok": True, "message": message, "latency_ms": int((time.time() - t0) * 1000), "details": details}


def _fail(message, t0, **details):
    return {"ok": False, "message": message, "latency_ms": int((time.time() - t0) * 1000), "details": details}


async def test_facebook(creds: Dict[str, str]) -> Dict[str, Any]:
    t0 = time.time()
    miss = _missing(["page_id", "access_token"], creds)
    if miss:
        return _fail(f"Missing fields: {', '.join(miss)}", t0)
    url = f"https://graph.facebook.com/v19.0/{creds['page_id']}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(url, params={"fields": "name,id", "access_token": creds["access_token"]})
        if r.status_code == 200:
            d = r.json()
            return _ok(f"Page '{d.get('name', d.get('id'))}' authenticated.", t0, page=d)
        return _fail(f"Facebook returned {r.status_code}: {r.text[:200]}", t0)
    except httpx.HTTPError as e:
        return _fail(f"Network error: {e}", t0)


async def test_instagram(creds: Dict[str, str]) -> Dict[str, Any]:
    t0 = time.time()
    miss = _missing(["ig_user_id", "access_token"], creds)
    if miss:
        return _fail(f"Missing fields: {', '.join(miss)}", t0)
    url = f"https://graph.facebook.com/v19.0/{creds['ig_user_id']}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(url, params={"fields": "username,id", "access_token": creds["access_token"]})
        if r.status_code == 200:
            d = r.json()
            return _ok(f"IG '@{d.get('username', d.get('id'))}' authenticated.", t0, account=d)
        return _fail(f"Instagram returned {r.status_code}: {r.text[:200]}", t0)
    except httpx.HTTPError as e:
        return _fail(f"Network error: {e}", t0)


async def test_google_business(creds: Dict[str, str]) -> Dict[str, Any]:
    t0 = time.time()
    miss = _missing(["location_id", "oauth_token"], creds)
    if miss:
        return _fail(f"Missing fields: {', '.join(miss)}", t0)
    url = f"https://mybusiness.googleapis.com/v4/{creds['location_id']}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(url, headers={"Authorization": f"Bearer {creds['oauth_token']}"})
        if r.status_code == 200:
            return _ok("Google Business location accessible.", t0, location=r.json())
        return _fail(f"Google returned {r.status_code}: {r.text[:200]}", t0)
    except httpx.HTTPError as e:
        return _fail(f"Network error: {e}", t0)


async def test_mailchimp(creds: Dict[str, str]) -> Dict[str, Any]:
    t0 = time.time()
    miss = _missing(["api_key", "audience_id"], creds)
    if miss:
        return _fail(f"Missing fields: {', '.join(miss)}", t0)
    if "-" not in creds["api_key"]:
        return _fail("api_key must be of the form '...-usN'", t0)
    dc = creds["api_key"].split("-")[-1]
    url = f"https://{dc}.api.mailchimp.com/3.0/lists/{creds['audience_id']}"
    try:
        async with httpx.AsyncClient(timeout=15.0, auth=("any", creds["api_key"])) as cli:
            r = await cli.get(url)
        if r.status_code == 200:
            d = r.json()
            return _ok(f"Audience '{d.get('name', creds['audience_id'])}' ({d.get('stats', {}).get('member_count', '?')} members).", t0)
        return _fail(f"Mailchimp returned {r.status_code}: {r.text[:200]}", t0)
    except httpx.HTTPError as e:
        return _fail(f"Network error: {e}", t0)


async def test_email_sendgrid(creds: Dict[str, str]) -> Dict[str, Any]:
    t0 = time.time()
    if not (creds.get("api_key") or "").strip():
        return _fail("Missing fields: api_key", t0)
    # Hit the API-key scope endpoint — proves the key is valid without sending mail.
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(
                "https://api.sendgrid.com/v3/scopes",
                headers={"Authorization": f"Bearer {creds['api_key']}"},
            )
        if r.status_code == 200:
            scopes = r.json().get("scopes", [])
            ok_send = "mail.send" in scopes
            return _ok(
                f"SendGrid key valid ({len(scopes)} scopes; can send: {ok_send}).",
                t0,
                scopes_count=len(scopes), can_send=ok_send,
            )
        return _fail(f"SendGrid returned {r.status_code}: {r.text[:200]}", t0)
    except httpx.HTTPError as e:
        return _fail(f"Network error: {e}", t0)


async def test_sms_twilio(creds: Dict[str, str]) -> Dict[str, Any]:
    t0 = time.time()
    miss = _missing(["account_sid", "auth_token"], creds)
    if miss:
        return _fail(f"Missing fields: {', '.join(miss)}", t0)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{creds['account_sid']}.json"
    try:
        async with httpx.AsyncClient(timeout=15.0, auth=(creds["account_sid"], creds["auth_token"])) as cli:
            r = await cli.get(url)
        if r.status_code == 200:
            d = r.json()
            return _ok(f"Twilio account '{d.get('friendly_name', creds['account_sid'])}' active.", t0, status=d.get("status"))
        return _fail(f"Twilio returned {r.status_code}: {r.text[:200]}", t0)
    except httpx.HTTPError as e:
        return _fail(f"Network error: {e}", t0)


TESTERS = {
    "facebook": test_facebook,
    "instagram": test_instagram,
    "google_business": test_google_business,
    "mailchimp": test_mailchimp,
    "email": test_email_sendgrid,
    "sms": test_sms_twilio,
}


async def run_test(provider: str, creds: Dict[str, str]) -> Dict[str, Any]:
    tester = TESTERS.get(provider)
    if not tester:
        return {"ok": False, "message": f"No tester for '{provider}'.", "latency_ms": 0, "details": {}}
    return await tester(creds or {})
