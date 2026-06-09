"""Publisher base interface + registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PublishResult:
    success: bool
    provider: str
    external_id: Optional[str] = None
    error: Optional[str] = None                  # plain string (legacy / provider-raw)
    structured_error: Optional[Dict[str, Any]] = None  # StructuredError.to_payload()
    raw: Dict[str, Any] = field(default_factory=dict)
    published_at: Optional[str] = None


class Publisher:
    """Abstract publisher contract.

    Concrete providers override `publish()` (and optionally `schedule()`).
    `schedule()` defaults to "store-and-poll": the backend stores the
    scheduled_post and the background worker calls `publish()` when due.
    """

    id: str = ""
    label: str = ""
    description: str = ""
    requires_credentials: bool = True
    credential_fields: List[Dict[str, Any]] = []
    supported_kinds: List[str] = []

    async def publish(
        self,
        *,
        asset: Dict[str, Any],
        connection: Optional[Dict[str, Any]] = None,
    ) -> PublishResult:
        raise NotImplementedError

    async def status(self, *, external_id: str, connection: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"external_id": external_id, "status": "unknown"}

    def to_public(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "requires_credentials": self.requires_credentials,
            "credential_fields": self.credential_fields,
            "supported_kinds": self.supported_kinds,
        }


# ---- Registry ----
_REGISTRY: Dict[str, Publisher] = {}


def register_provider(provider: Publisher) -> Publisher:
    _REGISTRY[provider.id] = provider
    return provider


def get_provider(provider_id: str) -> Optional[Publisher]:
    return _REGISTRY.get(provider_id)


def list_providers() -> List[Dict[str, Any]]:
    return [p.to_public() for p in _REGISTRY.values()]


async def publish_now(
    *,
    provider_id: str,
    asset: Dict[str, Any],
    connection: Optional[Dict[str, Any]] = None,
) -> PublishResult:
    from errors import classify_publish_error
    provider = get_provider(provider_id)
    if not provider:
        msg = f"Provider '{provider_id}' not registered"
        err = classify_publish_error(provider_id, msg)
        return PublishResult(success=False, provider=provider_id, error=msg,
                             structured_error=err.to_payload())
    try:
        result = await provider.publish(asset=asset, connection=connection)
        if not result.published_at:
            result.published_at = datetime.now(timezone.utc).isoformat()
        # If the provider returned a failure with no structured_error, classify the raw string.
        if not result.success and not result.structured_error:
            err = classify_publish_error(provider_id, result.error or "")
            result.structured_error = err.to_payload()
        return result
    except Exception as e:  # noqa: BLE001
        err = classify_publish_error(provider_id, str(e))
        return PublishResult(success=False, provider=provider_id, error=str(e),
                             structured_error=err.to_payload())
