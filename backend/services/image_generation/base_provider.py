"""Sprint 15B.8 — abstract image-provider contract.

Each concrete provider (Flux, OpenAI gpt-image-1, future Imagen/Ideogram)
implements `generate()` returning a list of `GeneratedImage` records.
Routers and the factory only depend on this base class.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


class ImageGenerationError(Exception):
    """Single exception type for the entire image-gen stack.

    Carries an owner-friendly `user_message` plus a stable `code` so the
    router can decide HTTP status without sniffing the message string.
    """

    def __init__(self, code: str, user_message: str, detail: str | None = None) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.detail = detail


@dataclass(frozen=True)
class GeneratedImage:
    """One generated image, returned from a provider as raw bytes."""

    data: bytes              # PNG bytes
    mime: str                # "image/png" or "image/jpeg"
    width: int               # pixels
    height: int              # pixels
    provider: str            # "flux" | "openai"
    model: str               # e.g. "fal-ai/flux-pro/v1.1"
    seed: int | None = None  # provider-supplied seed when available


class BaseImageProvider:
    """Abstract base. Concrete providers MUST override `generate()`."""

    name: str = "base"  # short id used in logs + /api/media/health
    model: str = ""     # human-readable model id

    @property
    def is_configured(self) -> bool:
        """Return True if this provider has the credentials it needs.

        Default impl returns False so a misconfigured subclass never
        accidentally passes the factory's gate.
        """
        return False

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str,
        n: int,
    ) -> List[GeneratedImage]:
        raise NotImplementedError

    # Helper used by both providers to coerce arbitrary aspect-ratio strings
    # into the supported set.  Routers validate inputs once at the edge but
    # providers should also be defensive.
    SUPPORTED_RATIOS = {"1:1", "4:5", "9:16", "16:9"}

    @classmethod
    def normalize_ratio(cls, ratio: str) -> str:
        return ratio if ratio in cls.SUPPORTED_RATIOS else "1:1"
