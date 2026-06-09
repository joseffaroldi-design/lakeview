"""Reusable AI marketing engine — industry-agnostic core.

Designed for multi-business reuse:
  - Lakeview Burgers & Seafood (Restaurant mode)
  - Moving Company CRM (Moving mode — future)
  - KreweHQ Event platform (Event mode — future)
  - Generic SaaS / Retail / Service (default)

The core engine handles prompt assembly, LLM calls, and structured output parsing.
Industry-specific modules under ./industries/ contribute templates + system prompts.
"""
