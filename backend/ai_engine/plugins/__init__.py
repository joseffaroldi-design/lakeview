"""Industry plugins for the AI Marketing Engine.

A plugin is a registered module that bundles:
  • an `id` (e.g. "restaurant", "moving", "event", "retail", "service")
  • a human label and description
  • a list of supported "templates" (campaign archetypes)
  • a list of supported "actions" (one-click multi-channel flows)
  • a context-builder that turns a domain object (menu item, listing, event)
    into a normalized brief consumable by the core generators.

Core generators (ai_engine.generators) MUST NOT contain industry logic.
All industry-specific prompt enrichment lives inside the plugin.
"""
from .base import Plugin, register_plugin, list_plugins, get_plugin
from . import restaurant  # noqa: F401 — registers itself on import

__all__ = ["Plugin", "register_plugin", "list_plugins", "get_plugin"]
