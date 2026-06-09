"""Plugin base class + registry for the AI Marketing Engine.

A plugin contributes:
  - templates: list of campaign template dicts {id, label, defaults}
  - actions: list of one-click flows {id, label, channels, brief_template}
  - build_brief(context, action_id) -> dict: turns a domain object into a
    normalized brief for a specific channel/action.

The core engine never imports concrete plugins; it goes through the registry.
"""
from typing import Any, Callable, Dict, List, Optional


class Plugin:
    """Industry plugin definition."""

    def __init__(
        self,
        *,
        id: str,
        label: str,
        description: str,
        templates: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        build_brief: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> None:
        self.id = id
        self.label = label
        self.description = description
        self.templates = templates
        self.actions = actions
        self._build_brief = build_brief
        self.system_prompt = system_prompt

    def build_brief(self, context: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        """Compose a per-channel brief from a context object + action descriptor."""
        return self._build_brief(context, action)

    def to_public(self) -> Dict[str, Any]:
        """JSON-safe descriptor for the frontend."""
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "templates": self.templates,
            "actions": self.actions,
        }


# ---- Registry ----

_REGISTRY: Dict[str, Plugin] = {}


def register_plugin(plugin: Plugin) -> Plugin:
    _REGISTRY[plugin.id] = plugin
    return plugin


def get_plugin(plugin_id: str) -> Optional[Plugin]:
    return _REGISTRY.get(plugin_id)


def list_plugins() -> List[Dict[str, Any]]:
    return [p.to_public() for p in _REGISTRY.values()]
