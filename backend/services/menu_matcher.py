"""Fuzzy match an AI-detected food name against the live menu collection.

Sprint 16D — auto-fills price on the Photo→Flyer review screen so the
owner doesn't have to type. Uses pure-Python difflib + token-overlap,
no external services. Designed to be cheap and conservative: when in
doubt, returns `matched=False` and the UI shows a manual price field.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


def _tokens(s: str) -> set:
    return {t.lower() for t in re.findall(r"[a-zA-Z]+", s or "") if len(t) >= 3}


def _score(query: str, candidate: str) -> float:
    """Combined score: difflib ratio + token-overlap. Higher = better."""
    if not query or not candidate:
        return 0.0
    q = query.strip().lower()
    c = candidate.strip().lower()
    if q == c:
        return 1.0
    seq = SequenceMatcher(a=q, b=c).ratio()  # 0..1
    qt, ct = _tokens(query), _tokens(candidate)
    if not qt or not ct:
        return seq
    overlap = len(qt & ct) / max(1, len(qt | ct))
    # 60% sequence, 40% token overlap
    return 0.6 * seq + 0.4 * overlap


def _item_key(category: str, name: str) -> str:
    """Mirror the menu_item_key convention used elsewhere."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    cat = re.sub(r"[^a-z0-9]+", "-", (category or "menu").lower()).strip("-")
    return f"{cat}::{slug}"


async def match_food_to_menu(food_type: str,
                             db: Any,
                             *,
                             threshold: float = 0.55,
                             top_k: int = 5) -> Dict[str, Any]:
    """Try to find a menu item that matches `food_type`. Returns:

        {matched: bool,
         item_key: 'cat::slug' or None,
         name: str or None,
         price: str or None,
         confidence: 0..1,
         tried: int   # how many menu items we scored}

    Conservative: requires score >= threshold AND no near-tie with another
    candidate (prevents auto-filling the wrong dish when two items are
    similarly close).
    """
    out = {"matched": False, "item_key": None, "name": None,
           "price": None, "confidence": 0.0, "tried": 0}
    if not food_type:
        return out

    # The menu surface stores items under `menu_items` collection (see
    # backend/routers/menu.py). Each row has at least: name, price, category.
    # We tolerate either an embedded structure or a flat one.
    items: List[Dict[str, Any]] = []
    # The Lakeview app stores menu in `menu_categories` with embedded
    # `items[]`. Try that first (it's the canonical path), then fall back
    # to the older shapes for completeness.
    candidates = ("menu_categories", "menu_items", "menu")
    for col_name in candidates:
        try:
            col = getattr(db, col_name)
            cursor = col.find({}, {"_id": 0})
            async for row in cursor:
                # Embedded items[] shape (menu_categories, menu)
                cat_label = (row.get("display_name") or row.get("name")
                             or row.get("category") or row.get("slug") or "menu")
                embedded = row.get("items") or []
                if embedded:
                    for it in embedded:
                        if it.get("name"):
                            items.append({
                                "name": it.get("name"),
                                "price": it.get("price"),
                                "category": cat_label,
                                "item_key": it.get("item_key"),
                            })
                # Flat shape (menu_items)
                elif row.get("name"):
                    items.append({
                        "name": row.get("name"),
                        "price": row.get("price"),
                        "category": row.get("category", "menu"),
                        "item_key": row.get("item_key"),
                    })
            if items:
                break  # found rows in this collection
        except Exception:  # noqa: BLE001
            continue

    out["tried"] = len(items)
    if not items:
        return out

    scored = sorted(
        ((item, _score(food_type, item.get("name", ""))) for item in items),
        key=lambda x: x[1], reverse=True,
    )
    best_item, best_score = scored[0]
    runner_score = scored[1][1] if len(scored) > 1 else 0.0

    # Confidence must clear threshold AND beat the runner-up by ≥0.08
    if best_score < threshold or (best_score - runner_score) < 0.08:
        return out

    name = best_item.get("name")
    out.update({
        "matched": True,
        "name": name,
        "price": best_item.get("price"),
        "confidence": round(best_score, 3),
        "item_key": best_item.get("item_key") or _item_key(
            best_item.get("category", "menu"), name,
        ),
    })
    return out
