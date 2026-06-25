"""Sprint 16F — Theme Pack registry.

Loads every pack module, validates each theme, and exposes:

    THEME_STYLES  : flat dict { theme_id -> theme_spec }  (router uses this)
    THEME_META    : flat dict { theme_id -> {pack, pack_label, category, best_use} }
    PACKS         : list of pack metadata (id, label, category, theme_ids)
    WARNINGS      : list[str] surfaced from validation

Validation rules (Sprint 16F):
  * Duplicate theme IDs → second occurrence dropped, warning emitted.
  * Missing required keys (bg_color/title/body/price) → theme dropped.
  * Color fields must be 3- or 4-tuples of 0-255 ints → invalid themes dropped.
  * Packs with `enabled=False` are skipped entirely.

To add a new pack: drop a `<name>_pack.py` next to this file exposing
top-level `PACK` (dict) and `THEMES` (dict). `_PACK_MODULES` below is the
ordered registry — append your import there.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from . import (
    burger_pack,
    classic_pack,
    flyer_pack,
    game_day_pack,
    seafood_pack,
    seasonal_pack,
)

logger = logging.getLogger("uvicorn.error")

# Order = display order in the UI / API response.
_PACK_MODULES = [
    classic_pack,
    flyer_pack,
    burger_pack,
    seafood_pack,
    game_day_pack,
    seasonal_pack,
]

_REQUIRED_KEYS = ("bg_color", "title", "body", "price", "branding_color")


def _is_color(v: Any) -> bool:
    if not isinstance(v, tuple) or len(v) not in (3, 4):
        return False
    return all(isinstance(c, int) and 0 <= c <= 255 for c in v)


def _validate_theme(tid: str, spec: Dict[str, Any]) -> Tuple[bool, str]:
    for k in _REQUIRED_KEYS:
        if k not in spec:
            return False, f"theme '{tid}' missing required key '{k}'"
    if not _is_color(spec["bg_color"]):
        return False, f"theme '{tid}' has invalid bg_color"
    for sub in ("title", "body"):
        s = spec.get(sub, {})
        if not isinstance(s, dict):
            return False, f"theme '{tid}'.{sub} must be a dict"
        if "color" in s and not _is_color(s["color"]):
            return False, f"theme '{tid}'.{sub}.color invalid"
    return True, ""


def _load() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, str]],
                     List[Dict[str, Any]], List[str]]:
    themes: Dict[str, Dict[str, Any]] = {}
    meta: Dict[str, Dict[str, str]] = {}
    packs: List[Dict[str, Any]] = []
    warnings: List[str] = []

    seen_ids: set[str] = set()
    seen_pack_ids: set[str] = set()

    for mod in _PACK_MODULES:
        pack = getattr(mod, "PACK", None)
        pack_themes = getattr(mod, "THEMES", None)
        if not isinstance(pack, dict) or not isinstance(pack_themes, dict):
            warnings.append(f"pack module '{mod.__name__}' missing PACK/THEMES")
            continue
        if not pack.get("enabled", True):
            logger.info("[theme_packs] skipping disabled pack '%s'", pack.get("id"))
            continue
        pid = pack.get("id")
        if not pid or not isinstance(pid, str):
            warnings.append(f"pack module '{mod.__name__}' has no string PACK['id']")
            continue
        if pid in seen_pack_ids:
            warnings.append(f"duplicate pack id '{pid}' — second occurrence skipped")
            continue
        seen_pack_ids.add(pid)

        accepted_ids: List[str] = []
        for tid, spec in pack_themes.items():
            if tid in seen_ids:
                warnings.append(f"duplicate theme id '{tid}' in pack '{pid}' — skipped")
                continue
            ok, why = _validate_theme(tid, spec)
            if not ok:
                warnings.append(f"pack '{pid}': {why}")
                continue
            seen_ids.add(tid)
            themes[tid] = spec
            meta[tid] = {
                "pack": pid,
                "pack_label": pack.get("label", pid),
                "category": pack.get("category", ""),
                "best_use": spec.get("best_use", ""),
            }
            accepted_ids.append(tid)

        packs.append({
            "id": pid,
            "label": pack.get("label", pid),
            "category": pack.get("category", ""),
            "description": pack.get("description", ""),
            "theme_ids": accepted_ids,
        })

    for w in warnings:
        logger.warning("[theme_packs] %s", w)
    logger.info("[theme_packs] loaded %d themes across %d packs", len(themes), len(packs))
    return themes, meta, packs, warnings


THEME_STYLES, THEME_META, PACKS, WARNINGS = _load()
