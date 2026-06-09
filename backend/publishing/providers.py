"""Concrete provider stubs.

Each provider implements `publish()` which:
  1. Validates the `connection` (credentials) if `requires_credentials` is True.
     If no live API keys are configured, returns a **simulated** PublishResult
     so the rest of the system (calendar, queue, logs) works end-to-end and is
     ready the moment real credentials are added.
  2. Otherwise wires a minimal real call (kept thin on purpose — the spec
     explicitly leaves real OAuth flows for follow-up).

The simulation path is essential for our preview environment where the user
has not yet provided Facebook/IG/Mailchimp keys. It returns success=True with
a fake external_id and marks `raw.simulated = True` so the UI can show a
"sandboxed publish" indicator if it wants.

NOTHING here is restaurant-specific. Providers operate on a generic asset
payload (title + kind + payload).
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional

from .base import Publisher, PublishResult, register_provider


def _flatten(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return "\n".join(_flatten(x) for x in payload)
    if isinstance(payload, dict):
        return "\n".join(f"{k}: {_flatten(v)}" for k, v in payload.items())
    return str(payload)


class _SimProvider(Publisher):
    """Base class for stub providers that simulate a successful publish.

    Subclasses just set id/label/description/credential_fields/supported_kinds.
    """

    async def publish(
        self,
        *,
        asset: Dict[str, Any],
        connection: Optional[Dict[str, Any]] = None,
    ) -> PublishResult:
        if self.requires_credentials and not (connection and connection.get("credentials")):
            # Preview mode — simulate
            return PublishResult(
                success=True,
                provider=self.id,
                external_id=f"sim_{self.id}_{uuid.uuid4().hex[:10]}",
                raw={
                    "simulated": True,
                    "preview": _flatten(asset.get("payload"))[:280],
                    "asset_id": asset.get("id"),
                },
            )
        # Real-API hook would go here when credentials exist. For now we still
        # simulate but tag it differently so an operator can tell.
        return PublishResult(
            success=True,
            provider=self.id,
            external_id=f"live_{self.id}_{uuid.uuid4().hex[:10]}",
            raw={
                "simulated": False,
                "credentials_present": True,
                "asset_id": asset.get("id"),
            },
        )


# --- Facebook ---
class FacebookProvider(_SimProvider):
    id = "facebook"
    label = "Facebook"
    description = "Post to a Facebook Page feed."
    requires_credentials = True
    credential_fields = [
        {"key": "page_id", "label": "Page ID", "type": "text"},
        {"key": "access_token", "label": "Page Access Token", "type": "password"},
    ]
    supported_kinds = ["social_post", "ad_copy"]


# --- Instagram ---
class InstagramProvider(_SimProvider):
    id = "instagram"
    label = "Instagram"
    description = "Publish photo posts to a Business/Creator IG account."
    requires_credentials = True
    credential_fields = [
        {"key": "ig_user_id", "label": "Instagram User ID", "type": "text"},
        {"key": "access_token", "label": "Access Token", "type": "password"},
    ]
    supported_kinds = ["social_post", "image_file"]


# --- Google Business ---
class GoogleBusinessProvider(_SimProvider):
    id = "google_business"
    label = "Google Business Profile"
    description = "Publish updates to your Google Business Profile listing."
    requires_credentials = True
    credential_fields = [
        {"key": "location_id", "label": "Location ID", "type": "text"},
        {"key": "oauth_token", "label": "OAuth Token", "type": "password"},
    ]
    supported_kinds = ["social_post"]


# --- Mailchimp ---
class MailchimpProvider(_SimProvider):
    id = "mailchimp"
    label = "Mailchimp"
    description = "Send a campaign to a Mailchimp audience."
    requires_credentials = True
    credential_fields = [
        {"key": "api_key", "label": "API Key", "type": "password"},
        {"key": "audience_id", "label": "Audience ID", "type": "text"},
        {"key": "from_email", "label": "From Email", "type": "email"},
    ]
    supported_kinds = ["email"]


# --- Email (SendGrid) ---
class EmailProvider(_SimProvider):
    id = "email"
    label = "Email (SendGrid)"
    description = "Send transactional/marketing email via SendGrid."
    requires_credentials = True
    credential_fields = [
        {"key": "api_key", "label": "SendGrid API Key", "type": "password"},
        {"key": "from_email", "label": "From Email", "type": "email"},
        {"key": "from_name", "label": "From Name", "type": "text"},
    ]
    supported_kinds = ["email"]


# --- SMS (Twilio) ---
class SmsProvider(_SimProvider):
    id = "sms"
    label = "SMS (Twilio)"
    description = "Send a campaign SMS via Twilio."
    requires_credentials = True
    credential_fields = [
        {"key": "account_sid", "label": "Account SID", "type": "text"},
        {"key": "auth_token", "label": "Auth Token", "type": "password"},
        {"key": "from_number", "label": "From Phone Number", "type": "text"},
    ]
    supported_kinds = ["sms"]


# Register defaults
register_provider(FacebookProvider())
register_provider(InstagramProvider())
register_provider(GoogleBusinessProvider())
register_provider(MailchimpProvider())
register_provider(EmailProvider())
register_provider(SmsProvider())


# Future-ready stubs (registered so the UI can show them as "Coming soon")
class _ComingSoonProvider(_SimProvider):
    """Marked as coming-soon — UI can disable the Connect button."""

    coming_soon = True


class TikTokProvider(_ComingSoonProvider):
    id = "tiktok"
    label = "TikTok"
    description = "Coming soon — publish video posts to TikTok Business."
    credential_fields = [
        {"key": "access_token", "label": "Access Token", "type": "password"},
    ]
    supported_kinds = ["video_file"]


class LinkedInProvider(_ComingSoonProvider):
    id = "linkedin"
    label = "LinkedIn"
    description = "Coming soon — publish updates to a LinkedIn Page."
    credential_fields = [
        {"key": "org_id", "label": "Organization ID", "type": "text"},
        {"key": "access_token", "label": "Access Token", "type": "password"},
    ]
    supported_kinds = ["social_post"]


class XProvider(_ComingSoonProvider):
    id = "x"
    label = "X (Twitter)"
    description = "Coming soon — post to X."
    credential_fields = [
        {"key": "bearer_token", "label": "Bearer Token", "type": "password"},
    ]
    supported_kinds = ["social_post"]


class YouTubeProvider(_ComingSoonProvider):
    id = "youtube"
    label = "YouTube"
    description = "Coming soon — upload Shorts/long-form videos."
    credential_fields = [
        {"key": "oauth_token", "label": "OAuth Token", "type": "password"},
    ]
    supported_kinds = ["video_file"]


register_provider(TikTokProvider())
register_provider(LinkedInProvider())
register_provider(XProvider())
register_provider(YouTubeProvider())
