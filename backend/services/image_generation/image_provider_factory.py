"""Sprint 15B.8 — image-provider factory + capability probe.

The factory enforces the user mandate:
  * Flux is the **preferred** provider when `FAL_KEY` is set.
  * OpenAI is the **default** provider whenever Flux is unavailable —
    no errors are raised at boot, no errors when generation is requested,
    no missing-credential 500s in the dashboard.
  * If neither provider is configured the factory raises a clear
    `ImageGenerationError` that the router translates to HTTP 503.

`available_providers()` is exposed for `/api/media/health` so the admin
sees at a glance which engine is active.
"""
from __future__ import annotations

import os
from typing import Dict, List

from .base_provider import BaseImageProvider, ImageGenerationError
from .flux_provider import FluxProvider
from .openai_provider import OpenAIImageProvider


# Singleton instances — providers themselves are stateless beyond their
# credential check, so reusing them avoids per-request construction.
_FLUX = FluxProvider()
_OPENAI = OpenAIImageProvider()


def get_image_provider(prefer: str | None = None) -> BaseImageProvider:
    """Return the active image provider.

    Selection order:
      1. `prefer` argument when explicitly set AND that provider is configured
      2. Flux when `FAL_KEY` is present
      3. OpenAI when `EMERGENT_LLM_KEY` is present (the steady-state default)

    Raises `ImageGenerationError(code='no_provider')` only when BOTH are unconfigured.
    """
    if prefer == "flux" and _FLUX.is_configured:
        return _FLUX
    if prefer == "openai" and _OPENAI.is_configured:
        return _OPENAI

    if _FLUX.is_configured:
        return _FLUX
    if _OPENAI.is_configured:
        return _OPENAI

    raise ImageGenerationError(
        code="no_provider",
        user_message=(
            "No image-generation provider is configured. Add EMERGENT_LLM_KEY or "
            "FAL_KEY to backend env."
        ),
    )


def available_providers() -> Dict[str, object]:
    """Diagnostic for /api/media/health.

    Returns shape:
      {
        "active": "flux" | "openai" | None,
        "providers": [
          {"name": "flux",   "configured": bool, "model": str},
          {"name": "openai", "configured": bool, "model": str},
        ]
      }
    """
    providers: List[Dict[str, object]] = [
        {"name": _FLUX.name,   "configured": _FLUX.is_configured,   "model": _FLUX.model},
        {"name": _OPENAI.name, "configured": _OPENAI.is_configured, "model": _OPENAI.model},
    ]
    active: str | None = None
    try:
        active = get_image_provider().name
    except ImageGenerationError:
        active = None
    return {
        "active": active,
        "providers": providers,
        "fal_key_loaded": bool(os.environ.get("FAL_KEY")),
        "emergent_llm_key_loaded": bool(os.environ.get("EMERGENT_LLM_KEY")),
    }
