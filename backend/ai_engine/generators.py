"""Specialty generators built on top of ai_engine.client.generate_structured.

Each generator = system-prompt addon + JSON schema hint + brief-builder.
Adding a new asset type later = one new entry in GENERATORS.
"""
from typing import Any, Dict, Optional

from ai_engine.client import generate_structured
from ai_engine.prompts import resolve_system_prompt


# ---- SOCIAL ----
SOCIAL_SCHEMA = """{
  "platform": "Facebook|Instagram|TikTok|Google Business",
  "short":  {"caption": string, "headline": string, "hashtags": [string, ...], "cta": string},
  "medium": {"caption": string, "headline": string, "hashtags": [string, ...], "cta": string},
  "long":   {"caption": string, "headline": string, "hashtags": [string, ...], "cta": string}
}"""

PLATFORM_RULES = {
    "Facebook": (
        "Facebook rules: hook in first 1-2 lines (truncated otherwise). Conversational, slightly longer ok. "
        "Use 0-3 hashtags. CTA = clear next step like 'Order Now' or 'Reserve'. Emoji sparingly."
    ),
    "Instagram": (
        "Instagram rules: front-load the hook, line breaks for scannability. Hashtags grouped at the end (8-15). "
        "Casual + sensory. Visual-first language. Emoji ok if on brand."
    ),
    "TikTok": (
        "TikTok rules: punchy, native, lowercase casual, very short. 3-5 hashtags max blended naturally. "
        "Sound and movement implied. No corporate tone. Avoid emoji unless ironic."
    ),
    "Google Business": (
        "Google Business Profile rules: keyword-rich, location-aware, factual. Plain CTA. "
        "Hashtags optional and minimal. 1500 char hard limit."
    ),
}

# ---- EMAIL ----
EMAIL_SCHEMA = """{
  "campaign_type": "Welcome|Promotion|Holiday|Winback",
  "subject_line": string,
  "preview_text": string,
  "email_body": string,
  "cta_label": string,
  "cta_link_suggestion": string
}"""

EMAIL_TYPE_GUIDANCE = {
    "Welcome": "Warm first impression. Set expectations for what's coming. Soft single CTA.",
    "Promotion": "Lead with offer + deadline. Clear urgency. Single dominant CTA.",
    "Holiday": "Tie message to the holiday. Sentiment + offer balance. Conversational close.",
    "Winback": "Acknowledge it's been a while. Compelling reason to return + small incentive.",
}

# ---- SMS ----
SMS_SCHEMA = """{
  "v160": string,
  "v300": string,
  "urgency": string,
  "discount": string
}"""

# ---- IMAGE CONCEPT ----
IMAGE_CONCEPT_SCHEMA = """{
  "headline": string,
  "subheadline": string,
  "cta": string,
  "layout_direction": string,
  "photography_direction": string,
  "graphic_direction": string,
  "brand_direction": string,
  "generation_prompt": string
}"""

# ---- VIDEO CONCEPT ----
VIDEO_CONCEPT_SCHEMA = """{
  "duration_seconds": number,
  "script": string,
  "voiceover": string,
  "shot_list": [string, ...],
  "scene_list": [{"scene": string, "duration_seconds": number, "visual": string, "audio": string}, ...],
  "storyboard": [string, ...],
  "on_screen_text": [string, ...],
  "production_notes": string,
  "generation_prompt": string
}"""


def _common_lines(brief: Dict[str, Any]):
    parts = []
    if brief.get("name"):
        parts.append(f"CAMPAIGN: {brief['name']}")
    if brief.get("goal"):
        parts.append(f"GOAL: {brief['goal']}")
    if brief.get("tone"):
        parts.append(f"TONE: {brief['tone']}")
    if brief.get("audience"):
        parts.append(f"AUDIENCE: {brief['audience']}")
    if brief.get("offer"):
        parts.append(f"OFFER: {brief['offer']}")
    if brief.get("context"):
        parts.append(f"BUSINESS CONTEXT:\n{brief['context']}")
    return parts


