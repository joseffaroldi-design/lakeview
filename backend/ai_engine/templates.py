"""Campaign templates registry.

Each template is a tagged preset that pre-fills the campaign brief.
Industries can register their own templates here without modifying the engine.
"""
from typing import Dict, List, Any

# Generic templates available to ALL industries
GENERIC_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "generic_lead_gen",
        "label": "Lead Generation",
        "industry": "generic",
        "defaults": {
            "goal": "Generate Leads",
            "tone": "Professional",
            "platform": "Facebook",
        },
    },
    {
        "id": "generic_event",
        "label": "Event Promotion",
        "industry": "generic",
        "defaults": {
            "goal": "Promote Event",
            "tone": "Urgent",
            "platform": "Instagram",
        },
    },
    {
        "id": "generic_loyalty",
        "label": "Customer Loyalty",
        "industry": "generic",
        "defaults": {
            "goal": "Customer Retention",
            "tone": "Family Friendly",
            "platform": "Email",
        },
    },
]

# Restaurant-specific templates (per spec)
RESTAURANT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "rest_promotion",
        "label": "Restaurant Promotion",
        "industry": "restaurant",
        "defaults": {
            "goal": "Increase Sales",
            "tone": "Local New Orleans Style",
            "platform": "Facebook",
        },
    },
    {
        "id": "rest_daily_special",
        "label": "Daily Special",
        "industry": "restaurant",
        "defaults": {
            "goal": "Promote Menu Item",
            "tone": "Casual",
            "platform": "Instagram",
        },
    },
    {
        "id": "rest_happy_hour",
        "label": "Happy Hour",
        "industry": "restaurant",
        "defaults": {
            "goal": "Increase Sales",
            "tone": "Urgent",
            "platform": "Instagram",
        },
    },
    {
        "id": "rest_catering",
        "label": "Catering",
        "industry": "restaurant",
        "defaults": {
            "goal": "Generate Leads",
            "tone": "Professional",
            "platform": "Facebook",
        },
    },
    {
        "id": "rest_seafood_special",
        "label": "Seafood Special",
        "industry": "restaurant",
        "defaults": {
            "goal": "Promote Menu Item",
            "tone": "Local New Orleans Style",
            "platform": "Instagram",
        },
    },
    {
        "id": "rest_burger_special",
        "label": "Burger Special",
        "industry": "restaurant",
        "defaults": {
            "goal": "Promote Menu Item",
            "tone": "Casual",
            "platform": "Facebook",
        },
    },
    {
        "id": "rest_event_promotion",
        "label": "Event Promotion",
        "industry": "restaurant",
        "defaults": {
            "goal": "Promote Event",
            "tone": "Local New Orleans Style",
            "platform": "Facebook",
        },
    },
    {
        "id": "rest_loyalty",
        "label": "Customer Loyalty",
        "industry": "restaurant",
        "defaults": {
            "goal": "Customer Retention",
            "tone": "Family Friendly",
            "platform": "Email",
        },
    },
]

ALL_TEMPLATES = GENERIC_TEMPLATES + RESTAURANT_TEMPLATES


def get_templates(industry: str = None) -> List[Dict[str, Any]]:
    if industry is None:
        return ALL_TEMPLATES
    return [t for t in ALL_TEMPLATES if t["industry"] in (industry, "generic")]


def get_template(template_id: str) -> Dict[str, Any]:
    for t in ALL_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


# Public catalogs for the frontend dropdowns
GOALS = [
    "Increase Sales",
    "Promote Event",
    "Promote Menu Item",
    "Generate Leads",
    "Increase Followers",
    "Customer Retention",
]

PLATFORMS = ["Facebook", "Instagram", "TikTok", "Google", "Email", "SMS"]

TONES = [
    "Professional",
    "Funny",
    "Family Friendly",
    "Luxury",
    "Urgent",
    "Casual",
    "Local New Orleans Style",
]
