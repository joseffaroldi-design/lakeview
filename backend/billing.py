"""Self-tracked LLM budget layer (Billing Resilience Sprint).

WHY THIS EXISTS
---------------
Emergent's Universal LLM Key budget is platform-managed; there is no public
API to read remaining balance from backend code. The only signal is a 402
returned from a failed call (handled by `errors.classify_llm_error`).

To give the owner a visible "balance" + pre-flight gating, we maintain a
*virtual* budget in MongoDB:
  - `billing_state` collection: monthly_cap_usd, current_balance_usd, threshold
  - `llm_usage` collection: append-only ledger of every estimated LLM cost

The virtual balance WILL drift from Emergent's true balance over time.
The owner has a one-click "I just topped up" button on Home that resets the
virtual balance to the cap.

THRESHOLDS (per Billing Resilience Sprint spec)
  < $1   = yellow warning
  < $0.50 = red warning
  = $0  = block generation

TELEMETRY
  BUDGET_CHECK_START / PASS / FAIL
  BUDGET_WARNING_SHOWN  (frontend-emitted)
  LLM_USAGE_RECORDED
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------- Pricing
# Public USD pricing for the models actively used in this codebase.
# Update these when provider pricing changes. Conservative estimates.
TEXT_PRICING_PER_1M: Dict[str, Tuple[float, float]] = {
    # (input_per_1m, output_per_1m)
    "gpt-5":       (1.25, 10.00),  # default for chat completion via emergentintegrations
    "gpt-5.2":     (1.25, 10.00),
    "gpt-4o":      (2.50,  10.00),
    "gpt-4o-mini": (0.15,  0.60),
    "claude-sonnet-4-5": (3.00, 15.00),
    "gemini-2.5-flash":  (0.30,  2.50),
}

# Flat per-image pricing for gpt-image-1 (the only image model in use).
# Source: OpenAI Image Gen pricing — medium quality ≈ $0.042, high ≈ $0.080
IMAGE_PRICING_PER_IMAGE: Dict[str, float] = {
    "gpt-image-1:low":    0.011,
    "gpt-image-1:medium": 0.042,
    "gpt-image-1:high":   0.080,
}

# Average tokens per marketing-pack pipeline (measured from production runs):
#   inferring step: ~400 in, ~80 out
#   writing_copy step: ~700 in, ~600 out
# Total: ~1100 in, ~680 out via gpt-5
MARKETING_PACK_TEXT_INPUT_TOKENS = 1100
MARKETING_PACK_TEXT_OUTPUT_TOKENS = 680


def estimate_text_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of a text completion. Defaults to gpt-5 pricing if model unknown."""
    in_per_1m, out_per_1m = TEXT_PRICING_PER_1M.get(model, TEXT_PRICING_PER_1M["gpt-5"])
    return (input_tokens / 1_000_000.0) * in_per_1m + (output_tokens / 1_000_000.0) * out_per_1m


def estimate_image_cost(model: str = "gpt-image-1", quality: str = "medium", count: int = 1) -> float:
    """USD cost of image generation."""
    key = f"{model}:{quality}"
    per_image = IMAGE_PRICING_PER_IMAGE.get(key, IMAGE_PRICING_PER_IMAGE["gpt-image-1:medium"])
    return per_image * count


