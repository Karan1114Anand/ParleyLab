"""
parley_ai — AI/ML layer for the ParleyLab negotiation simulator.

Public interface (5 functions):
    parse_move                  User text → structured negotiation move
    get_strategic_action        7-dim state vector → RL policy action
    generate_opponent_response  RL action + context → natural-language reply
    get_critic_feedback         User move → structured critique
    score_session               Full history → end-of-session performance score

All functions are currently stubs returning realistic fake data.
Real implementations are progressively added in Tasks 2–9.
"""

from __future__ import annotations

import random
import re

# ---------------------------------------------------------------------------
# Internal constants
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
        "within current constraints. I'd like to find a way forward together, "
        "but the number itself needs to stay where it is."
    ),
    "Concede Small": (
        "You've made some good points. Let me see what I can do — I think I "
        "can stretch a bit to meet you closer to the middle."
    ),
    "Concede Large": (
        "You've raised compelling arguments and I want to get this done. I'm "
        "willing to move meaningfully on this to reach an agreement."
    ),
    "Bluff": (
        "I've had some internal conversations since we last spoke, and honestly "
        "my flexibility here is tighter than I'd hoped. The situation has shifted."
    ),
    "Walk Away": (
        "I've given this a great deal of thought. I don't believe we can reach "
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


# ---------------------------------------------------------------------------
# Lazy singleton — StrategyPolicy loaded on first call, cached for process
# ---------------------------------------------------------------------------

_policy = None  # parley_ai.rl.policy.StrategyPolicy


def _get_policy():
    global _policy
    if _policy is None:
        from parley_ai.rl.policy import StrategyPolicy
        _policy = StrategyPolicy()
    return _policy


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def parse_move(user_message: str, history: list[dict]) -> dict:
    """Convert a free-form user message into a structured negotiation move.

    Delegates to the LLM-powered agent in ``parley_ai.agents.move_parser``.
    If the LLM provider is unreachable, falls back to a heuristic keyword
    parser so the pipeline keeps running.

    Args:
        user_message: The user's raw negotiation text for the current turn.
        history: Ordered list of previous messages in the session. Each
            element is a dict with keys ``"role"`` (``"user"`` or
            ``"opponent"``) and ``"content"`` (str).

    Returns:
        A dict with the following keys:

        - ``primary_move`` (str): One of ``"opening_anchor"``,
          ``"counteroffer"``, ``"concession"``, ``"bluff"``,
          ``"walk_away"``, ``"accept"``, ``"signal"``.
        - ``offered_value`` (float | None): The numeric offer value, or
          ``None`` if none was stated.
        - ``signals`` (list[str]): Zero or more of
          ``"competing_bid_disclosure"``, ``"bundled_demand"``,
          ``"time_pressure"``, ``"reciprocity_request"``.
        - ``tone`` (str): One of ``"collaborative"``, ``"firm"``,
          ``"aggressive"``, ``"desperate"``.

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
    except ConnectionError:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Ollama not reachable — falling back to heuristic move parser."
        )

    # Heuristic fallback — runs when LLM is unavailable
    msg = user_message.lower()

    raw_numbers = re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", user_message)
    offered_value: float | None = (
        float(raw_numbers[0].replace(",", "")) if raw_numbers else None
    )

    signals: list[str] = []
    if any(w in msg for w in ("competing", "other offer", "alternative bid")):
        signals.append("competing_bid_disclosure")
    if any(w in msg for w in ("relocation", "bonus", "equity", "stock", "vacation")):
        signals.append("bundled_demand")
    if any(w in msg for w in ("deadline", "friday", "by end of week", "today", "urgent")):
        signals.append("time_pressure")

    if any(w in msg for w in ("appreciate", "grateful", "would love", "please", "happy to")):
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

    return {
        "primary_move":  primary_move,
        "offered_value": offered_value,
        "signals":       signals,
        "tone":          tone,
    }


def get_strategic_action(state_vector: list[float]) -> dict:
    """Determine the opponent's strategic action from the current game state.

    Consults the trained PPO policy (or, in stub mode, a weighted random
    draw) to decide whether the opponent should hold, concede, bluff, or
    walk away.

    Args:
        state_vector: A 7-element list of floats, each normalized to
            ``[0.0, 1.0]``, in this order:

            0. ``own_offer_norm``
            1. ``opponent_offer_norm``
            2. ``turn_norm``
            3. ``own_concession_rate``
            4. ``opponent_concession_rate``
            5. ``gap_norm``
            6. ``turns_since_last_concession_norm``

    Returns:
        A dict with:

        - ``action_id`` (int): Integer in ``{0, 1, 2, 3, 4}``.
        - ``action_name`` (str): Human-readable label.
        - ``description`` (str): What the action means in game terms.

        Action mapping::

            0  Hold Firm       Maintain position; signal confidence.
            1  Concede Small   Move 5% toward the opponent.
            2  Concede Large   Move 15% toward the opponent.
            3  Bluff           Move 5% away from opponent.
            4  Walk Away       End negotiation; take BATNA.

    Raises:
        TypeError: If ``state_vector`` is not a list.
        ValueError: If ``state_vector`` does not have exactly 7 elements,
            or if any element is outside ``[0.0, 1.0]``.

    Note:
        Delegates to ``StrategyPolicy`` in ``parley_ai.rl.policy``. The
        model is loaded lazily on first call and cached for the process
        lifetime — import time is not affected.
    """
    return _get_policy().predict(state_vector)


def generate_opponent_response(
    action: dict,
    hidden_context: dict,
    history: list[dict],
    parsed_user_move: dict,
    llm=None,
) -> str:
    """Translate a strategic action into a natural-language opponent reply.

    The response reflects the opponent's persona and conversation history
    while expressing the strategic intent chosen by the RL policy.

    Args:
        action: The output of :func:`get_strategic_action` — a dict that
            must contain at least the key ``"action_name"`` (str).
        hidden_context: The opponent's private scenario data. Expected keys:

            - ``"target"`` (float): Opponent's ideal outcome value.
            - ``"batna"`` (float): Opponent's walk-away threshold.
            - ``"persona"`` (str): Short persona description, e.g.
              ``"Polite but budget-constrained"``.
            - ``"urgency"`` (str): Urgency cue, e.g. ``"Moderate"``.

        history: Ordered list of all messages in the session, including the
            current user turn as the final entry (same schema as
            :func:`parse_move`).
        parsed_user_move: The output of :func:`parse_move` for the current
            turn.
        llm: An ``LLMRouter`` instance. When ``None`` a default router is
            constructed from environment variables.

    Returns:
        A single string containing the opponent's natural-language reply,
        safe to send directly to the frontend chat UI.

    Raises:
        TypeError: If ``action`` or ``hidden_context`` is not a dict.
        KeyError: If ``action`` does not contain the key ``"action_name"``.
    """
    if not isinstance(action, dict):
        raise TypeError(f"action must be a dict, got {type(action).__name__}.")
    if not isinstance(hidden_context, dict):
        raise TypeError(
            f"hidden_context must be a dict, got {type(hidden_context).__name__}."
        )
    if "action_name" not in action:
        raise KeyError("action must contain the key 'action_name'.")

    try:
        from parley_ai.agents.opponent import generate_opponent_response as _agent_reply
        return _agent_reply(action, hidden_context, history, parsed_user_move, llm=llm)
    except ConnectionError:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Ollama not reachable — falling back to opponent template."
        )

    return _OPPONENT_TEMPLATES.get(action["action_name"], _OPPONENT_TEMPLATES["Hold Firm"])


def get_critic_feedback(
    parsed_user_move: dict,
    history: list[dict],
) -> dict:
    """Evaluate the user's most recent move against negotiation theory.

    The critic is independent of the opponent: it judges the quality of the
    user's tactic regardless of how the opponent happened to respond.

    Args:
        parsed_user_move: The output of :func:`parse_move` for the current
            turn — a dict with keys ``"primary_move"``, ``"offered_value"``,
            ``"signals"``, and ``"tone"``.
        history: Ordered list of all prior messages in the session.

    Returns:
        A dict with:

        - ``strengths`` (list[str]): What the user did well.
        - ``weaknesses`` (list[str]): What could be improved.
        - ``suggestion`` (str): One concrete, actionable improvement.
        - ``concept_tag`` (str): The negotiation concept this feedback maps
          to — one of ``"anchoring"``, ``"reciprocity"``,
          ``"concession_pacing"``, ``"batna_awareness"``.

    Raises:
        TypeError: If ``parsed_user_move`` is not a dict or ``history`` is
            not a list.

    Note:
        Stub — draws from a small pool of pre-written items. Task 6
        replaces this with a real LLM call that reads the actual move and
        history.
    """
    if not isinstance(parsed_user_move, dict):
        raise TypeError(
            f"parsed_user_move must be a dict, got {type(parsed_user_move).__name__}."
        )
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")

    return dict(random.choice(_FEEDBACK_POOL))


def score_session(history: list[dict]) -> dict:
    """Compute an end-of-session performance score for the user.

    Analyses the full negotiation transcript and returns a numeric score,
    a qualitative rating, and the single best and worst user move.

    Args:
        history: Complete ordered list of all messages in the session. Each
            element is a dict with:

            - ``"role"`` (str): ``"user"`` or ``"opponent"``.
            - ``"content"`` (str): The raw message text.

    Returns:
        A dict with:

        - ``score`` (int): Overall score in ``[0, 100]``.
        - ``rating`` (str): One of ``"Excellent"``, ``"Good"``,
          ``"Fair"``, or ``"Needs Work"``.
        - ``best_move`` (dict): Keys ``"turn"`` (int, 1-indexed) and
          ``"summary"`` (str describing what was done well).
        - ``worst_move`` (dict): Keys ``"turn"`` (int, 1-indexed) and
          ``"summary"`` (str describing what could be improved).

    Raises:
        TypeError: If ``history`` is not a list.
        ValueError: If ``history`` is empty.

    Note:
        Stub — derives a plausible score from session length with jitter.
        Task 7 replaces this with a real scoring algorithm that analyses
        concession rates, BATNA usage, and anchoring quality.
    """
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")
    if not history:
        raise ValueError("history must not be empty.")

    user_turn_indices = [i for i, m in enumerate(history) if m.get("role") == "user"]
    n = len(user_turn_indices)

    raw = 45 + n * 6 + random.randint(-8, 18)
    score = max(0, min(100, raw))

    rating: str
    if score >= 80:
        rating = "Excellent"
    elif score >= 65:
        rating = "Good"
    elif score >= 50:
        rating = "Fair"
    else:
        rating = "Needs Work"

    if n >= 2:
        best_idx  = random.choice(user_turn_indices) + 1
        remaining = [t + 1 for t in user_turn_indices if t + 1 != best_idx]
        worst_idx = random.choice(remaining) if remaining else best_idx
    else:
        best_idx = worst_idx = (user_turn_indices[0] + 1 if user_turn_indices else 1)

    return {
        "score":  score,
        "rating": rating,
        "best_move": {
            "turn":    best_idx,
            "summary": "Anchored above target before conceding",
        },
        "worst_move": {
            "turn":    worst_idx,
            "summary": "Disclosed competing-bid value before extracting a concession",
        },
    }
