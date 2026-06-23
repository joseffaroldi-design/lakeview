"""Sprint 15B.8 — Fal AI Flux Pro provider.

Uses `fal-ai/flux-pro/v1.1` — chosen for restaurant food photography:
  * v1.1 has the highest texture and lighting fidelity in Fal's catalog
  * ~$0.05 per image — sits comfortably under v1.1-ultra ($0.06) for
    social-media use cases where 2K resolution is unnecessary
  * Same async API as the rest of the Flux family — easy to swap later

Aspect-ratio mapping is explicit so we never depend on Fal's default.
The provider is silently disabled when `FAL_KEY` is absent — the factory
then falls back to OpenAI without raising.
"""
from __future__ import annotations

import asyncio
import os
from typing import List

import httpx

from .base_provider import (
    BaseImageProvider,
    GeneratedImage,
    ImageGenerationError,
)
from .style_presets import build_prompt

# Aspect-ratio → (width, height) for Flux Pro. Numbers chosen to match
# the model's native multiples-of-32 grid while staying close to the
# requested ratio.
_FLUX_SIZE_MAP = {
    "1:1":  (1024, 1024),
    "4:5":  (1024, 1280),
    "9:16": (768,  1344),
    "16:9": (1344, 768),
}

_MODEL_ID = "fal-ai/flux-pro/v1.1"
_TIMEOUT_SEC = 90  # individual variation; full request is 4× this concurrently


class FluxProvider(BaseImageProvider):
    name = "flux"
    model = _MODEL_ID

    @property
    def is_configured(self) -> bool:
        return bool(os.environ.get("FAL_KEY"))

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str,
        n: int,
    ) -> List[GeneratedImage]:
        if not self.is_configured:
            raise ImageGenerationError(
                code="missing_credentials",
                user_message="Flux is not configured on this account. Switching to default provider.",
            )

        # Lazy import — keeps `fal_client` off the import path when the
        # provider is disabled. Saves ~30 MB resident memory on boot.
        import fal_client  # noqa: PLC0415

        ratio = self.normalize_ratio(aspect_ratio)
        width, height = _FLUX_SIZE_MAP[ratio]
        scaffolded, negative = build_prompt(style_key="", raw_prompt=prompt)
        # When called via router, build_prompt happens at job-creation time
        # and `prompt` is already scaffolded; this re-scaffold is a no-op
        # for unknown style keys.

        async def _one(idx: int) -> GeneratedImage:
            try:
                handler = await fal_client.submit_async(
                    _MODEL_ID,
                    arguments={
                        "prompt": prompt,
                        "image_size": {"width": width, "height": height},
                        "num_images": 1,
                        "enable_safety_checker": True,
                        "safety_tolerance": "2",
                        # Flux Pro accepts an empty list for negative_prompt
                        # — we keep the negative phrasing in the positive
                        # prompt instead since Flux follows it well.
                    },
                )
                result = await asyncio.wait_for(handler.get(), timeout=_TIMEOUT_SEC)
            except asyncio.TimeoutError as exc:
                raise ImageGenerationError(
                    code="provider_timeout",
                    user_message=(
                        "Flux took too long to respond. Try again or switch to the default provider."
                    ),
                    detail=f"variation {idx} timed out after {_TIMEOUT_SEC}s",
                ) from exc
            except Exception as exc:  # noqa: BLE001
                # Fal client raises generic errors with quota / key hints in
                # the string. Surface a clean message; preserve detail for logs.
                msg = str(exc).lower()
                if "401" in msg or "unauthor" in msg or "api_key" in msg:
                    raise ImageGenerationError(
                        code="invalid_api_key",
                        user_message="Flux API key was rejected. Check FAL_KEY in your env config.",
                        detail=str(exc)[:300],
                    ) from exc
                if "quota" in msg or "credit" in msg or "429" in msg:
                    raise ImageGenerationError(
                        code="quota_exceeded",
                        user_message="Flux account is out of credits. Top up at fal.ai/dashboard.",
                        detail=str(exc)[:300],
                    ) from exc
                raise ImageGenerationError(
                    code="provider_error",
                    user_message="Flux had a temporary issue. Try again in a moment.",
                    detail=str(exc)[:300],
                ) from exc

            images = result.get("images") or []
            if not images:
                raise ImageGenerationError(
                    code="empty_response",
                    user_message="Flux returned no image. Try a different prompt.",
                )
            url = images[0].get("url")
            if not url:
                raise ImageGenerationError(
                    code="empty_response",
                    user_message="Flux returned an empty image URL. Try again.",
                )

            # Download the bytes ourselves — Fal returns a CDN URL.
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            return GeneratedImage(
                data=resp.content,
                mime=resp.headers.get("content-type", "image/png"),
                width=width,
                height=height,
                provider=self.name,
                model=_MODEL_ID,
                seed=result.get("seed"),
            )

        # Run all variations concurrently. Flux handles parallel submits
        # cleanly via its async client.
        return await asyncio.gather(*[_one(i) for i in range(n)])
