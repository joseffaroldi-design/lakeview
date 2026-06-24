"""Deterministic PIL photo enhancement.

Sprint 16D — improves a food photo without altering its semantic content:
  - auto contrast (white-balance via channel autoexpand)
  - exposure normalization
  - saturation bump
  - unsharp mask
  - mild noise reduction (median filter, radius=1)

No LLM, no img2img. Same input → same output, every time.
"""
from __future__ import annotations

import io
from typing import Tuple

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


MAX_DIMENSION = 2400  # cap to keep enhancement cheap; flyer needs ≤1080 anyway


def enhance_photo(src_bytes: bytes,
                  *,
                  max_dim: int = MAX_DIMENSION) -> Tuple[bytes, dict]:
    """Enhance a food photo deterministically. Returns (jpeg_bytes, info).

    info: {'mode': 'enhanced', 'src_size': (w,h), 'out_size': (w,h)}

    The function NEVER alters the food itself — only the global tone curve,
    saturation, and sharpness. Realism is preserved.
    """
    with Image.open(io.BytesIO(src_bytes)) as img:
        img.load()
        src_size = img.size
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Down-cap to a sane max dimension for fast PIL work.
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        # 1. Auto-contrast (channel autoexpand) — fixes flat / underexposed shots
        img = ImageOps.autocontrast(img, cutoff=1)

        # 2. Slight saturation bump (1.15x) — makes food look fresher
        img = ImageEnhance.Color(img).enhance(1.15)

        # 3. Light contrast boost (1.10x)
        img = ImageEnhance.Contrast(img).enhance(1.10)

        # 4. Light brightness lift (1.05x) — counter dim restaurant lighting
        img = ImageEnhance.Brightness(img).enhance(1.05)

        # 5. Unsharp mask — bring out food texture
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))

        # 6. Mild denoise — radius-1 median, only after sharpening
        img = img.filter(ImageFilter.MedianFilter(size=3))

        # Re-apply a tiny sharpen pass to recover edges lost to denoise
        img = ImageEnhance.Sharpness(img).enhance(1.10)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue(), {
            "mode": "enhanced",
            "src_size": src_size,
            "out_size": img.size,
        }
