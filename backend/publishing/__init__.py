"""Publishing engine — provider-abstracted, multi-tenant.

Architecture:
  Publisher  (abstract interface — publish/schedule/cancel/status)
    │
    ├── FacebookProvider        (stub — wire real Graph API when keys exist)
    ├── InstagramProvider       (stub)
    ├── GoogleBusinessProvider  (stub)
    ├── MailchimpProvider       (stub)
    ├── EmailProvider           (stub — wraps SendGrid when key supplied)
    └── SmsProvider             (stub — wraps Twilio when key supplied)

  Future providers (tiktok / linkedin / x / youtube) plug in the same way.

All publishing flows go through `publish_now(connection, asset, scheduled_post)`
which dispatches to the correct provider. The router never references a
specific provider; that's strictly the registry's job.

No restaurant-specific logic lives here — providers are industry-agnostic.
"""
from .base import (
    PublishResult,
    Publisher,
    register_provider,
    get_provider,
    list_providers,
    publish_now,
)
from . import providers as _providers  # noqa: F401 — registers default providers
from .scheduler import (
    schedule_publish,
    cancel_publish,
    reschedule_publish,
    fetch_due_posts,
    run_due_publishes,
)

__all__ = [
    "PublishResult",
    "Publisher",
    "register_provider",
    "get_provider",
    "list_providers",
    "publish_now",
    "schedule_publish",
    "cancel_publish",
    "reschedule_publish",
    "fetch_due_posts",
    "run_due_publishes",
]
