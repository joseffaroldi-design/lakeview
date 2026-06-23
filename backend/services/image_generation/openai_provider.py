"""Sprint 15B.8 — OpenAI gpt-image-1 provider via emergentintegrations.

Uses the universal `EMERGENT_LLM_KEY` already loaded in the backend env
(Sprint 15B.6). No additional credential needed.

gpt-image-1 supports only three native sizes:
  * 1024x1024 (square)
  * 1024x1536 (portrait)
  * 1536x1024 (landscape)

We map the four requested aspect ratios into the closest native size.
4:5 → portrait, 9:16 → portrait (same), 16:9 → landscape, 1:1 → square.
A note on aspect ratio is added to the prompt so the model frames it
accordingly within the chosen canvas.
"""
from __future__ import annotations

import asyncio
import os
from typing import List

from .base_provider import (
    BaseImageProvider,
    GeneratedImage,
    ImageGenerationError,
)

_MODEL_ID = "gpt-image-1"
_TIMEOUT_SEC = 90

# Aspect ratio → (width, height, hint_in_prompt)
_OPENAI_SIZE_MAP = {
    "1:1":  (1024, 1024, "Square 1:1 composition."),
    "4:5":  (1024, 1536, "Vertical 4:5 portrait composition; subject occupies the upper portion."),
    "9:16": (1024, 1536, "Tall 9:16 vertical composition; framed for mobile feed."),
    "16:9": (1536, 1024, "Wide 16:9 landscape composition; horizontal banner framing."),
}


class OpenAIImageProvider(BaseImageProvider):
    name = "openai"
    model = _MODEL_ID

    @property
    def is_configured(self) -> bool:
        return bool(os.environ.get("EMERGENT_LLM_KEY"))

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str,
        n: int,
    ) -> List[GeneratedImage]:
        if not self.is_configured:
            raise ImageGenerationError(
                code="missing_credentials",
                user_message="OpenAI image generation is not configured (EMERGENT_LLM_KEY missing).",
            )

        # Lazy import keeps SDK out of the boot path.
        from emergentintegrations.llm.openai.image_generation import (  # noqa: PLC0415
            OpenAIImageGeneration,
        )

        ratio = self.normalize_ratio(aspect_ratio)
        width, height, ratio_hint = _OPENAI_SIZE_MAP[ratio]
        framed_prompt = f"{prompt}\n\n{ratio_hint}"

        try:
            gen = OpenAIImageGeneration(api_key=os.environ["EMERGENT_LLM_KEY"])
            # The library returns a list of raw bytes. We request `n` in a
            # single call — far cheaper than n separate HTTP round-trips.
            images = await asyncio.wait_for(
                gen.generate_images(
                    prompt=framed_prompt,
                    model=_MODEL_ID,
                    number_of_images=n,
                ),
                timeout=_TIMEOUT_SEC * n,  # generous; single call returns all
            )
        except asyncio.TimeoutError as exc:
            raise ImageGenerationError(
                code="provider_timeout",
                user_message="OpenAI took too long to respond. Try again.",
                detail=f"timed out after {_TIMEOUT_SEC * n}s",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "401" in msg or "unauthor" in msg or "invalid_api_key" in msg:
                raise ImageGenerationError(
                    code="invalid_api_key",
                    user_message="OpenAI API key was rejected. Check EMERGENT_LLM_KEY.",
                    detail=str(exc)[:300],
                ) from exc
            if "429" in msg or "rate_limit" in msg or "quota" in msg or "billing" in msg:
                raise ImageGenerationError(
                    code="quota_exceeded",
                    user_message=(
                        "OpenAI quota exceeded. Top up at Profile → Universal Key → Add Balance."
                    ),
                    detail=str(exc)[:300],
                ) from exc
            if "content_policy" in msg or "safety" in msg or "moderation" in msg:
                raise ImageGenerationError(
                    code="invalid_prompt",
                    user_message=(
                        "OpenAI rejected the prompt for content policy. Try a milder phrasing."
                    ),
                    detail=str(exc)[:300],
                ) from exc
            raise ImageGenerationError(
                code="provider_error",
                user_message="OpenAI had a temporary issue. Try again in a moment.",
                detail=str(exc)[:300],
            ) from exc

        if not images:
            raise ImageGenerationError(
                code="empty_response",
                user_message="OpenAI returned no image. Try a different prompt.",
            )

        return [
            GeneratedImage(
                data=img,
                mime="image/png",
                width=width,
                height=height,
                provider=self.name,
                model=_MODEL_ID,
            )
            for img in images
        ]
