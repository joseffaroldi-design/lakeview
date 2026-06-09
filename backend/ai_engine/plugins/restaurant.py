"""Restaurant plugin — first vertical for the AI Marketing Engine.

Contributes:
  • 7 campaign templates (Daily Special, Seafood Special, ...)
  • 9 one-click "Promote This Item" channels
  • build_brief() that converts a Menu Item context into a per-channel brief

This plugin lives ON TOP of the core engine. Core code knows nothing about
menu items, burgers, or seafood.
"""
from typing import Any, Dict

from .base import Plugin, register_plugin
from ..industries.restaurant import SYSTEM_PROMPT


TEMPLATES = [
    {
        "id": "daily_special",
        "label": "Daily Special",
        "defaults": {
            "goal": "Promote Menu Item",
            "platform": "Facebook",
            "tone": "Local New Orleans Style",
        },
    },
    {
        "id": "seafood_special",
        "label": "Seafood Special",
        "defaults": {
            "goal": "Promote Menu Item",
            "platform": "Instagram",
            "tone": "Sensory + Crave-worthy",
            "audience": "Gulf seafood lovers, weekend diners",
        },
    },
    {
        "id": "burger_special",
        "label": "Burger Special",
        "defaults": {
            "goal": "Promote Menu Item",
            "platform": "Instagram",
            "tone": "Bold + Hungry",
            "audience": "Burger fans, lunch crowd, after-work diners",
        },
    },
    {
        "id": "happy_hour",
        "label": "Happy Hour",
        "defaults": {
            "goal": "Increase Sales",
            "platform": "Facebook",
            "tone": "Casual + Inviting",
            "audience": "Local professionals 25-55, after-work crowd",
        },
    },
    {
        "id": "catering_promotion",
        "label": "Catering Promotion",
        "defaults": {
            "goal": "Catering Leads",
            "platform": "Facebook",
            "tone": "Warm + Professional",
            "audience": "Office managers, event planners, hosts",
        },
    },
    {
        "id": "event_promotion",
        "label": "Event Promotion",
        "defaults": {
            "goal": "Event Awareness",
            "platform": "Instagram",
            "tone": "Festive + Energetic",
        },
    },
    {
        "id": "loyalty_campaign",
        "label": "Loyalty Campaign",
        "defaults": {
            "goal": "Customer Loyalty",
            "platform": "Email",
            "tone": "Grateful + Warm",
            "audience": "Repeat guests, loyalty members",
        },
    },
]


# Each action ties a channel to one of the core engine's generators.
# `kind` matches keys in ai_engine.generators.GENERATORS.
# `extra_brief` is merged into the brief at build time.
ACTIONS = [
    {
        "id": "facebook_ad",
        "label": "Facebook Ad",
        "kind": "social",
        "extra_brief": {"platform": "Facebook"},
        "asset_kind": "social_post",
    },
    {
        "id": "instagram_caption",
        "label": "Instagram Caption",
        "kind": "social",
        "extra_brief": {"platform": "Instagram"},
        "asset_kind": "social_post",
    },
    {
        "id": "tiktok_caption",
        "label": "TikTok Caption",
        "kind": "social",
        "extra_brief": {"platform": "TikTok"},
        "asset_kind": "social_post",
    },
    {
        "id": "google_business_post",
        "label": "Google Business Post",
        "kind": "social",
        "extra_brief": {"platform": "Google Business"},
        "asset_kind": "social_post",
    },
    {
        "id": "email_campaign",
        "label": "Email Campaign",
        "kind": "email",
        "extra_brief": {"email_type": "Promotion"},
        "asset_kind": "email",
    },
    {
        "id": "sms_campaign",
        "label": "SMS Campaign",
        "kind": "sms",
        "extra_brief": {},
        "asset_kind": "sms",
    },
    {
        "id": "flyer_copy",
        "label": "Flyer Copy",
        "kind": "image_concept",
        "extra_brief": {"asset_subtype": "Flyer Layout"},
        "asset_kind": "image_concept",
    },
    {
        "id": "image_prompt",
        "label": "AI Image Prompt",
        "kind": "image_concept",
        "extra_brief": {"asset_subtype": "Food Photography"},
        "asset_kind": "image_concept",
    },
    {
        "id": "video_script_15",
        "label": "15-second Video Script",
        "kind": "video_concept",
        "extra_brief": {"duration_seconds": 15},
        "asset_kind": "video_concept",
    },
]


def _format_menu_context(item: Dict[str, Any]) -> str:
    """Render a menu item as the BUSINESS CONTEXT block fed to the LLM."""
    lines = []
    name = item.get("name")
    if name:
        lines.append(f"FEATURED MENU ITEM: {name}")
    cat = item.get("category")
    if cat:
        lines.append(f"CATEGORY: {cat}")
    desc = item.get("description")
    if desc:
        lines.append(f"DESCRIPTION: {desc}")
    price = item.get("price")
    if price not in (None, ""):
        lines.append(f"PRICE: ${price}")
    if item.get("image_url"):
        lines.append(f"IMAGE REFERENCE: {item['image_url']}")
    lines.append(
        "Restaurant: Lakeview Burgers & Seafood — neighborhood restaurant in Lakeview, "
        "New Orleans. Family-owned. Specializes in Gulf seafood, smashburgers, "
        "po'boys, gumbo, and Friday fish fries."
    )
    return "\n".join(lines)


def build_brief(context: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a menu item + selected action into a normalized core-engine brief."""
    item = context.get("item") or {}
    template_id = context.get("template_id") or "daily_special"
    template = next((t for t in TEMPLATES if t["id"] == template_id), TEMPLATES[0])

    brief: Dict[str, Any] = {
        "industry": "restaurant",
        "name": context.get("campaign_name") or f"Promote {item.get('name') or 'Menu Item'}",
        **template["defaults"],
        "context": _format_menu_context(item),
        "audience": (
            context.get("audience")
            or template["defaults"].get("audience")
            or "Local New Orleans residents, families, foodies"
        ),
        "offer": context.get("offer") or item.get("description") or "",
    }
    # Action-specific overrides (platform/email_type/duration/subtype...)
    brief.update(action.get("extra_brief", {}))
    return brief


PLUGIN = Plugin(
    id="restaurant",
    label="Restaurant",
    description=(
        "Promote menu items, daily specials, happy hours, catering, and events. "
        "One-click multi-channel generation from your Menu Editor."
    ),
    templates=TEMPLATES,
    actions=ACTIONS,
    build_brief=build_brief,
    system_prompt=SYSTEM_PROMPT,
)

register_plugin(PLUGIN)
