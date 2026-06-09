"""LLM client wrapper. Model can be swapped at runtime via DB config."""
import os
import json
import logging
import re
import uuid
from typing import Any, Dict, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

# Default fallback if no DB config — user said GPT-5 explicitly
DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5"


async def get_active_model(db) -> Dict[str, str]:
    """Return {'provider': ..., 'model': ...} from `ai_config` collection, or defaults."""
    cfg = await db.ai_config.find_one({"_id": "active"}, {"_id": 0})
    if cfg and cfg.get("provider") and cfg.get("model"):
        return {"provider": cfg["provider"], "model": cfg["model"]}
    return {"provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL}


async def set_active_model(db, provider: str, model: str) -> Dict[str, str]:
    """Persist new active model selection (used by future settings panel)."""
    await db.ai_config.update_one(
        {"_id": "active"},
        {"$set": {"provider": provider, "model": model}},
        upsert=True,
    )
    return {"provider": provider, "model": model}


def _build_chat(system_message: str, provider: str, model: str, session_id: Optional[str] = None) -> LlmChat:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id or str(uuid.uuid4()),
        system_message=system_message,
    ).with_model(provider, model)
    return chat


def _strip_code_fences(text: str) -> str:
    """LLMs sometimes wrap JSON in ```json ... ```. Strip it."""
    s = text.strip()
    if s.startswith("```"):
        # remove opening fence (with optional language label)
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", s)
        # remove closing fence
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


async def generate_structured(
    db,
    *,
    system_prompt: str,
    user_prompt: str,
    schema_hint: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a structured-JSON generation against the active model.

    Returns the parsed JSON dict. Raises if parsing fails.
    """
    active = await get_active_model(db)

    full_system = (
        system_prompt
        + "\n\nYou MUST respond with ONLY a valid JSON object that matches this schema:\n"
        + schema_hint
        + "\nDo NOT include code fences, prose, or commentary — only the JSON object."
    )

    chat = _build_chat(full_system, active["provider"], active["model"], session_id)

    try:
        raw = await chat.send_message(UserMessage(text=user_prompt))
    except AttributeError:
        # Fallback: some versions only expose stream_message
        from emergentintegrations.llm.chat import TextDelta, StreamDone
        chunks = []
        async for ev in chat.stream_message(UserMessage(text=user_prompt)):
            if isinstance(ev, TextDelta):
                chunks.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
        raw = "".join(chunks)

    cleaned = _strip_code_fences(raw if isinstance(raw, str) else str(raw))

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Try to extract the first {...} block defensively
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            parsed = json.loads(match.group(0))
        else:
            logger.error("AI returned non-JSON content: %s", cleaned[:300])
            raise RuntimeError(f"AI response was not valid JSON: {e}") from e

    return {
        "data": parsed,
        "model_used": f"{active['provider']}/{active['model']}",
        "raw": cleaned,
    }
