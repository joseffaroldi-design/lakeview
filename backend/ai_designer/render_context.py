"""Sprint 22G — RenderContext.

A single, immutable bundle of per-render data + a deterministic RNG.

Every renderer (HTML, agency template, procedural overlay layer) receives
the same `RenderContext` instance. Within a renderer, any randomness MUST
be sourced from `ctx.rng(salt=...)` so:

  * The same `(job_nonce, variant_index)` always produces the same flyer
    (reproducible).
  * A new `job_nonce` (one per regeneration) shuffles every design choice
    that was salted with it (visible diversity).
  * Independent stages (photo placement vs. title alignment vs. badge
    corner) get independent RNG streams via the `salt` argument, so a
    change in one stage cannot cascade-perturb another.

The RNG salts variation through DESIGN DECISIONS — photo offset, badge
corner, feature order, overlay subset, background filter — never through
visible pixel noise. That's what the Sprint 22G mandate calls for.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RenderContext:
    job_nonce: int = 0
    variant_index: int = 0
    theme_id: str = ""
    layout: str = ""
    platform: str = "instagram_post"
    item_name: str = ""
    features: tuple = ()
    price: str = ""
    cta: str = ""
    brand: str = "LAKEVIEW BURGERS & SEAFOOD"
    extra: Dict[str, Any] = field(default_factory=dict)

    # ----- RNG -----

    def rng(self, salt: str = "") -> random.Random:
        """Return a fresh `random.Random` seeded from (job_nonce, variant_index, salt).

        Two callers in the same render pass with the same `salt` will see
        the same sequence; with different `salt` they'll see independent
        sequences. Salting prevents one stage's choices from cascading
        into another's — e.g. changing the title alignment logic doesn't
        suddenly shift the food photo position. Both stages stay
        reproducible per (job_nonce, variant_index) but evolve
        independently.
        """
        seed = hash((self.job_nonce, self.variant_index, salt)) & 0xFFFFFFFF
        return random.Random(seed)

    # ----- Compatibility shim for the overlay TLS path -----
    # `_overlays._rng()` reads a thread-local nonce. Renderers that touch
    # `compose_layered_with_score` / overlay_fn still go through that
    # path, so the same nonce is bound there too via `set_overlay_nonce`.

    @property
    def overlay_nonce(self) -> int:
        return (self.job_nonce ^ (self.variant_index * 2654435761)) & 0xFFFFFFFF


def default_context() -> RenderContext:
    """Sprint 22G — fallback context used when a renderer is invoked
    directly (e.g. unit tests, regression snapshots, legacy callers).

    `job_nonce=0` + `variant_index=0` reproduces the pre-22G byte-identical
    output, so the snapshot test suite remains untouched.
    """
    return RenderContext()
