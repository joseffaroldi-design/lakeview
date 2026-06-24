"""Gemini 3 Flash vision client for food-photo analysis.

Sprint 16D — single multimodal LLM call returns structured JSON:
  {food_type, confidence, features, suggested_theme, dominant_colors}

Graceful degradation: ANY exception (budget, network, timeout, bad JSON)
returns `vision_ok=False` with a short error string. The orchestrator
hands that to the UI so the owner can manually fill the fields and
continue with flyer generation.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional


# The 5 flyer themes Sprint 16A.1/16A.2 actually ship — vision MUST pick one of these.
VALID_THEMES = ["comic_pop", "vintage_diner", "bold_purple_pop",
                "casual_teal", "distressed_orange"]

log = logging.getLogger("uvicorn.error")

_SYSTEM = (
    "You are a restaurant marketing AI. Given a food photo, identify the "
    "dish and pick a flyer theme that matches its vibe. Output ONLY a valid "
    "JSON object — no markdown, no commentary."
)

_USER = (
    "Analyze this food photo and return JSON with these EXACT keys:\n"
    "  food_type: short dish name (≤60 chars). e.g. 'Smash Burger', 'Shrimp Taco'\n"
    "  confidence: 0.0–1.0 confidence in the food_type\n"
    "  features: 3–6 short ingredient/component strings. e.g. ['Cheese','Pickled Onions','Aioli']\n"
    "  suggested_theme: EXACTLY ONE of: " + ", ".join(VALID_THEMES) + "\n"
    "  dominant_colors: 3 hex strings like '#cc4422' representing the photo's palette\n"
    "Be specific about ingredients you can actually see. Avoid generic words like 'food', 'meal'."
)


def _strip_to_json(s: str) -> str:
    """LLMs sometimes wrap JSON in ```json blocks; tolerate that."""
    s = s.strip()
    m = re.search(r"\{.*\}", s, re.DOTALL)
    return m.group(0) if m else s


def _validate(d: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce loose model output into the contract we promise the UI."""
    food = str(d.get("food_type", "")).strip()[:60] or "Featured Dish"
    try:
        conf = float(d.get("confidence", 0.0))
        if conf != conf:  # NaN check
            conf = 0.0
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    feats_raw = d.get("features") or []
    if isinstance(feats_raw, str):
        feats_raw = [f.strip() for f in re.split(r"[,;\n]+", feats_raw)]
    features: List[str] = []
    for f in feats_raw:
        s = str(f).strip()[:40]
        if s and s.lower() not in ("food", "meal", "dish") and s not in features:
            features.append(s)
        if len(features) >= 6:
            break

    theme = str(d.get("suggested_theme", "")).strip().lower().replace("-", "_")
    if theme not in VALID_THEMES:
        theme = "comic_pop"  # safe default

    colors_raw = d.get("dominant_colors") or []
    colors: List[str] = []
    for c in colors_raw:
        s = str(c).strip()
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", s):
            colors.append("#" + s.lstrip("#"))
        if len(colors) >= 3:
            break

    return {
        "food_type": food,
        "confidence": conf,
        "features": features,
        "suggested_theme": theme,
        "dominant_colors": colors,
    }


async def analyze_food_photo(image_bytes: bytes,
                             *,
                             timeout: float = 25.0) -> Dict[str, Any]:
    """Call Gemini 3 Flash to classify a food photo. Always returns a dict.

    On success: {vision_ok: True, food_type, confidence, features,
                 suggested_theme, dominant_colors}
    On any failure: {vision_ok: False, error: '<short reason>',
                     ... safe defaults for the same shape}
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"vision_ok": False, "error": "EMERGENT_LLM_KEY not configured",
                **_safe_defaults()}

    try:
        from emergentintegrations.llm.chat import (
            LlmChat, UserMessage, ImageContent,
        )
    except ImportError as e:
        return {"vision_ok": False, "error": f"vision lib missing: {e}",
                **_safe_defaults()}

    chat = LlmChat(
        api_key=api_key,
        session_id=f"photo-flyer-{os.urandom(8).hex()}",
        system_message=_SYSTEM,
    ).with_model("gemini", "gemini-3-flash-preview")

    img = ImageContent(image_base64=base64.b64encode(image_bytes).decode("ascii"))
    msg = UserMessage(text=_USER, file_contents=[img])

    try:
        # Streaming response — collect to a single string. The Sprint
        # uses send_message for simpler buffering; the playbook permits
        # this for "explicit non-streaming requests" and the call is
        # internal-only (no user-facing token stream needed).
        body = await asyncio.wait_for(chat.send_message(msg), timeout=timeout)
    except asyncio.TimeoutError:
        log.warning("vision_client timeout after %.0fs", timeout)
        return {"vision_ok": False, "error": "vision timeout",
                **_safe_defaults()}
    except Exception as e:  # noqa: BLE001
        msg_text = str(e)[:200]
        log.warning("vision_client failed: %s", msg_text)
        # Specifically recognise budget-exceeded for nicer UI copy
        if "Budget has been exceeded" in msg_text or "budget" in msg_text.lower():
            return {"vision_ok": False, "error": "LLM budget exceeded",
                    **_safe_defaults()}
        return {"vision_ok": False, "error": msg_text, **_safe_defaults()}

    raw = body if isinstance(body, str) else getattr(body, "text", str(body))
    try:
        parsed = json.loads(_strip_to_json(raw))
    except json.JSONDecodeError as e:
        log.warning("vision_client got non-JSON: %r", raw[:200])
        return {"vision_ok": False, "error": f"bad json: {e}",
                **_safe_defaults()}

    validated = _validate(parsed)
    return {"vision_ok": True, **validated}


def _safe_defaults() -> Dict[str, Any]:
    return {
        "food_type": "",
        "confidence": 0.0,
        "features": [],
        "suggested_theme": "comic_pop",
        "dominant_colors": [],
    }