def build_social_prompt(brief: Dict[str, Any]) -> str:
    platform = brief.get("platform", "Facebook")
    rules = PLATFORM_RULES.get(platform, "")
    parts = _common_lines(brief)
    parts.append(f"PLATFORM: {platform}")
    parts.append(f"PLATFORM RULES: {rules}")
    parts.append(
        "Produce SHORT (under 80 chars caption), MEDIUM (80-200 chars caption), and LONG "
        "(200-500 chars caption) variants. Each variant has caption + headline + hashtags + cta."
    )
    return "\n".join(parts)


def build_email_prompt(brief: Dict[str, Any]) -> str:
    et = brief.get("email_type", "Promotion")
    guide = EMAIL_TYPE_GUIDANCE.get(et, "")
    parts = _common_lines(brief)
    parts.append(f"EMAIL TYPE: {et}")
    parts.append(f"GUIDANCE: {guide}")
    parts.append(
        "Return subject_line (≤60 chars), preview_text (≤90 chars), email_body (200-500 words, "
        "with paragraph breaks; do not invent links — instead suggest one CTA link target via cta_link_suggestion), "
        "cta_label, cta_link_suggestion."
    )
    return "\n".join(parts)


def build_sms_prompt(brief: Dict[str, Any]) -> str:
    parts = _common_lines(brief)
    parts.append(
        "Produce 4 SMS variants for the same campaign:\n"
        "- v160: under 160 characters total\n"
        "- v300: under 300 characters total\n"
        "- urgency: leans into time-sensitive urgency\n"
        "- discount: leads with the discount/offer\n"
        "Include 'Reply STOP to opt out' only on the longer variants. No links unless an offer demands it."
    )
    return "\n".join(parts)


def build_image_concept_prompt(brief: Dict[str, Any]) -> str:
    asset_subtype = brief.get("asset_subtype", "Ad Creative")
    parts = _common_lines(brief)
    parts.append(f"IMAGE TYPE: {asset_subtype}")
    parts.append(
        "Produce a complete art direction brief: headline (≤8 words), subheadline, cta button label, "
        "layout_direction (composition + hierarchy), photography_direction (lens/lighting/styling, or 'illustration' if not photo), "
        "graphic_direction (typography, colors, motifs aligned to brand), brand_direction (overall feel), "
        "and a generation_prompt (single dense prompt suitable for OpenAI Images / Ideogram / Midjourney / Flux — "
        "include subject, framing, lens, lighting, style cues, no negative prompt, no aspect ratio param)."
    )
    return "\n".join(parts)


def build_video_concept_prompt(brief: Dict[str, Any]) -> str:
    duration = brief.get("duration_seconds", 30)
    parts = _common_lines(brief)
    parts.append(f"DURATION: {duration} seconds")
    parts.append(
        "Produce a full production-ready video brief: script (voiceover dialogue), voiceover (delivery direction), "
        f"shot_list (one-line entries), scene_list (one entry per beat with scene name + duration_seconds summing to {duration}, "
        "visual + audio), storyboard (one short visual description per scene), on_screen_text (text overlays), "
        "production_notes (tone, pacing, music genre, b-roll suggestions), and generation_prompt "
        "(single dense prompt suitable for Sora 2 / Runway / Veo / Kling — subject, motion, camera, lighting)."
    )
    return "\n".join(parts)


# ---- Public dispatcher ----

GENERATORS = {
    "social": {"schema": SOCIAL_SCHEMA, "builder": build_social_prompt},
    "email": {"schema": EMAIL_SCHEMA, "builder": build_email_prompt},
    "sms": {"schema": SMS_SCHEMA, "builder": build_sms_prompt},
    "image_concept": {"schema": IMAGE_CONCEPT_SCHEMA, "builder": build_image_concept_prompt},
    "video_concept": {"schema": VIDEO_CONCEPT_SCHEMA, "builder": build_video_concept_prompt},
}


async def run_generator(
    db,
    kind: str,
    brief: Dict[str, Any],
    *,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    if kind not in GENERATORS:
        raise ValueError(f"Unknown generator kind: {kind}")
    spec = GENERATORS[kind]
    system_prompt = resolve_system_prompt(brief.get("industry"))
    user_prompt = spec["builder"](brief)
    return await generate_structured(
        db,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_hint=spec["schema"],
        provider_override=provider_override,
        model_override=model_override,
    )
