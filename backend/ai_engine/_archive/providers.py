"""Provider abstraction layer.

The system functions even when no image or video provider is connected.
Image / Video providers are STUBS — they emit concept artifacts now and can
be wired to real APIs (OpenAI Images, Ideogram, Flux, Runway, Veo, etc.)
later by implementing the interfaces below.

Text providers go through ai_engine.client (emergentintegrations w/ runtime
model swap), which already supports openai / anthropic / gemini.
"""
from typing import Any, Dict, List, Optional


# Registry of providers per capability — used by the Settings panel UI.
CAPABILITIES = {
    "text": {
        "available": [
            {"provider": "openai", "model": "gpt-5", "label": "GPT-5", "default": True},
            {"provider": "openai", "model": "gpt-5-mini", "label": "GPT-5 mini (cheap)"},
            {"provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "label": "Claude Sonnet 4.5"},
            {"provider": "gemini", "model": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
            {"provider": "gemini", "model": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
        ],
        "enabled": True,
    },
    "image": {
        "available": [
            {"provider": "openai", "model": "gpt-image-1", "label": "OpenAI GPT Image 1"},
            {"provider": "gemini", "model": "gemini-2.5-flash-image", "label": "Gemini Nano Banana"},
            {"provider": "ideogram", "model": "ideogram-v3", "label": "Ideogram v3 (BYO key)"},
            {"provider": "flux", "model": "flux-pro-1.1", "label": "Flux Pro 1.1 (BYO key)"},
        ],
        "enabled": False,  # Concept-only until a provider is wired
    },
    "video": {
        "available": [
            {"provider": "openai", "model": "sora-2", "label": "Sora 2"},
            {"provider": "runway", "model": "gen-3-alpha", "label": "Runway Gen-3 (BYO key)"},
            {"provider": "google", "model": "veo-3", "label": "Google Veo 3 (BYO key)"},
            {"provider": "kling", "model": "kling-1.6", "label": "Kling 1.6 (BYO key)"},
            {"provider": "pika", "model": "pika-2.0", "label": "Pika 2.0 (BYO key)"},
        ],
        "enabled": False,
    },
}


def list_providers(capability: str) -> Dict[str, Any]:
    cap = CAPABILITIES.get(capability)
    if not cap:
        return {"available": [], "enabled": False}
    return cap


async def get_setting(db, key: str, default: Any = None) -> Any:
    """Generic settings getter — `ai_settings` collection with id = key."""
    doc = await db.ai_settings.find_one({"_id": key}, {"_id": 0})
    if not doc:
        return default
    return doc.get("value", default)


async def set_setting(db, key: str, value: Any) -> Any:
    await db.ai_settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)
    return value


# -------- Image/Video stubs --------
# When you wire real providers, implement these and flip CAPABILITIES[*]["enabled"].

async def generate_image(prompt: str, *, provider: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """Stub: returns prompt echo. Real implementation goes here."""
    return {
        "status": "not_implemented",
        "message": "Image generation provider not connected. See ai_engine/providers.py to wire one.",
        "prompt": prompt,
    }


async def generate_video(prompt: str, *, provider: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    return {
        "status": "not_implemented",
        "message": "Video generation provider not connected. See ai_engine/providers.py to wire one.",
        "prompt": prompt,
    }
