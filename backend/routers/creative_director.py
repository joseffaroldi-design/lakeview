"""Sprint 17A — Creative Director.

A pure scoring engine that recommends 3 themes (Best / Good / Alternative).
NEVER auto-applies. The owner always picks. Reuses the existing theme_packs
registry — no duplicate theme metadata.

Single endpoint: POST /api/creative-director/recommend
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Cookie, Header
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
from config import db
from theme_packs import THEME_STYLES, THEME_META

router = APIRouter(prefix="/creative-director", tags=["creative-director"])
log = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------- model
class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_key: Optional[constr(strip_whitespace=True, max_length=200)] = None
    food_type: Optional[constr(strip_whitespace=True, max_length=200)] = None
    features: List[constr(strip_whitespace=True, max_length=120)] = Field(default_factory=list)
    dominant_colors: List[constr(strip_whitespace=True, max_length=20)] = Field(default_factory=list)


# ---------------------------------------------------------------- helpers

# Map keywords found in the item name / food_type / item_key to a pack category.
# First match wins; fall back to "general".
_CATEGORY_HINTS = [
    ("burger",   ["burger", "smash", "patty", "cheeseburger", "double-stack"]),
    ("seafood",  ["shrimp", "fish", "oyster", "po-boy", "po'boy", "poboy", "crab",
                   "lobster", "ceviche", "seafood", "catfish", "calamari", "scallop"]),
    ("sports",   ["wing", "nacho", "tailgate", "game-day", "gameday", "pretzel"]),
    ("seasonal", ["mardi", "lent", "thanksgiving", "christmas", "valentine",
                  "easter", "halloween", "july-4", "fourth", "boil"]),
]


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _infer_category(item_key: Optional[str], food_type: Optional[str],
                    features: List[str]) -> str:
    """Return the most likely pack category for the given signals."""
    haystack = " ".join([
        (item_key or "").replace("::", " "),
        (food_type or ""),
        " ".join(features or []),
    ]).lower()
    haystack_slug = _slugify(haystack)
    for cat, kws in _CATEGORY_HINTS:
        for kw in kws:
            if kw in haystack or kw in haystack_slug:
                return cat
    return "general"


def _current_season() -> Tuple[str, str]:
    """Returns (season, holiday_window) — both lowercase short codes.
    `holiday_window` is "" outside of well-known windows.
    """
    now = datetime.now(timezone.utc)
    m, d = now.month, now.day
    # Season (US/Northern hemisphere defaults)
    if (m, d) >= (12, 21) or (m, d) < (3, 20):
        season = "winter"
    elif (m, d) < (6, 21):
        season = "spring"
    elif (m, d) < (9, 23):
        season = "summer"
    else:
        season = "fall"
    # Holiday windows (rough; not exhaustive)
    if m == 2 and 1 <= d <= 28:
        return season, "mardi_gras"  # Lent / Mardi Gras window
    if m == 7 and 1 <= d <= 7:
        return season, "july_4"
    if m == 2 and 10 <= d <= 16:
        return season, "valentines"
    if (m == 11 and d >= 20) or (m == 12 and d <= 26):
        return season, "holidays"
    if m in (5, 6, 7, 8):
        return season, "summer"
    return season, ""


def _seasonal_theme_bonus(theme_id: str, holiday: str) -> Tuple[int, str]:
    """Return (bonus_points, reason). Bonus 0 means no seasonal hook."""
    if not holiday:
        return 0, ""
    h = holiday.lower()
    # Heuristic match on theme id / pack
    tid = theme_id.lower()
    meta = THEME_META.get(theme_id, {})
    pack = meta.get("pack", "")
    best_use = (meta.get("best_use") or "").lower()
    if pack == "seasonal":
        if h == "mardi_gras" and ("mardi" in tid or "mardi" in best_use):
            return 18, "It's Mardi Gras season."
        if h == "july_4" and ("july" in tid or "boil" in tid or "summer" in best_use):
            return 16, "Patriotic / summer window."
        if h == "valentines" and ("valent" in tid or "rose" in tid or "ros" in best_use):
            return 14, "Valentine's window."
        if h == "holidays" and ("holiday" in tid or "winter" in tid or "thanksgiving" in best_use
                                or "christmas" in best_use):
            return 16, "Holiday season."
        # Generic seasonal nudge so the pack still shows
        return 6, "Seasonal-themed pack."
    return 0, ""


def _color_match_bonus(dominant_colors: List[str], theme_id: str) -> Tuple[int, str]:
    """Lightweight color harmony: if the theme's bg or branding_color is
    'warm' / 'cool' and the photo's dominant colors agree, give a small bump.
    """
    if not dominant_colors:
        return 0, ""
    spec = THEME_STYLES.get(theme_id, {})
    bg = spec.get("bg_color")
    if not bg:
        return 0, ""
    r, g, b = bg[0], bg[1], bg[2]
    # Naive warm/cool classification of the theme bg
    theme_warm = (r - b) > 20
    theme_cool = (b - r) > 20
    # Same for photo dominant_colors (hex strings like "#abcdef")
    warm_votes = cool_votes = 0
    for hx in dominant_colors[:5]:
        try:
            if hx.startswith("#") and len(hx) >= 7:
                pr, pg, pb = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
                if (pr - pb) > 20:
                    warm_votes += 1
                elif (pb - pr) > 20:
                    cool_votes += 1
        except Exception:  # noqa: BLE001
            continue
    if theme_warm and warm_votes >= max(1, cool_votes + 1):
        return 6, "Warm color harmony with your photo."
    if theme_cool and cool_votes >= max(1, warm_votes + 1):
        return 6, "Cool color harmony with your photo."
    return 0, ""


async def _load_brand_color() -> Optional[Tuple[int, int, int]]:
    """Read brand accent color from site_content. Defaults to gold (#a5935b)
    if the CMS doesn't expose anything (the legacy seed). Never raises.
    """
    try:
        content = await db.site_content.find_one({}, {"_id": 0}) or {}
        # Hero/about/contact don't carry a brand color directly today; fall back
        # to the legacy gold from seed_data wheel entries.
        hero = (content or {}).get("hero", {}) or {}
        # Some installs may have a custom brand.color; tolerate missing.
        brand = (content or {}).get("brand") or {}
        hex_str = brand.get("color") or hero.get("accent") or "#a5935b"
        if isinstance(hex_str, str) and hex_str.startswith("#") and len(hex_str) >= 7:
            return int(hex_str[1:3], 16), int(hex_str[3:5], 16), int(hex_str[5:7], 16)
    except Exception:  # noqa: BLE001
        return None
    return (165, 147, 91)  # legacy gold


def _brand_match_bonus(brand_rgb: Optional[Tuple[int, int, int]],
                       theme_id: str) -> Tuple[int, str]:
    if not brand_rgb:
        return 0, ""
    spec = THEME_STYLES.get(theme_id, {})
    # Compare brand to branding_color first, then bg_color
    target = spec.get("branding_color") or spec.get("bg_color")
    if not target:
        return 0, ""
    dr = abs(brand_rgb[0] - target[0])
    dg = abs(brand_rgb[1] - target[1])
    db_ = abs(brand_rgb[2] - target[2])
    dist = dr + dg + db_  # cheap L1 distance
    if dist < 80:
        return 5, "Matches your brand color."
    return 0, ""


# ---------------------------------------------------------------- core scorer

def _score_themes(*, category: str,
                  memory_theme: Optional[str],
                  season: str, holiday: str,
                  dominant_colors: List[str],
                  brand_rgb: Optional[Tuple[int, int, int]]) -> List[Dict[str, Any]]:
    """Score every theme. Returns a list sorted by score desc."""
    rows: List[Dict[str, Any]] = []
    for tid, spec in THEME_STYLES.items():
        meta = THEME_META.get(tid, {})
        pack_cat = meta.get("category", "")
        score = 0
        reasons: List[str] = []

        # 1) Category match (the single strongest signal)
        if category != "general" and pack_cat == category:
            score += 50
            reasons.append(f"Best for {category}.")
        elif category != "general" and pack_cat in ("general", "poster"):
            score += 14
        elif category == "general":
            # If we couldn't infer a category, prefer general/poster themes.
            if pack_cat in ("general", "poster"):
                score += 22
            else:
                score += 6
        else:
            score += 4

        # 2) Memory bias — owner's previous successful theme for this item.
        if memory_theme and tid == memory_theme:
            score += 35
            reasons.append("Matches your saved style.")

        # 3) Seasonal/holiday nudge
        s_bonus, s_reason = _seasonal_theme_bonus(tid, holiday)
        score += s_bonus
        if s_reason:
            reasons.append(s_reason)

        # 4) Color harmony with photo
        c_bonus, c_reason = _color_match_bonus(dominant_colors, tid)
        score += c_bonus
        if c_reason:
            reasons.append(c_reason)

        # 5) Brand color match
        b_bonus, b_reason = _brand_match_bonus(brand_rgb, tid)
        score += b_bonus
        if b_reason:
            reasons.append(b_reason)

        rows.append({
            "id": tid,
            "label": spec.get("label", tid),
            "pack": meta.get("pack", ""),
            "pack_label": meta.get("pack_label", ""),
            "category": pack_cat,
            "best_use": meta.get("best_use", ""),
            "preview_color": "#{:02x}{:02x}{:02x}".format(*spec["bg_color"]),
            "score": score,
            "reasons": reasons,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def _label_rank(idx: int) -> Tuple[str, int]:
    """Returns (rank_label, stars) for the i-th recommendation (0-based)."""
    if idx == 0:
        return "Best Match", 5
    if idx == 1:
        return "Good Match", 4
    return "Alternative", 3


# ---------------------------------------------------------------- route
@router.post("/recommend")
async def recommend(body: RecommendRequest,
                    authorization: str = Header(None),
                    session_token: str = Cookie(None)):
    """Return top 3 theme recommendations with stars + reasons.
    Does NOT auto-apply anything. The Photo→Flyer UI shows these as
    suggestions; the owner clicks one to pick it.
    """
    await verify_session(authorization, session_token)

    # 1) Load memory (if any) so we can bias toward the saved theme.
    memory: Dict[str, Any] = {}
    if body.item_key:
        memory = await db.design_memory.find_one(
            {"item_key": body.item_key}, {"_id": 0}) or {}

    # 2) Infer category from item_key / food_type / features.
    category = _infer_category(body.item_key, body.food_type, body.features or [])

    # 3) Season + holiday window
    season, holiday = _current_season()

    # 4) Brand color from CMS (fail-soft)
    brand_rgb = await _load_brand_color()

    # 5) Score every theme.
    ranked = _score_themes(
        category=category,
        memory_theme=memory.get("theme"),
        season=season, holiday=holiday,
        dominant_colors=body.dominant_colors or [],
        brand_rgb=brand_rgb,
    )

    # 6) Trim to top 3, attach rank label + a primary reason.
    recs: List[Dict[str, Any]] = []
    for i, row in enumerate(ranked[:3]):
        label, stars = _label_rank(i)
        reasons = row["reasons"]
        # Prefer memory > category > season > color > brand for the primary reason.
        primary = next((r for r in reasons if "saved style" in r), None) \
            or next((r for r in reasons if r.startswith("Best for")), None) \
            or next((r for r in reasons if "season" in r.lower() or "mardi" in r.lower()), None) \
            or (reasons[0] if reasons else row.get("best_use") or "Solid all-rounder for this dish.")
        recs.append({
            **{k: v for k, v in row.items() if k != "reasons"},
            "rank": label,
            "stars": stars,
            "reason": primary,
            "all_reasons": reasons,
        })

    log.info("CD_RECOMMEND item_key=%s category=%s holiday=%s memory_theme=%s -> %s",
             body.item_key, category, holiday, memory.get("theme"),
             [r["id"] for r in recs])
    return {
        "recommendations": recs,
        "context": {
            "category": category,
            "season": season,
            "holiday": holiday,
            "memory_theme": memory.get("theme"),
            "has_memory": bool(memory),
        },
    }
