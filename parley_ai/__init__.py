"""
parley_ai — AI/ML layer for the ParleyLab negotiation simulator.

Public interface (5 functions):
    parse_move                  User text → structured negotiation move
    get_strategic_action        7-dim state vector → RL policy action
    generate_opponent_response  RL action + context → natural-language reply
    get_critic_feedback         User move + history → structured critique
    score_session               Full history → end-of-session performance score

Only these five names are exported.  Internal helpers, LLMRouter,
StrategyPolicy, and all agent implementations remain private to their
own modules.
"""

from __future__ import annotations

import random
import re

__all__ = [
    "parse_move",
    "get_strategic_action",
    "generate_opponent_response",
    "get_critic_feedback",
    "score_session",
]

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------

import logging as _logging
_log = _logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal constants — fallback data only, not part of the public API
# ---------------------------------------------------------------------------

_ACTION_MAP: dict[int, tuple[str, str]] = {
    0: ("Hold Firm",     "Maintain current position; signal confidence."),
    1: ("Concede Small", "Move 5% toward the opponent's position."),
    2: ("Concede Large", "Move 15% toward the opponent's position."),
    3: ("Bluff",         "Move 5% away from opponent to imply a stronger BATNA."),
    4: ("Walk Away",     "End negotiation and take BATNA."),
}

_OPPONENT_TEMPLATES: dict[str, str] = {
    "Hold Firm": (
        "I appreciate your perspective, but our offer reflects what we can do "
        "within current constraints.  I'd like to find a way forward together, "
        "but the number itself needs to stay where it is."
    ),
    "Concede Small": (
        "You've made some good points.  Let me see what I can do — I think I "
        "can stretch a bit to meet you closer to the middle."
    ),
    "Concede Large": (
        "You've raised compelling arguments and I want to get this done.  I'm "
        "willing to move meaningfully on this to reach an agreement."
    ),
    "Bluff": (
        "I've had some internal conversations since we last spoke, and honestly "
        "my flexibility here is tighter than I'd hoped.  The situation has shifted."
    ),
    "Walk Away": (
        "I've given this a great deal of thought.  I don't believe we can reach "
        "terms that work for both sides, so I'm going to have to respectfully "
        "step away."
    ),
}

_FEEDBACK_POOL: list[dict] = [
    {
        "strengths":   ["Anchored above target before conceding",
                        "Maintained composure under pressure"],
        "weaknesses":  ["Revealed competing-bid value too early"],
        "suggestion":  (
            "Withhold the competing-bid number — disclose its existence first "
            "and leverage the ambiguity before naming a figure."
        ),
        "concept_tag": "anchoring",
    },
    {
        "strengths":   ["Bundled a non-monetary demand effectively"],
        "weaknesses":  ["Conceded without extracting a reciprocal move"],
        "suggestion":  (
            "Always ask for something in return before conceding — even a small "
            "ask signals that you expect reciprocity."
        ),
        "concept_tag": "reciprocity",
    },
    {
        "strengths":   ["Held firm when the opponent applied pressure"],
        "weaknesses":  ["Did not acknowledge the opponent's concern before countering"],
        "suggestion":  (
            "Label the opponent's concern before presenting your counter — it "
            "reduces defensiveness and makes them more receptive."
        ),
        "concept_tag": "concession_pacing",
    },
    {
        "strengths":   ["Used silence and a firm anchor effectively"],
        "weaknesses":  ["Opened too close to your target, leaving no room to concede"],
        "suggestion":  (
            "Open 15–20% above your real target so you have room to appear "
            "reasonable when you eventually move."
        ),
        "concept_tag": "anchoring",
    },
]

_SCORE_FALLBACK: dict = {
    "score":      50,
    "rating":     "Fair",
    "best_move":  {"turn": 1, "summary": "Opening move",
                   "reason": "Score could not be computed — using safe default."},
    "worst_move": {"turn": 1, "summary": "Opening move",
                   "reason": "Score could not be computed — using safe default."},
}

# ---------------------------------------------------------------------------
# Lazy singleton — StrategyPolicy loaded on first call, cached for process
# ---------------------------------------------------------------------------

_policy = None


