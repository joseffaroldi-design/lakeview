"""Reusable prompt framework. Industry-agnostic by default.

Architecture:
  - BASE_SYSTEM_PROMPT — common marketer persona
  - build_master_user_prompt(...) — composes the user prompt from a CampaignBrief
  - SCHEMA_HINT — JSON shape the model must return

Industry modules can override BASE_SYSTEM_PROMPT (e.g. restaurant.SYSTEM_PROMPT)
while keeping the user-prompt composition identical.
"""
from typing import Optional, Dict, Any

BASE_SYSTEM_PROMPT = (
    "You are an elite direct-response marketing copywriter and ad strategist "
    "with 20 years of experience writing high-converting campaigns across "
    "Facebook, Instagram, TikTok, Google, email, and SMS. You write tight, "
    "compelling copy that drives action. You adapt voice, format, and length "
    "to the platform and audience. You avoid clichés, AI-sounding phrasing, "
    "and emoji unless they serve the message."
)


MASTER_SCHEMA_HINT = """{
  "headlines": [string, string, string, string, string],
  "primary_text": [string, string, string],
  "ctas": [string, string, string],
  "hashtags": [string, ...],
  "image_concepts": [string, string, string],
  "video_concepts": [string, string],
  "video_hooks": [string, string, string]
}"""


def build_master_user_prompt(brief: Dict[str, Any]) -> str:
    """Compose the user-side prompt from a normalized campaign brief.

    Industry-agnostic. Industries inject extra context via the `context` field.
    """
    parts = []
    parts.append(f"CAMPAIGN: {brief.get('name', '(untitled)')}")
    parts.append(f"GOAL: {brief['goal']}")
    parts.append(f"PLATFORM: {brief['platform']}")
    parts.append(f"TONE: {brief['tone']}")

    if brief.get("audience"):
        parts.append(f"AUDIENCE: {brief['audience']}")
    if brief.get("offer"):
        parts.append(f"OFFER: {brief['offer']}")
    if brief.get("budget"):
        parts.append(f"BUDGET: ${brief['budget']}")
    if brief.get("template"):
        parts.append(f"TEMPLATE: {brief['template']}")
    if brief.get("context"):
        parts.append(f"BUSINESS CONTEXT:\n{brief['context']}")
    if brief.get("variation_seed"):
        parts.append(
            f"VARIATION REQUEST: Generate a fresh batch (variation #{brief['variation_seed']}). "
            f"Avoid repeating any earlier outputs. Push for new angles."
        )

    parts.append(
        "Produce 5 distinct headlines, 3 primary text variations (~50-150 words each), "
        "3 CTA button labels, a hashtag set (8-12 tags), 3 image-shoot concepts, "
        "2 video concepts, and 3 video hook ideas (first 3 seconds)."
    )
    return "\n".join(parts)


def resolve_system_prompt(industry: Optional[str]) -> str:
    """Pick the right system prompt based on industry. Future industries plug in here."""
    if industry == "restaurant":
        from ai_engine.industries.restaurant import SYSTEM_PROMPT
        return SYSTEM_PROMPT
    return BASE_SYSTEM_PROMPT
