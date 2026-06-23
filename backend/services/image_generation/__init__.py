"""Sprint 15B.8 — Image generation service package.

Provides a provider-agnostic API for generating images via external AI
services. The package is structured for production safety:

  * No provider is imported eagerly at module load; the factory picks the
    available one at request time and falls back gracefully if a primary
    provider's credentials are missing.
  * Bytes returned from providers are pushed into the existing Emergent
    Object Storage (`storage.put_bytes`) — no new persistence layer.
  * Errors are mapped to owner-friendly messages so the dashboard never
    leaks stack traces.

Public surface:
  * `get_image_provider()`         — factory; returns the active provider.
  * `available_providers()`        — diagnostic; used by /api/media/health.
  * `STYLE_PRESETS`                — list[dict] of named prompt scaffolds.
  * `ImageGenerationError`         — single exception type bubbled to routers.
"""
from .base_provider import BaseImageProvider, ImageGenerationError, GeneratedImage
from .image_provider_factory import get_image_provider, available_providers
from .style_presets import STYLE_PRESETS, build_prompt

__all__ = [
    "BaseImageProvider",
    "ImageGenerationError",
    "GeneratedImage",
    "get_image_provider",
    "available_providers",
    "STYLE_PRESETS",
    "build_prompt",
]
