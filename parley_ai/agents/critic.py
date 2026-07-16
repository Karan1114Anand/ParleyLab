"""Critic agent — evaluates the user's negotiation move against theory."""

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

VALID_CONCEPT_TAGS = frozenset({
    "anchoring",
    "concession_pacing",
    "batna_signaling",
    "reciprocity",
    "information_disclosure",
    "framing",
    "walk_away_credibility",
})

_SAFE_DEFAULT: dict = {
    "strengths":   ["Move recorded."],
    "weaknesses":  ["Unable to evaluate this turn in detail."],
    "suggestion":  "Continue applying negotiation principles on the next turn.",
    "concept_tag": "anchoring",
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

NEGOTIATION_THEORY_RUBRIC = """\
BATNA AWARENESS
Know your walk-away point before you enter. Never volunteer it. A credible \
BATNA gives leverage; disclosing its weakness surrenders it.

ANCHORING
The first number stated anchors the final outcome. Anchor aggressively \
(buyer: low, seller: high) and justify immediately — a bare number anchors \
weakly; a number with a stated reason anchors strongly.

CONCESSION PACING
Concede slowly and in diminishing increments. Large early concessions signal \
desperation. Never concede without extracting something in return, however \
small — unconditional concessions teach the opponent to wait you out.

RECIPROCITY SIGNALING
When you move, signal that you expect a matching move. Explicit language — \
"I'm stretching here; I need you to meet me" — preserves leverage. Silent \
concessions invite exploitation.

INFORMATION DISCLOSURE DISCIPLINE
Reveal information only when it strengthens your position. Disclosing a \
deadline, BATNA value, or a specific competing offer too early hands power \
to the opponent. Disclose the existence of an alternative before its value.\
"""

SYSTEM_PROMPT = """\
You are a negotiation coach. Evaluate the user's latest move and return \
structured feedback. You cannot see the opponent's private goals or BATNA — \
judge only the user's observable behaviour.

THEORY (brief):
- Anchoring: first number biases outcome; justify it immediately
- Concession pacing: concede slowly in shrinking steps, never for free
- Reciprocity: signal you expect a matching move when you give ground
- Information disclosure: reveal an alternative exists before naming its value
- BATNA signaling: imply a strong walk-away without disclosing the exact number
- Framing: how you phrase a move shapes how it lands
- Walk-away credibility: only creates leverage if the opponent believes it

RULES:
1. Reference SPECIFIC words, numbers, or tactics the user actually used — \
no generic advice ("be more confident" is forbidden). Quote their exact \
phrasing when calling out a strength or weakness.
2. Suggestion must be one concrete action for the VERY NEXT turn.
3. Output ONLY a JSON object, nothing else.

JSON SCHEMA:
{
  "strengths":   [1-3 strings specific to this move],
  "weaknesses":  [1-3 strings specific to this move],
  "suggestion":  "one actionable next-turn tip",
  "concept_tag": "anchoring"|"concession_pacing"|"batna_signaling"|"reciprocity"|"information_disclosure"|"framing"|"walk_away_credibility"
}
"""

# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def get_critic_feedback(
    parsed_user_move: dict,
    history: list[dict],
    llm: "LLMRouter | None" = None,
) -> dict:
    """Evaluate the user's most recent negotiation move against theory.

    The critic has no access to the opponent's hidden state — it judges
    only observable user behaviour. On JSON parse failure it returns a
    safe default dict and logs a warning rather than crashing the pipeline.

    Args:
        parsed_user_move: Output of ``parse_move()`` for the current turn.
            Expected keys: ``"primary_move"``, ``"offered_value"``,
            ``"signals"``, ``"tone"``.
        history: Full ordered conversation list including the current user
            turn as the final entry. Each element has ``"role"``
            (``"user"`` or ``"opponent"``) and ``"content"`` (str).
        llm: An ``LLMRouter`` instance. When ``None`` a default router is
            constructed from environment variables.

    Returns:
        A dict with exactly these keys:

        - ``strengths`` (list[str]): 1–3 specific things the user did well.
        - ``weaknesses`` (list[str]): 1–3 specific things to improve.
        - ``suggestion`` (str): One actionable tip for the next turn.
        - ``concept_tag`` (str): Primary theory concept — one of
          ``"anchoring"``, ``"concession_pacing"``, ``"batna_signaling"``,
          ``"reciprocity"``, ``"information_disclosure"``, ``"framing"``,
          ``"walk_away_credibility"``.

    Raises:
        TypeError: If ``parsed_user_move`` is not a dict or ``history`` is
            not a list.
        ConnectionError: If the LLM provider is unreachable (propagated
            from ``LLMRouter``; caller should catch and fall back).
    """
    if not isinstance(parsed_user_move, dict):
        raise TypeError(
            f"parsed_user_move must be a dict, got {type(parsed_user_move).__name__}."
        )
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")

    if llm is None:
        from parley_ai.llm.router import LLMRouter
        llm = LLMRouter(agent_role="critic")

    # Pass ONLY the current user message to save LLM context window memory.
    # Extract only the user's last message to prevent the critic from evaluating the AI
    user_messages = [msg["content"] for msg in history if msg.get("role") == "user"]
    latest_user_message = user_messages[-1] if user_messages else "No user message found."

    ctx: list[dict] = [{
        "role": "user",
        "content": (
            f"User's raw message: \"{latest_user_message}\"\n\n"
            f"The move above has been parsed as: {json.dumps(parsed_user_move)}. "
            f"The specific statement you must evaluate from the candidate is: '{latest_user_message}'. "
            "Please evaluate it according to the rubric."
        ),
    }]

    _t0 = time.perf_counter()
    raw = llm.chat(
        system=SYSTEM_PROMPT,
        messages=ctx,
        json_mode=True,
        temperature=0.3,
    )
    log.info(
        "critic: provider=%s model=%s latency=%.2fs",
        getattr(llm, "provider", "unknown"),
        getattr(getattr(llm, "_client", None), "model", "unknown"),
        time.perf_counter() - _t0,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "Critic agent: JSON parse failed (%s). Raw: %.120r", exc, raw
        )
        return dict(_SAFE_DEFAULT)

    return _sanitize(parsed)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize(raw: dict) -> dict:
    """Validate LLM output and substitute safe defaults for invalid fields."""
    strengths = raw.get("strengths", [])
    if not isinstance(strengths, list) or not strengths:
        strengths = _SAFE_DEFAULT["strengths"]
    strengths = [s for s in strengths if isinstance(s, str) and s.strip()][:3]
    if not strengths:
        strengths = _SAFE_DEFAULT["strengths"]

    weaknesses = raw.get("weaknesses", [])
    if not isinstance(weaknesses, list) or not weaknesses:
        weaknesses = _SAFE_DEFAULT["weaknesses"]
    weaknesses = [w for w in weaknesses if isinstance(w, str) and w.strip()][:3]
    if not weaknesses:
        weaknesses = _SAFE_DEFAULT["weaknesses"]

    suggestion = raw.get("suggestion", "")
    if not isinstance(suggestion, str) or not suggestion.strip():
        suggestion = _SAFE_DEFAULT["suggestion"]

    concept_tag = raw.get("concept_tag", "anchoring")
    if concept_tag not in VALID_CONCEPT_TAGS:
        log.warning(
            "Critic agent: invalid concept_tag %r — defaulting to 'anchoring'",
            concept_tag,
        )
        concept_tag = "anchoring"

    return {
        "strengths":   strengths,
        "weaknesses":  weaknesses,
        "suggestion":  suggestion,
        "concept_tag": concept_tag,
    }