def estimate_marketing_pack_cost() -> Dict[str, float]:
    """Itemized estimate for a single marketing-pack run.

    The pack does:
      - 2 LLM text calls (gpt-5): inferring + writing_copy
      - 0 LLM image calls (resizes the source image to 4 formats — local PIL, free)
      - 0 LLM video calls (ffmpeg slideshow — local, free)
    """
    text = estimate_text_cost("gpt-5",
                              MARKETING_PACK_TEXT_INPUT_TOKENS,
                              MARKETING_PACK_TEXT_OUTPUT_TOKENS)
    return {
        "text_cost": round(text, 4),
        "image_cost": 0.0,
        "video_cost": 0.0,
        "total_cost": round(text, 4),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- State

# Default monthly cap if env var not set. Owner can override BILLING_MONTHLY_CAP_USD.
DEFAULT_MONTHLY_CAP_USD = float(os.environ.get("BILLING_MONTHLY_CAP_USD", "4.00"))
LOW_BALANCE_USD = 1.00
CRITICAL_BALANCE_USD = 0.50


async def ensure_state(db) -> Dict[str, Any]:
    """Load or initialize the singleton billing_state document."""
    state = await db.billing_state.find_one({"_id": "global"})
    if state:
        return state
    state = {
        "_id": "global",
        "monthly_cap_usd": DEFAULT_MONTHLY_CAP_USD,
        "current_balance_usd": DEFAULT_MONTHLY_CAP_USD,
        "low_balance_threshold_usd": LOW_BALANCE_USD,
        "critical_balance_threshold_usd": CRITICAL_BALANCE_USD,
        "last_reset_at": _now(),
        "created_at": _now(),
    }
    await db.billing_state.insert_one(state)
    logger.info("BILLING_STATE_INITIALIZED cap=$%.2f", DEFAULT_MONTHLY_CAP_USD)
    return state


async def get_status(db) -> Dict[str, Any]:
    """Return current billing status for the Home dashboard."""
    state = await ensure_state(db)
    bal = float(state["current_balance_usd"])
    cap = float(state["monthly_cap_usd"])
    pack_cost = estimate_marketing_pack_cost()["total_cost"]
    packs_remaining = int(bal / pack_cost) if pack_cost > 0 else 0

    if bal <= 0:
        tier = "blocked"
    elif bal < CRITICAL_BALANCE_USD:
        tier = "critical"
    elif bal < LOW_BALANCE_USD:
        tier = "low"
    else:
        tier = "healthy"

    return {
        "current_balance_usd": round(bal, 4),
        "monthly_cap_usd": round(cap, 2),
        "estimated_pack_cost_usd": pack_cost,
        "estimated_packs_remaining": packs_remaining,
        "low_balance_threshold_usd": LOW_BALANCE_USD,
        "critical_balance_threshold_usd": CRITICAL_BALANCE_USD,
        "tier": tier,
        "is_blocked": bal <= 0,
        "is_low": bal < LOW_BALANCE_USD,
        "is_critical": bal < CRITICAL_BALANCE_USD,
        "last_reset_at": state.get("last_reset_at"),
    }


async def check_can_afford(db, estimated_cost: float, surface: str) -> Tuple[bool, Dict[str, Any]]:
    """Pre-flight check. Returns (can_afford, status_dict).

    `surface` is a freeform label for structured logs (e.g. "marketing_pack", "ai_image").
    Logs BUDGET_CHECK_START + BUDGET_CHECK_PASS|FAIL with cost + remaining balance.
    """
    logger.info("BUDGET_CHECK_START surface=%s estimated_cost=$%.4f", surface, estimated_cost)
    status = await get_status(db)
    bal = status["current_balance_usd"]
    can = bal >= estimated_cost and not status["is_blocked"]
    if can:
        logger.info("BUDGET_CHECK_PASS surface=%s balance=$%.4f cost=$%.4f remaining_after=$%.4f",
                    surface, bal, estimated_cost, bal - estimated_cost)
    else:
        logger.warning("BUDGET_CHECK_FAIL surface=%s balance=$%.4f required=$%.4f",
                       surface, bal, estimated_cost)
    return can, status


async def record_usage(
    db,
    *,
    surface: str,
    model: str,
    operation: str,
    cost_usd: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    image_count: int = 0,
    pipeline_id: Optional[str] = None,
) -> float:
    """Record an LLM usage event and decrement the virtual balance. Returns new balance."""
    state = await ensure_state(db)
    new_balance = max(0.0, float(state["current_balance_usd"]) - cost_usd)
    await db.billing_state.update_one(
        {"_id": "global"},
        {"$set": {"current_balance_usd": new_balance, "updated_at": _now()}},
    )
    await db.llm_usage.insert_one({
        "id": str(uuid.uuid4()),
        "surface": surface,
        "model": model,
        "operation": operation,
        "cost_usd": round(cost_usd, 6),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "image_count": image_count,
        "pipeline_id": pipeline_id,
        "balance_after_usd": round(new_balance, 4),
        "created_at": _now(),
    })
    logger.info(
        "LLM_USAGE_RECORDED surface=%s model=%s op=%s cost=$%.6f balance_after=$%.4f",
        surface, model, operation, cost_usd, new_balance,
    )
    return new_balance


async def reset_balance(db) -> Dict[str, Any]:
    """One-click 'I just topped up Emergent' reset. Sets virtual balance back to cap."""
    state = await ensure_state(db)
    cap = float(state["monthly_cap_usd"])
    await db.billing_state.update_one(
        {"_id": "global"},
        {"$set": {"current_balance_usd": cap, "last_reset_at": _now()}},
    )
    logger.info("BILLING_RESET balance_restored_to=$%.2f", cap)
    return await get_status(db)


async def set_cap(db, new_cap_usd: float) -> Dict[str, Any]:
    """Admin: change the monthly cap (e.g. you bought more Emergent credits)."""
    new_cap_usd = max(0.0, float(new_cap_usd))
    await db.billing_state.update_one(
        {"_id": "global"},
        {"$set": {"monthly_cap_usd": new_cap_usd,
                  "current_balance_usd": new_cap_usd,
                  "last_reset_at": _now()}},
        upsert=True,
    )
    logger.info("BILLING_CAP_UPDATED new_cap=$%.2f", new_cap_usd)
    return await get_status(db)
