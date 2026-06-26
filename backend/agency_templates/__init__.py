"""Sprint 20 Phase 0 — Agency-Grade Template Slot System.

A second rendering pipeline that sits ALONGSIDE the procedural PIL engine.
Templates are JSON manifests + background PNG assets stored under
`agency_templates/manifests/` and `agency_templates/backgrounds/`. Each
manifest declares typed slots (photo / title / price / features / brand /
cta) with pre-positioned coordinates, fonts, colours and alignment rules.

The procedural engine remains the fallback. If a manifest references a
missing asset or fails schema validation, the renderer raises
`TemplateError` and the caller falls back to procedural compose.

Public surface:
    list_templates(category=None) -> List[TemplateSummary]
    load_template(template_id) -> Template
    pick_template_for(category, theme_hint) -> Optional[Template]

The actual compositor lives in `agency_renderer.py`.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger("uvicorn.error")

_ROOT = os.path.dirname(os.path.abspath(__file__))
MANIFESTS_DIR = os.path.join(_ROOT, "manifests")
BACKGROUNDS_DIR = os.path.join(_ROOT, "backgrounds")
OVERLAYS_DIR = os.path.join(_ROOT, "overlays")


class TemplateError(RuntimeError):
    """Manifest failed validation or referenced a missing asset."""


# Required top-level keys
_REQUIRED = ("id", "label", "category", "canvas", "background", "slots", "fallback_theme")
# Required slot kinds
_REQUIRED_SLOTS = ("photo", "title", "price", "brand")
# Optional slot kinds (validated only if present)
_OPTIONAL_SLOTS = ("features", "cta")


@dataclass
class Template:
    id: str
    label: str
    category: str
    best_use: str
    canvas: tuple  # (w, h)
    background_path: str
    overlay_paths: List[str]
    slots: Dict[str, Dict[str, Any]]
    safe_zones: List[Dict[str, int]]
    fallback_theme: str
    raw: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "best_use": self.best_use,
            "fallback_theme": self.fallback_theme,
            "canvas": list(self.canvas),
        }


def _validate(manifest: Dict[str, Any]) -> None:
    for k in _REQUIRED:
        if k not in manifest:
            raise TemplateError(f"manifest missing required key: {k}")
    if not isinstance(manifest["canvas"], list) or len(manifest["canvas"]) != 2:
        raise TemplateError("canvas must be [w, h]")
    slots = manifest["slots"]
    if not isinstance(slots, dict):
        raise TemplateError("slots must be an object")
    for kind in _REQUIRED_SLOTS:
        if kind not in slots:
            raise TemplateError(f"missing required slot: {kind}")
    # photo slot needs x/y/w/h
    photo = slots["photo"]
    for k in ("x", "y", "w", "h"):
        if k not in photo:
            raise TemplateError(f"photo slot missing {k}")
    # price slot needs cx/cy/radius
    price = slots["price"]
    for k in ("cx", "cy", "radius"):
        if k not in price:
            raise TemplateError(f"price slot missing {k}")


def load_template(template_id: str) -> Template:
    """Load + validate a manifest by id. Raises TemplateError on any failure."""
    path = os.path.join(MANIFESTS_DIR, f"{template_id}.json")
    if not os.path.exists(path):
        raise TemplateError(f"manifest not found: {template_id}")
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        raise TemplateError(f"manifest {template_id}: {e}") from e
    _validate(data)
    bg_path = os.path.join(BACKGROUNDS_DIR, data["background"])
    if not os.path.exists(bg_path):
        raise TemplateError(f"manifest {template_id}: background asset missing: {data['background']}")
    overlay_paths = []
    for ov in data.get("overlays", []) or []:
        asset = ov if isinstance(ov, str) else ov.get("asset")
        if not asset:
            continue
        full = os.path.join(OVERLAYS_DIR, asset)
        if not os.path.exists(full):
            # Overlays are optional — log + skip rather than fail the whole template.
            log.warning(f"[agency_templates] overlay missing for {template_id}: {asset}")
            continue
        overlay_paths.append(full)
    return Template(
        id=data["id"],
        label=data["label"],
        category=data["category"],
        best_use=data.get("best_use", ""),
        canvas=tuple(data["canvas"]),
        background_path=bg_path,
        overlay_paths=overlay_paths,
        slots=data["slots"],
        safe_zones=data.get("safe_zones", []) or [],
        fallback_theme=data["fallback_theme"],
        raw=data,
    )


def list_templates(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return manifests' summary metadata, filtered by category if given."""
    if not os.path.isdir(MANIFESTS_DIR):
        return []
    out: List[Dict[str, Any]] = []
    for fn in sorted(os.listdir(MANIFESTS_DIR)):
        if not fn.endswith(".json"):
            continue
        tid = fn[:-5]
        try:
            t = load_template(tid)
        except TemplateError as e:
            log.warning(f"[agency_templates] skipping {tid}: {e}")
            continue
        if category and t.category != category:
            continue
        out.append(t.summary())
    return out


def pick_template_for(category: Optional[str], theme_hint: Optional[str] = None) -> Optional[Template]:
    """Pick a template best matching the inferred category. Returns None if
    none match — caller should fall back to procedural compose.

    Selection rule (priority order):
      1. theme_hint match against `fallback_theme` (exact)
      2. category match
      3. category == 'general'
    """
    # Walk all valid manifests.
    valid: List[Template] = []
    for tid in [fn[:-5] for fn in os.listdir(MANIFESTS_DIR) if fn.endswith(".json")] if os.path.isdir(MANIFESTS_DIR) else []:
        try:
            valid.append(load_template(tid))
        except TemplateError:
            continue
    if not valid:
        return None
    if theme_hint:
        for t in valid:
            if t.fallback_theme == theme_hint:
                return t
    if category:
        for t in valid:
            if t.category == category:
                return t
    for t in valid:
        if t.category == "general":
            return t
    return valid[0]