def _get_policy():
    global _policy
    if _policy is None:
        from parley_ai.rl.policy import StrategyPolicy
        _policy = StrategyPolicy()
    return _policy


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def parse_move(user_message: str, history: list[dict]) -> dict:
    """Convert a free-form user message into a structured negotiation move.

    Delegates to the LLM-powered agent in ``parley_ai.agents.move_parser``.
    If the LLM provider is unreachable or times out, falls back to a
    heuristic keyword parser so the pipeline keeps running.

    Args:
        user_message: The user's raw negotiation text for the current turn.
        history: Ordered list of previous messages.  Each element is a dict
            with keys ``"role"`` (``"user"`` or ``"opponent"``) and
            ``"content"`` (str).

    Returns:
        ``{"primary_move": str, "offered_value": float|None,
           "signals": list[str], "tone": str}``

    Raises:
        ValueError: If ``user_message`` is empty or whitespace-only.
        TypeError: If ``history`` is not a list.
    """
    if not user_message or not user_message.strip():
        raise ValueError("user_message must not be empty.")
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")

    try:
        from parley_ai.agents.move_parser import parse_move as _agent_parse
        return _agent_parse(user_message, history)
    except (ConnectionError, TimeoutError) as exc:
        _log.warning("parse_move: LLM unavailable (%s) — heuristic fallback.", exc)

    # Heuristic fallback
    msg = user_message.lower()
    # Prefer plain numbers with optional commas ("92,000"); fall back to K-notation ("90K")
    _plain = re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", user_message)
    if _plain:
        offered_value: float | None = float(_plain[0].replace(",", ""))
    else:
        _km = re.search(r"\b(\d[\d,]*)\s*[Kk]\b", user_message)
        offered_value = float(_km.group(1).replace(",", "")) * 1000 if _km else None
    signals: list[str] = []
    if any(w in msg for w in ("competing", "other offer", "alternative bid")):
        signals.append("competing_bid_disclosure")
    if any(w in msg for w in ("relocation", "bonus", "equity", "stock", "vacation", "pto")):
        signals.append("bundled_demand")
    if any(w in msg for w in ("deadline", "friday", "by end of week", "today", "urgent")):
        signals.append("time_pressure")
    if any(w in msg for w in ("appreciate", "grateful", "would love", "please")):
        tone = "collaborative"
    elif any(w in msg for w in ("take it or leave", "final offer", "won't", "cannot")):
        tone = "aggressive"
    elif any(w in msg for w in ("must", "need", "require", "firm")):
        tone = "firm"
    else:
        tone = "collaborative"
    if any(w in msg for w in ("walking away", "walk away", "stepping back", "no deal")):
        primary_move = "walk_away"
    elif any(w in msg for w in ("i'll take", "accept", "agreed", "deal")):
        primary_move = "accept"
    elif any(w in msg for w in ("take it or leave", "final offer")):
        primary_move = "bluff"
    elif offered_value is not None and history:
        primary_move = "counteroffer"
    elif offered_value is not None:
        primary_move = "opening_anchor"
    else:
        primary_move = "signal"
    return {"primary_move": primary_move, "offered_value": offered_value,
            "signals": signals, "tone": tone}


def get_strategic_action(state_vector: list[float]) -> dict:
    """Determine the opponent's strategic action from the current game state.

    Consults the trained PPO policy to decide whether the opponent should
    hold firm, concede, bluff, or walk away.

    Args:
        state_vector: A 7-element list of floats, each in ``[0.0, 1.0]``.

            0. ``own_offer_norm``
            1. ``opponent_offer_norm``
            2. ``turn_norm``
            3. ``own_concession_rate``
            4. ``opponent_concession_rate``
            5. ``gap_norm``
            6. ``turns_since_last_concession_norm``

    Returns:
        ``{"action_id": int, "action_name": str, "description": str}``

        Action IDs: 0 Hold Firm · 1 Concede Small · 2 Concede Large ·
        3 Bluff · 4 Walk Away.

    Raises:
        TypeError: If ``state_vector`` is not a list.
        ValueError: If ``state_vector`` does not have exactly 7 elements,
            or any element is outside ``[0.0, 1.0]``.
    """
    if not isinstance(state_vector, list):
        raise TypeError(
            f"state_vector must be a list, got {type(state_vector).__name__}."
        )
    if len(state_vector) != 7:
        raise ValueError(
            f"state_vector must have exactly 7 elements, got {len(state_vector)}."
        )
    for i, v in enumerate(state_vector):
        if not isinstance(v, (int, float)):
            raise ValueError(
                f"state_vector[{i}] must be numeric, got {type(v).__name__}."
            )
        if not (0.0 <= float(v) <= 1.0):
            raise ValueError(
                f"state_vector[{i}] = {v} is outside [0.0, 1.0]."
            )
    try:
        return _get_policy().predict(state_vector)
    except Exception as exc:
        _log.error("get_strategic_action: policy predict failed (%s) — safe fallback.", exc)
        return {"action_id": 0, "action_name": "Hold Firm",
                "description": _ACTION_MAP[0][1]}


