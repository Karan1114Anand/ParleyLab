"""Opponent agent — generates natural-language replies for the AI negotiation counterpart."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parley_ai.llm.router import LLMRouter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persona system prompt template
# ---------------------------------------------------------------------------

PERSONA_SYSTEM_PROMPT_TEMPLATE = """\
You are playing the role of a negotiation counterpart. Your character: {persona}.
Your urgency level is {urgency}.

Your strategic move for this turn is: **{action_name}**
{offer_line}
How to execute each move:
- Hold Firm: Politely decline to move from your current position. Give a brief, confident \
reason without revealing any private threshold numbers.
- Concede Small: Nudge very slightly toward their position. Frame it as a reluctant \
stretch — something you're doing to keep talks alive, not because you're comfortable.
- Concede Large: Move meaningfully toward their position. Frame it explicitly as a \
one-time, exceptional gesture you won't repeat.
- Bluff: Refuse to move and subtly imply your alternative is stronger than theirs. \
Do NOT state your actual walk-away threshold.
- Walk Away: Politely but firmly signal that you are ending the negotiation. Wish them well.

Rules:
- Reply in 1–3 sentences only. Verbose opponents are annoying.
- Stay fully in character. No meta-commentary, no stage directions.
- NEVER mention your target value or walk-away threshold.
- If you have a current offer to state, include it naturally in your reply.
- Output only your spoken reply — no JSON, no "Opponent says:" prefix, no labels.
- Let your persona shape the vocabulary and register throughout.
"""

# ---------------------------------------------------------------------------
# Fallback templates (used when LLM is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK_TEMPLATES: dict[str, str] = {
    "Hold Firm": (
        "I hear where you're coming from, but our position reflects what's "
        "feasible right now — I'm not in a position to move on that."
    ),
    "Concede Small": (
        "You've raised some fair points. Let me see if I can stretch just a "
        "touch — I want to keep this conversation going."
    ),
    "Concede Large": (
        "You've made a compelling case, and I genuinely want to get this done. "
        "I'm willing to make a meaningful move as a one-time gesture."
    ),
    "Bluff": (
        "I've had to reassess the situation on my end, and honestly I have "
        "less flexibility than I'd hoped — my alternatives are looking stronger."
    ),
    "Walk Away": (
        "I've given this serious consideration, but I don't think we can find "
        "terms that work for both sides — I'm going to have to step away."
    ),
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_fallback(action_name: str, current_offer: float | None, value_unit: str) -> str:
    """Build a fallback reply that embeds the specific offer number when available."""
    if current_offer is not None and action_name in ("Concede Small", "Concede Large"):
        offer_str = f"{int(current_offer):,} {value_unit}".strip()
        if action_name == "Concede Small":
            return (
                f"I've looked at what's possible and I can stretch to {offer_str} — "
                "that's a real push for us, but I want to keep talks alive."
            )
        else:
            return (
                f"You've made a strong case, and as a one-time gesture I'll go to {offer_str}. "
                "I can't go further — this is genuinely the ceiling."
            )
    return _FALLBACK_TEMPLATES.get(action_name, _FALLBACK_TEMPLATES["Hold Firm"])


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def generate_opponent_response(
    action: dict,
    hidden_context: dict,
    history: list[dict],
    parsed_user_move: dict,
    llm: "LLMRouter | None" = None,
) -> str:
    """Generate a natural-language opponent reply given a strategic action.

    The LLM is instructed to play the opponent's persona and execute the
    strategic move chosen by the RL policy. Hidden context (target, BATNA)
    informs tone only — those numbers must never appear in the reply.

    Args:
        action: Output of ``get_strategic_action()`` — must contain
            ``"action_name"`` (str).
        hidden_context: Opponent's private scenario data with keys
            ``"target"`` (float), ``"batna"`` (float),
            ``"persona"`` (str), ``"urgency"`` (str).
        history: Full ordered conversation so far, including the current user
            turn as the final entry. Each element has ``"role"``
            (``"user"`` or ``"opponent"``) and ``"content"`` (str).
        parsed_user_move: Output of ``parse_move()`` for the current turn.
        llm: An ``LLMRouter`` instance. When ``None`` a default router is
            constructed from environment variables.

    Returns:
        A single string — the opponent's natural-language reply, safe to
        send directly to the chat UI.

    Raises:
        ConnectionError: If the LLM provider is unreachable (propagated
            from ``LLMRouter``; caller should catch and fall back).
    """
    action_name = action.get("action_name", "Hold Firm")
    persona = hidden_context.get("persona", "Professional negotiator")
    urgency = hidden_context.get("urgency", "Moderate")
    user_name = hidden_context.get("user_name", "")

    # Optional: include the specific numeric offer when the orchestrator provides it
    current_offer = hidden_context.get("current_offer")
    value_unit = hidden_context.get("value_unit", "")
    if current_offer is not None:
        offer_line = (
            f"REQUIRED: You MUST state the specific number "
            f"{int(current_offer):,} {value_unit} in your reply — do not omit it.\n"
        )
    else:
        offer_line = ""

    # If user name is provided, instruct the LLM to use it
    name_line = ""
    if user_name:
        name_line = (
            f"The person you are negotiating with is named {user_name}. "
            f"Address them by name naturally in your reply.\n"
        )

    if llm is None:
        import os
        from parley_ai.llm.router import LLMRouter
        llm = LLMRouter(model=os.getenv("PARLEYLAB_OPPONENT_MODEL"))

    system = PERSONA_SYSTEM_PROMPT_TEMPLATE.format(
        persona=persona,
        urgency=urgency,
        action_name=action_name,
        offer_line=offer_line,
    )
    # Append name instruction after the main template
    if name_line:
        system += "\n" + name_line

    # Build conversation context: up to the last 4 history entries (≈2 full turns).
    # history[-4:] includes the current user turn when it is the final entry,
    # which is the standard pipeline contract.
    messages: list[dict] = []
    for msg in history[-4:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role in ("opponent", "assistant"):
            messages.append({"role": "assistant", "content": content})

    # If history didn't include the current user turn, add a minimal prompt so
    # the LLM has something to respond to.
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": "I'd like to discuss the terms."})

    try:
        _t0 = time.perf_counter()
        reply = llm.chat(
            system=system,
            messages=messages,
            json_mode=False,
            temperature=0.7,
        )
        log.info(
            "opponent: provider=%s model=%s action=%s latency=%.2fs",
            getattr(llm, "provider", "unknown"),
            getattr(getattr(llm, "_client", None), "model", "unknown"),
            action_name,
            time.perf_counter() - _t0,
        )
        return reply.strip()
    except Exception as exc:
        log.warning(
            "Opponent agent: LLM call failed (%s) — using fallback template.",
            exc,
        )
        return _build_fallback(action_name, current_offer, value_unit)
