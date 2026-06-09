"""Real provider implementations.

Each `publish()` does a real HTTP call to the platform API when credentials
are present. When credentials are missing, returns a CLEAR ERROR (not a
silent simulated success) — the operator must connect the provider in the
Provider Connections UI before publishing will work.

Stored fields on success (in scheduled_posts.external_id + .raw):
  - external_post_id  → the platform-specific post ID
  - published_url     → human-clickable URL when available
  - publish_timestamp → ISO 8601 UTC of platform's response time
  - provider_response → trimmed copy of the platform's JSON for debugging
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from .base import Publisher, PublishResult, register_provider


def _flatten(payload: Any, limit: int = 4000) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload[:limit]
    if isinstance(payload, list):
        return "\n".join(_flatten(x) for x in payload)[:limit]
    if isinstance(payload, dict):
        # Prefer a "caption"/"body"/"text"/"copy" field if present.
        for key in ("caption", "body", "text", "copy", "headline", "subject"):
            if key in payload and isinstance(payload[key], str):
                return payload[key][:limit]
        return "\n".join(f"{k}: {_flatten(v)}" for k, v in payload.items())[:limit]
    return str(payload)[:limit]


def _missing(field_list, creds):
    return [f for f in field_list if not (creds.get(f) or "").strip()]


def _err(provider: str, msg: str) -> PublishResult:
    return PublishResult(success=False, provider=provider, error=msg)


def _need_connect(provider: str) -> PublishResult:
    return _err(
        provider,
        f"No connection configured for '{provider}'. "
        f"Open AI Ads → Providers and connect {provider} before publishing."
    )


# ============================================================
#                    FACEBOOK PAGE FEED
# ============================================================
class FacebookProvider(Publisher):
    id = "facebook"
    label = "Facebook"
    description = "Post to a Facebook Page feed (Graph API v19.0)."
    requires_credentials = True
    credential_fields = [
        {"key": "page_id", "label": "Page ID", "type": "text"},
        {"key": "access_token", "label": "Page Access Token", "type": "password"},
    ]
    supported_kinds = ["social_post", "ad_copy"]

    async def publish(self, *, asset, connection=None) -> PublishResult:
        if not (connection and connection.get("credentials")):
            return _need_connect(self.id)
        creds = connection["credentials"]
        miss = _missing(["page_id", "access_token"], creds)
        if miss:
            return _err(self.id, f"Missing credentials: {', '.join(miss)}")
        text = _flatten(asset.get("payload"))
        url = f"https://graph.facebook.com/v19.0/{creds['page_id']}/feed"
        try:
            async with httpx.AsyncClient(timeout=20.0) as cli:
                r = await cli.post(url, data={"message": text, "access_token": creds["access_token"]})
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text}
            if r.status_code >= 400:
                err = (data.get("error") or {}).get("message") or r.text[:200]
                return _err(self.id, f"Facebook API error: {err}")
            post_id = data.get("id", "")
            published_url = f"https://www.facebook.com/{post_id}" if post_id else None
            return PublishResult(
                success=True, provider=self.id,
                external_id=post_id or None,
                published_at=datetime.now(timezone.utc).isoformat(),
                raw={
                    "external_post_id": post_id, "published_url": published_url,
                    "provider_response": data, "simulated": False,
                },
            )
        except httpx.HTTPError as e:
            return _err(self.id, f"Network error: {e}")


# ============================================================
#                    INSTAGRAM (Business)
# ============================================================
# Posting an image to IG requires 2 calls: (1) create media container with
# image_url + caption, (2) publish container. We assume the asset payload
# carries an `image_url`; for caption-only posts the call returns a clear error.
class InstagramProvider(Publisher):
    id = "instagram"
    label = "Instagram"
    description = "Publish to a Business/Creator IG account (Graph API)."
    requires_credentials = True
    credential_fields = [
        {"key": "ig_user_id", "label": "Instagram User ID", "type": "text"},
        {"key": "access_token", "label": "Access Token", "type": "password"},
    ]
    supported_kinds = ["social_post", "image_file"]

    async def publish(self, *, asset, connection=None) -> PublishResult:
        if not (connection and connection.get("credentials")):
            return _need_connect(self.id)
        creds = connection["credentials"]
        miss = _missing(["ig_user_id", "access_token"], creds)
        if miss:
            return _err(self.id, f"Missing credentials: {', '.join(miss)}")
        payload = asset.get("payload") or {}
        image_url = (payload.get("image_url") if isinstance(payload, dict) else None) or asset.get("image_url")
        caption = _flatten(payload, 2200)
        if not image_url:
            return _err(self.id, "Instagram requires an image_url on the asset payload (Reels/Story not yet supported).")
        base = f"https://graph.facebook.com/v19.0/{creds['ig_user_id']}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as cli:
                # 1) create media container
                r1 = await cli.post(f"{base}/media",
                                    data={"image_url": image_url, "caption": caption,
                                          "access_token": creds["access_token"]})
                d1 = r1.json()
                if r1.status_code >= 400:
                    return _err(self.id, f"IG media container error: {(d1.get('error') or {}).get('message', r1.text[:200])}")
                container_id = d1.get("id")
                if not container_id:
                    return _err(self.id, "IG did not return a media container id.")
                # 2) publish
                r2 = await cli.post(f"{base}/media_publish",
                                    data={"creation_id": container_id, "access_token": creds["access_token"]})
                d2 = r2.json()
                if r2.status_code >= 400:
                    return _err(self.id, f"IG publish error: {(d2.get('error') or {}).get('message', r2.text[:200])}")
                post_id = d2.get("id", "")
                return PublishResult(
                    success=True, provider=self.id,
                    external_id=post_id or None,
                    published_at=datetime.now(timezone.utc).isoformat(),
                    raw={
                        "external_post_id": post_id,
                        "published_url": f"https://www.instagram.com/p/{post_id}" if post_id else None,
                        "provider_response": d2, "simulated": False,
                    },
                )
        except httpx.HTTPError as e:
            return _err(self.id, f"Network error: {e}")


# ============================================================
#                    GOOGLE BUSINESS PROFILE
# ============================================================
class GoogleBusinessProvider(Publisher):
    id = "google_business"
    label = "Google Business Profile"
    description = "Post updates to your Google Business Profile listing."
    requires_credentials = True
    credential_fields = [
        {"key": "location_id", "label": "Location ID (accounts/X/locations/Y)", "type": "text"},
        {"key": "oauth_token", "label": "OAuth Access Token", "type": "password"},
    ]
    supported_kinds = ["social_post"]

    async def publish(self, *, asset, connection=None) -> PublishResult:
        if not (connection and connection.get("credentials")):
            return _need_connect(self.id)
        creds = connection["credentials"]
        miss = _missing(["location_id", "oauth_token"], creds)
        if miss:
            return _err(self.id, f"Missing credentials: {', '.join(miss)}")
        text = _flatten(asset.get("payload"), 1500)
        url = f"https://mybusiness.googleapis.com/v4/{creds['location_id']}/localPosts"
        try:
            async with httpx.AsyncClient(timeout=20.0) as cli:
                r = await cli.post(
                    url,
                    json={"languageCode": "en-US", "summary": text, "topicType": "STANDARD"},
                    headers={"Authorization": f"Bearer {creds['oauth_token']}",
                             "Content-Type": "application/json"},
                )
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text}
            if r.status_code >= 400:
                msg = (data.get("error") or {}).get("message") or r.text[:200]
                return _err(self.id, f"Google Business API error: {msg}")
            return PublishResult(
                success=True, provider=self.id,
                external_id=data.get("name", "") or None,
                published_at=datetime.now(timezone.utc).isoformat(),
                raw={"external_post_id": data.get("name"), "provider_response": data, "simulated": False},
            )
        except httpx.HTTPError as e:
            return _err(self.id, f"Network error: {e}")


# ============================================================
#                    MAILCHIMP
# ============================================================
class MailchimpProvider(Publisher):
    id = "mailchimp"
    label = "Mailchimp"
    description = "Create + send a Mailchimp regular campaign."
    requires_credentials = True
    credential_fields = [
        {"key": "api_key", "label": "API Key (key-dcN format)", "type": "password"},
        {"key": "audience_id", "label": "Audience (List) ID", "type": "text"},
        {"key": "from_email", "label": "From Email", "type": "email"},
        {"key": "from_name", "label": "From Name", "type": "text"},
    ]
    supported_kinds = ["email"]

    async def publish(self, *, asset, connection=None) -> PublishResult:
        if not (connection and connection.get("credentials")):
            return _need_connect(self.id)
        creds = connection["credentials"]
        miss = _missing(["api_key", "audience_id", "from_email"], creds)
        if miss:
            return _err(self.id, f"Missing credentials: {', '.join(miss)}")
        if "-" not in creds["api_key"]:
            return _err(self.id, "Mailchimp api_key must be in the form 'xxxxxxxx-usN'")
        dc = creds["api_key"].split("-")[-1]
        base = f"https://{dc}.api.mailchimp.com/3.0"
        payload = asset.get("payload") or {}
        if isinstance(payload, dict):
            subject = payload.get("subject") or asset.get("title") or "Lakeview Update"
            body = payload.get("body") or _flatten(payload)
        else:
            subject = asset.get("title") or "Lakeview Update"
            body = _flatten(payload)
        auth = ("any", creds["api_key"])
        try:
            async with httpx.AsyncClient(timeout=30.0, auth=auth) as cli:
                # 1) Create campaign
                r1 = await cli.post(f"{base}/campaigns", json={
                    "type": "regular",
                    "recipients": {"list_id": creds["audience_id"]},
                    "settings": {
                        "subject_line": subject[:150],
                        "title": (asset.get("title") or subject)[:100],
                        "from_name": creds.get("from_name") or "Lakeview Burgers & Seafood",
                        "reply_to": creds["from_email"],
                    },
                })
                d1 = r1.json()
                if r1.status_code >= 400:
                    return _err(self.id, f"Mailchimp create error: {d1.get('detail') or d1.get('title') or r1.text[:200]}")
                cid = d1.get("id")
                # 2) Set content
                r2 = await cli.put(f"{base}/campaigns/{cid}/content", json={"html": f"<div>{body}</div>", "plain_text": body})
                if r2.status_code >= 400:
                    return _err(self.id, f"Mailchimp content error: {r2.text[:200]}")
                # 3) Send
                r3 = await cli.post(f"{base}/campaigns/{cid}/actions/send")
                if r3.status_code >= 400:
                    return _err(self.id, f"Mailchimp send error: {r3.text[:200]}")
                return PublishResult(
                    success=True, provider=self.id,
                    external_id=cid,
                    published_at=datetime.now(timezone.utc).isoformat(),
                    raw={"external_post_id": cid, "campaign": d1, "simulated": False},
                )
        except httpx.HTTPError as e:
            return _err(self.id, f"Network error: {e}")


# ============================================================
#                    EMAIL (SendGrid)
# ============================================================
class EmailProvider(Publisher):
    id = "email"
    label = "Email (SendGrid)"
    description = "Send a marketing email via SendGrid v3."
    requires_credentials = True
    credential_fields = [
        {"key": "api_key", "label": "SendGrid API Key", "type": "password"},
        {"key": "from_email", "label": "From Email", "type": "email"},
        {"key": "from_name", "label": "From Name", "type": "text"},
        {"key": "recipients", "label": "Recipient list (comma-separated)", "type": "text"},
    ]
    supported_kinds = ["email"]

    async def publish(self, *, asset, connection=None) -> PublishResult:
        if not (connection and connection.get("credentials")):
            return _need_connect(self.id)
        creds = connection["credentials"]
        miss = _missing(["api_key", "from_email", "recipients"], creds)
        if miss:
            return _err(self.id, f"Missing credentials: {', '.join(miss)}")
        recipients = [e.strip() for e in creds["recipients"].split(",") if e.strip()]
        if not recipients:
            return _err(self.id, "No recipients configured.")
        payload = asset.get("payload") or {}
        if isinstance(payload, dict):
            subject = payload.get("subject") or asset.get("title") or "Lakeview Update"
            body = payload.get("body") or _flatten(payload)
        else:
            subject = asset.get("title") or "Lakeview Update"
            body = _flatten(payload)
        try:
            async with httpx.AsyncClient(timeout=20.0) as cli:
                r = await cli.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {creds['api_key']}",
                             "Content-Type": "application/json"},
                    json={
                        "personalizations": [{"to": [{"email": e} for e in recipients]}],
                        "from": {"email": creds["from_email"], "name": creds.get("from_name") or "Lakeview"},
                        "subject": subject[:150],
                        "content": [{"type": "text/plain", "value": body}],
                    },
                )
            if r.status_code >= 400:
                return _err(self.id, f"SendGrid error {r.status_code}: {r.text[:200]}")
            msg_id = r.headers.get("X-Message-Id", "")
            return PublishResult(
                success=True, provider=self.id, external_id=msg_id or None,
                published_at=datetime.now(timezone.utc).isoformat(),
                raw={"external_post_id": msg_id, "recipients": len(recipients), "simulated": False},
            )
        except httpx.HTTPError as e:
            return _err(self.id, f"Network error: {e}")


# ============================================================
#                    SMS (Twilio)
# ============================================================
class SmsProvider(Publisher):
    id = "sms"
    label = "SMS (Twilio)"
    description = "Send SMS via Twilio REST API."
    requires_credentials = True
    credential_fields = [
        {"key": "account_sid", "label": "Account SID", "type": "text"},
        {"key": "auth_token", "label": "Auth Token", "type": "password"},
        {"key": "from_number", "label": "From Phone Number (E.164)", "type": "text"},
        {"key": "to_numbers", "label": "Default recipients (comma-separated E.164)", "type": "text"},
    ]
    supported_kinds = ["sms"]

    async def publish(self, *, asset, connection=None) -> PublishResult:
        if not (connection and connection.get("credentials")):
            return _need_connect(self.id)
        creds = connection["credentials"]
        miss = _missing(["account_sid", "auth_token", "from_number", "to_numbers"], creds)
        if miss:
            return _err(self.id, f"Missing credentials: {', '.join(miss)}")
        body = _flatten(asset.get("payload"), 320)
        recipients = [n.strip() for n in creds["to_numbers"].split(",") if n.strip()]
        if not recipients:
            return _err(self.id, "No SMS recipients configured.")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{creds['account_sid']}/Messages.json"
        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0,
                                         auth=(creds["account_sid"], creds["auth_token"])) as cli:
                for to in recipients:
                    r = await cli.post(url, data={"From": creds["from_number"], "To": to, "Body": body})
                    if r.status_code >= 400:
                        results.append({"to": to, "error": r.text[:200]})
                    else:
                        results.append({"to": to, "sid": r.json().get("sid")})
            ok = [r for r in results if "sid" in r]
            if not ok:
                return _err(self.id, f"All SMS sends failed. Sample: {results[0] if results else 'no recipients'}")
            return PublishResult(
                success=True, provider=self.id,
                external_id=ok[0]["sid"],
                published_at=datetime.now(timezone.utc).isoformat(),
                raw={"sent": len(ok), "failed": len(results) - len(ok), "results": results, "simulated": False},
            )
        except httpx.HTTPError as e:
            return _err(self.id, f"Network error: {e}")


# ---- Register real providers (override the simulated ones) ----
register_provider(FacebookProvider())
register_provider(InstagramProvider())
register_provider(GoogleBusinessProvider())
register_provider(MailchimpProvider())
register_provider(EmailProvider())
register_provider(SmsProvider())