def generate_opponent_response(
    action: dict,
    hidden_context: dict,
    history: list[dict],
    parsed_user_move: dict,
    llm=None,
) -> str:
    """Translate a strategic action into a natural-language opponent reply.

    Args:
        action: Output of :func:`get_strategic_action`.  Must contain
            ``"action_name"`` (str).
        hidden_context: Opponent's private scenario data.  Expected keys:
            ``"persona"`` (str), ``"urgency"`` (str), ``"target"`` (float),
            ``"batna"`` (float).  Missing keys fall back to safe defaults.
        history: Full ordered conversation including the current user turn
            as the last entry.
        parsed_user_move: Output of :func:`parse_move` for the current turn.
        llm: ``LLMRouter`` instance.  When ``None``, constructed from env.

    Returns:
        A single natural-language string ready for the chat UI.

    Raises:
        TypeError: If ``action`` or ``hidden_context`` is not a dict.
        ValueError: If ``action`` does not contain ``"action_name"``.
    """
    if not isinstance(action, dict):
        raise TypeError(f"action must be a dict, got {type(action).__name__}.")
    if not isinstance(hidden_context, dict):
        raise TypeError(
            f"hidden_context must be a dict, got {type(hidden_context).__name__}."
        )
    if "action_name" not in action:
        raise ValueError(
            "action must contain the key 'action_name'.  "
            "Pass the output of get_strategic_action() directly."
        )
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")

    try:
        from parley_ai.agents.opponent import generate_opponent_response as _agent_reply
        return _agent_reply(action, hidden_context, history, parsed_user_move, llm=llm)
    except (ConnectionError, TimeoutError) as exc:
        _log.warning(
            "generate_opponent_response: LLM unavailable (%s) — template fallback.", exc
        )
    return _OPPONENT_TEMPLATES.get(
        action["action_name"], _OPPONENT_TEMPLATES["Hold Firm"]
    )


def get_critic_feedback(
    parsed_user_move: dict,
    history: list[dict],
) -> dict:
    """Evaluate the user's most recent move against negotiation theory.

    The critic has no access to opponent hidden state — it judges only
    observable user behaviour.  Falls back to a curated pool entry if the
    LLM is unavailable.

    Args:
        parsed_user_move: Output of :func:`parse_move` for the current turn.
            Expected keys: ``"primary_move"``, ``"offered_value"``,
            ``"signals"``, ``"tone"``.
        history: Full ordered conversation list including the current user
            turn as the final entry.

    Returns:
        ``{"strengths": list[str], "weaknesses": list[str],
           "suggestion": str, "concept_tag": str}``

    Raises:
        TypeError: If ``parsed_user_move`` is not a dict or ``history`` is
            not a list.
    """
    if not isinstance(parsed_user_move, dict):
        raise TypeError(
            f"parsed_user_move must be a dict, got {type(parsed_user_move).__name__}."
        )
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")

    try:
        from parley_ai.agents.critic import get_critic_feedback as _agent_critique
        return _agent_critique(parsed_user_move, history)
    except (ConnectionError, TimeoutError) as exc:
        _log.warning(
            "get_critic_feedback: LLM unavailable (%s) — pool fallback.", exc
        )
    return dict(random.choice(_FEEDBACK_POOL))


def score_session(
    history: list[dict],
    hidden_context: dict | None = None,
    outcome: str = "deal_closed",
    final_deal_value: float | None = None,
    user_brief: dict | None = None,
    llm=None,
) -> dict:
    """Compute an end-of-session performance score for the user.

    Blends outcome quality (50%) with move quality (50%).  All optional
    arguments degrade gracefully when omitted — the scorer falls back to
    move-quality-only scoring and heuristic best/worst move selection.

    Args:
        history: Complete ordered conversation.  User turns may carry an
            optional ``"critic_feedback"`` key used for move-quality scoring.
        hidden_context: Opponent's private data (reserved, currently unused).
        outcome: One of ``"deal_closed"``, ``"walked_away"``, ``"timeout"``.
        final_deal_value: Agreed value when the deal closed.
        user_brief: Dict with ``"target"`` (float) and ``"batna"`` (float).
        llm: ``LLMRouter`` instance for best/worst identification.

    Returns:
        ``{"score": int, "rating": str, "best_move": dict, "worst_move": dict}``

        ``rating`` is one of ``"Poor"`` (0–39) · ``"Fair"`` (40–59) ·
        ``"Good"`` (60–79) · ``"Excellent"`` (80–100).

    Raises:
        TypeError: If ``history`` is not a list.
        ValueError: If ``history`` is empty.
    """
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")
    if not history:
        raise ValueError("history must not be empty.")

    try:
        from parley_ai.scoring import score_session as _real_score
        return _real_score(
            history=history,
            hidden_context=hidden_context,
            outcome=outcome,
            final_deal_value=final_deal_value,
            user_brief=user_brief,
            llm=llm,
        )
    except Exception as exc:
        _log.error(
            "score_session: scoring pipeline failed (%s) — safe fallback.", exc
        )
    return dict(_SCORE_FALLBACK)
