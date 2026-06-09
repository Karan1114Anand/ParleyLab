"""Move parser agent — converts user negotiation text to structured primitives."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parley_ai.llm.router import LLMRouter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

VALID_PRIMARY_MOVES = frozenset({
    "opening_anchor", "counteroffer", "concession",
    "bluff", "walk_away", "accept", "signal",
})

VALID_TONES = frozenset({"collaborative", "firm", "aggressive", "desperate"})

VALID_SIGNALS = frozenset({
    "competing_bid_disclosure",
    "bundled_demand",
    "time_pressure",
    "reciprocity_request",
})

_SAFE_DEFAULT: dict = {
    "primary_move": "signal",
    "offered_value": None,
    "signals":       [],
    "tone":          "collaborative",
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a negotiation move classifier. Given a message from a user in a \
salary/contract negotiation, extract structured primitives.

Return ONLY a JSON object with exactly these keys:

"primary_move": one of:
  "opening_anchor"  first numeric offer to anchor the negotiation
  "counteroffer"    a specific counter to the opponent's most recent position
  "concession"      moving toward the opponent without stating a new specific number
  "bluff"           ultimatum, false scarcity, or "final offer" pressure
  "walk_away"       ending or threatening to end the negotiation
  "accept"          explicitly accepting the current offer
  "signal"          sharing information or probing without a specific offer

"offered_value": the numeric value offered (e.g. 92000 for "92K"), or null

"signals": array of zero or more of:
  "competing_bid_disclosure"  mentions another offer or alternative
  "bundled_demand"            packages a non-monetary ask with the offer
  "time_pressure"             references a deadline or urgency
  "reciprocity_request"       explicitly asks for something in return

"tone": one of "collaborative", "firm", "aggressive", "desperate"

EXAMPLES

Input: "I'm thinking 95K would be fair for this role."
Output: {"primary_move": "opening_anchor", "offered_value": 95000, "signals": [], "tone": "firm"}

Input: "I appreciate the offer. I have a competing bid at 85K — I could do 92K if you include relocation."
Output: {"primary_move": "counteroffer", "offered_value": 92000, "signals": ["competing_bid_disclosure", "bundled_demand"], "tone": "collaborative"}

Input: "I'm walking away if you can't improve by end of day."
Output: {"primary_move": "walk_away", "offered_value": null, "signals": ["time_pressure"], "tone": "aggressive"}

Input: "I was thinking somewhere in the high 80s."
Output: {"primary_move": "opening_anchor", "offered_value": 88000, "signals": [], "tone": "collaborative"}

Input: "I'd take 90K with 25 days PTO — offered_value is the salary number only."
Output: {"primary_move": "counteroffer", "offered_value": 90000, "signals": ["bundled_demand"], "tone": "collaborative"}

Input: "100K or I walk — that's my final number."
Output: {"primary_move": "bluff", "offered_value": 100000, "signals": [], "tone": "aggressive"}
"""

# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def parse_move(
    user_message: str,
    history: list[dict],
    llm: "LLMRouter | None" = None,
) -> dict:
    """Convert a free-form user negotiation message into structured primitives.

    Uses an LLM to extract the negotiation intent, any numeric offer value,
    tactical signals, and conversational tone from the user's raw text. On
    JSON parse failure the function returns a safe default dict and logs a
    warning rather than crashing the pipeline.

    Args:
        user_message: The user's raw negotiation text for the current turn.
        history: Ordered list of prior messages in the session. Each element
            is a dict with keys ``"role"`` (``"user"`` or ``"opponent"``)
            and ``"content"`` (str). The last few turns are passed to the
            LLM as context so it can distinguish an opening anchor from a
            counteroffer.
        llm: An ``LLMRouter`` instance. When ``None`` a default router is
            constructed (reads provider/model from environment).

    Returns:
        A dict with exactly these keys:

        - ``primary_move`` (str): One of ``"opening_anchor"``,
          ``"counteroffer"``, ``"concession"``, ``"bluff"``,
          ``"walk_away"``, ``"accept"``, ``"signal"``.
        - ``offered_value`` (float | None): The numeric offer value, or
          ``None`` if none was stated.
        - ``signals`` (list[str]): Tactical signals from
          ``["competing_bid_disclosure", "bundled_demand",
          "time_pressure", "reciprocity_request"]``.
        - ``tone`` (str): One of ``"collaborative"``, ``"firm"``,
          ``"aggressive"``, ``"desperate"``.

    Raises:
        ValueError: If ``user_message`` is empty or whitespace-only.
        TypeError: If ``history`` is not a list.
        ConnectionError: If the LLM provider is unreachable (propagated
            from ``LLMRouter``; callers should catch and fall back).
    """
    if not user_message or not user_message.strip():
        raise ValueError("user_message must not be empty.")
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")

    if llm is None:
        from parley_ai.llm.router import LLMRouter
        llm = LLMRouter()

    # Pass the last 4 history messages as context so the LLM can determine
    # whether this is an opening anchor or a counteroffer.
    ctx: list[dict] = []
    for msg in history[-4:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            ctx.append({"role": "user", "content": content})
        elif role in ("opponent", "assistant"):
            ctx.append({"role": "assistant", "content": content})
    ctx.append({"role": "user", "content": user_message})

    _t0 = time.perf_counter()
    raw = llm.chat(
        system=SYSTEM_PROMPT,
        messages=ctx,
        json_mode=True,
        temperature=0.2,
    )
    log.info(
        "move_parser: provider=%s model=%s latency=%.2fs",
        getattr(llm, "provider", "unknown"),
        getattr(getattr(llm, "_client", None), "model", "unknown"),
        time.perf_counter() - _t0,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "Move parser: JSON parse failed (%s). Raw output: %.120r",
            exc, raw,
        )
        return dict(_SAFE_DEFAULT)

    return _sanitize(parsed)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize(raw: dict) -> dict:
    """Validate LLM output fields and substitute safe defaults for any invalid values."""
    primary_move = raw.get("primary_move", "signal")
    if primary_move not in VALID_PRIMARY_MOVES:
        log.warning("Move parser: invalid primary_move %r — defaulting to 'signal'", primary_move)
        primary_move = "signal"

    offered_value = raw.get("offered_value")
    if offered_value is not None:
        try:
            offered_value = float(offered_value)
        except (TypeError, ValueError):
            log.warning("Move parser: invalid offered_value %r — setting to None", offered_value)
            offered_value = None

    signals = raw.get("signals", [])
    if not isinstance(signals, list):
        signals = []
    signals = [s for s in signals if s in VALID_SIGNALS]

    tone = raw.get("tone", "collaborative")
    if tone not in VALID_TONES:
        log.warning("Move parser: invalid tone %r — defaulting to 'collaborative'", tone)
        tone = "collaborative"

    return {
        "primary_move":  primary_move,
        "offered_value": offered_value,
        "signals":       signals,
        "tone":          tone,
    }
