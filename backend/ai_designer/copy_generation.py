"""
Copy Generation Module

Marketing copy writing with LLM.
Technical Debt Reduction Sprint Step 3 - Extracted from ai_designer.py
"""

from typing import Dict, List, Optional, Any
from database import get_db


async def write_designer_copy(
    item_name: str,
    features: List[str],
    price: Optional[str],
    theme_label: str,
    tone: Optional[str] = None,
    marketing_goal: Optional[str] = None,
    caption_length: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate marketing copy for a restaurant dish.
    
    Uses LLM to create platform-specific copy (Facebook, Instagram, Google Business,
    SMS, Email) based on tone, marketing goal, and caption length.
    
    Args:
        item_name: Name of the dish
        features: List of food features/ingredients
        price: Price string (e.g., "$12.99")
        theme_label: Visual theme name (for context)
        tone: professional, casual, luxury, bold, or playful
        marketing_goal: drive_traffic, promote_item, limited_offer, etc.
        caption_length: short, medium, or long
        
    Returns:
        Dict with fb_post, ig_post, gbp, sms, email, hashtags, generated_at
    """
    from ai_engine.client import generate_structured
    from routers.media.shared import _now
    
    db = await get_db()

    feat_text = "\n".join(f"- {f}" for f in features) if features else "(none)"
    price_str = (price or "").strip() or "(omit)"
    
    # Map tone to writing style (Priority 2 & 3)
    tone_map = {
        "professional": "professional and refined",
        "casual": "casual and friendly",
        "luxury": "upscale and sophisticated",
        "bold": "bold and energetic",
        "playful": "fun and playful",
    }
    tone_style = tone_map.get(tone or "professional", "warm and appetizing")
    
    # Map marketing goal to emphasis (Priority 2 & 3)
    goal_map = {
        "drive_traffic": "Focus on urgency and immediate action. Use phrases like 'Stop by today' or 'Visit us now'.",
        "promote_item": "Highlight what makes this dish special and unique.",
        "limited_offer": "Emphasize scarcity and time-sensitivity. Use 'Limited time only' or 'While supplies last'.",
        "seasonal": "Connect to the current season or holiday. Use seasonal language.",
        "daily_special": "Position as today's featured item. Create FOMO with 'Today only' or 'Chef's pick'.",
        "brand_awareness": "Focus on the restaurant's story and values. Build emotional connection.",
    }
    goal_emphasis = goal_map.get(marketing_goal or "promote_item", "Highlight the dish appeal.")
    
    # Map caption length to word counts (Priority 2 & 3)
    length_map = {
        "short": {
            "fb": "30-50 words",
            "ig": "15-25 words",
            "gbp": "40-80 words",
            "email": "30-60 words",
        },
        "medium": {
            "fb": "60-100 words",
            "ig": "30-50 words",
            "gbp": "80-180 words",
            "email": "60-120 words",
        },
        "long": {
            "fb": "100-150 words",
            "ig": "50-80 words",
            "gbp": "180-300 words",
            "email": "120-200 words",
        },
    }
    lengths = length_map.get(caption_length or "medium", length_map["medium"])
    
    sys_prompt = (
        f"You are a New Orleans restaurant marketing copywriter for Lakeview "
        f"Burgers & Seafood. Write {tone_style} copy. "
        f"Output ONLY a valid JSON object — no markdown."
    )
    usr_prompt = (
        f"Item: {item_name}\n"
        f"Features:\n{feat_text}\n"
        f"Price: {price_str}\n"
        f"Visual theme: {theme_label}\n"
        f"Marketing Goal: {goal_emphasis}\n\n"
        f"Generate a complete marketing pack:\n"
        f" - fb_post: {lengths['fb']}, Facebook-style conversational, 1 emoji max, ends with CTA on its own line.\n"
        f" - ig_post: {lengths['ig']}, punchy Instagram-native, 2-3 emojis, ends with a hook question or CTA.\n"
        f" - gbp: {lengths['gbp']} for Google Business Profile, leads with the offer, ends with next step.\n"
        f" - sms: under 140 chars, includes item + price, ends with CTA.\n"
        f" - email_subject: 4-7 words, attention-grabbing.\n"
        f" - email_body: {lengths['email']}, friendly, plain text only.\n"
        f" - hashtags: 8-12 relevant hashtags as strings (no '#' prefix)."
    )
    schema = (
        '{"fb_post":"string","ig_post":"string","gbp":"string","sms":"string",'
        '"email_subject":"string","email_body":"string","hashtags":["string"]}'
    )
    wrapped = await generate_structured(db, system_prompt=sys_prompt, user_prompt=usr_prompt, schema_hint=schema)
    out = wrapped.get("data") or {}
    return {
        "fb_post": (out.get("fb_post") or "").strip()[:2000],
        "ig_post": (out.get("ig_post") or "").strip()[:2000],
        "gbp": (out.get("gbp") or "").strip()[:1500],
        "sms": (out.get("sms") or "").strip()[:160],
        "email": {
            "subject": (out.get("email_subject") or "").strip()[:120],
            "body": (out.get("email_body") or "").strip()[:2000],
        },
        "hashtags": [h.lstrip("#").strip() for h in (out.get("hashtags") or [])][:15],
        "generated_at": _now(),
    }


# Expose for backward compatibility
__all__ = ["write_designer_copy"]
