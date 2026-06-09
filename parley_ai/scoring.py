"""End-of-session performance scoring for ParleyLab."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parley_ai.llm.router import LLMRouter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rating thresholds (spec-defined)
# ---------------------------------------------------------------------------

_THRESHOLDS = [(80, "Excellent"), (60, "Good"), (40, "Fair"), (0, "Poor")]

# ---------------------------------------------------------------------------
# LLM prompt for best/worst move identification
# ---------------------------------------------------------------------------

_BEST_WORST_SYSTEM = """\
You are a negotiation analyst. Given a negotiation transcript (and optional \
per-turn coaching feedback), identify the single BEST and single WORST user move.

Best move  = the turn where the user gained the most leverage, made the \
strongest tactical choice, or extracted the best concession.
Worst move = the turn where the user gave the most away, revealed too much, \
or weakened their position unnecessarily.

If there is only one user turn, both best and worst are that same turn.

Return ONLY a JSON object with exactly these keys:
{
  "best_move":  {"turn": <int, 1-indexed>, "summary": "<one-phrase label>", "reason": "<one sentence>"},
  "worst_move": {"turn": <int, 1-indexed>, "summary": "<one-phrase label>", "reason": "<one sentence>"}
}
"""

_SAFE_BEST  = {"turn": 1, "summary": "Opening move", "reason": "Insufficient data for detailed evaluation."}
_SAFE_WORST = {"turn": 1, "summary": "Opening move", "reason": "Insufficient data for detailed evaluation."}


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def score_session(
    history: list[dict],
    hidden_context: dict | None = None,
    outcome: str = "deal_closed",
    final_deal_value: float | None = None,
    user_brief: dict | None = None,
    llm: "LLMRouter | None" = None,
) -> dict:
    """Compute an end-of-session performance score for the user.

    The score is a weighted blend of outcome quality (50%) and move quality
    (50%). Both components degrade gracefully when optional data is absent.

    Args:
        history: Complete ordered conversation. Each element is a dict with
            ``"role"`` (``"user"`` or ``"opponent"``) and ``"content"``
            (str). User turns may optionally carry a ``"critic_feedback"``
            key (dict with ``"strengths"`` and ``"weaknesses"`` lists) —
            when present these are used for move-quality scoring.
        hidden_context: Opponent's private data (unused by scorer; reserved
            for future use).
        outcome: Session result — one of ``"deal_closed"``,
            ``"walked_away"``, ``"timeout"``.
        final_deal_value: The agreed-upon value if the deal closed.
        user_brief: User's private brief — expected keys ``"target"``
            (float) and ``"batna"`` (float).
        llm: An ``LLMRouter`` instance for best/worst identification. When
            ``None`` a default router is constructed from environment vars.

    Returns:
        A dict with:

        - ``score`` (int): Overall score in ``[0, 100]``.
        - ``rating`` (str): One of ``"Excellent"``, ``"Good"``,
          ``"Fair"``, ``"Poor"``.
        - ``best_move`` (dict): ``{turn, summary, reason}`` — the single
          most impactful positive user move.
        - ``worst_move`` (dict): ``{turn, summary, reason}`` — the single
          weakest user move.

    Raises:
        TypeError: If ``history`` is not a list.
        ValueError: If ``history`` is empty.
    """
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, got {type(history).__name__}.")
    if not history:
        raise ValueError("history must not be empty.")

    # ── Component scores ─────────────────────────────────────────────────────
    outcome_score = _outcome_score(outcome, final_deal_value, user_brief)
    move_score    = _move_quality_score(history)

    total = outcome_score + move_score
    score = max(0, min(100, total))
    rating = next(r for threshold, r in _THRESHOLDS if score >= threshold)

    # ── Best / worst move (LLM call) ──────────────────────────────────────────
    best_move, worst_move = _identify_best_worst(history, llm)

    return {
        "score":      score,
        "rating":     rating,
        "best_move":  best_move,
        "worst_move": worst_move,
    }


# ---------------------------------------------------------------------------
# Outcome quality  (0 – 50 points)
# ---------------------------------------------------------------------------

def _outcome_score(
    outcome: str,
    final_deal_value: float | None,
    user_brief: dict | None,
) -> int:
    if outcome == "deal_closed":
        if final_deal_value is not None and user_brief is not None:
            try:
                target = float(user_brief["target"])
                batna  = float(user_brief["batna"])
                deal   = float(final_deal_value)
                return _value_score(deal, target, batna)
            except (KeyError, TypeError, ValueError):
                pass
        return 35  # closed but no value context

    if outcome == "walked_away":
        # Walking away can be smart (beat BATNA) or weak — treat as neutral-low
        return 20

    if outcome == "timeout":
        return 10

    return 25  # unknown / fallback


def _value_score(deal: float, target: float, batna: float) -> int:
    """Score 0-50 based on how close the deal was to target vs BATNA."""
    if target == batna:
        return 30  # degenerate case

    # Higher target = seller side (want high); lower target = buyer side (want low)
    seller_side = target > batna

    if seller_side:
        if deal >= target:               return 50
        if deal >= (batna + target) / 2: return 40
        if deal > batna:                 return 28
        return 10                        # at or below BATNA
    else:
        if deal <= target:               return 50
        if deal <= (batna + target) / 2: return 40
        if deal < batna:                 return 28
        return 10


# ---------------------------------------------------------------------------
# Move quality  (0 – 50 points)
# ---------------------------------------------------------------------------

def _move_quality_score(history: list[dict]) -> int:
    """
    If user turns carry embedded critic_feedback, derive score from
    strength/weakness counts. Otherwise use a lightweight heuristic.
    """
    ratios: list[float] = []
    for msg in history:
        if msg.get("role") != "user":
            continue
        fb = msg.get("critic_feedback")
        if not isinstance(fb, dict):
            continue
        strengths  = len(fb.get("strengths",  []))
        weaknesses = len(fb.get("weaknesses", []))
        total = strengths + weaknesses
        if total > 0:
            ratios.append(strengths / total)

    if ratios:
        avg = sum(ratios) / len(ratios)
        return int(avg * 50)

    # ── Heuristic fallback ────────────────────────────────────────────────────
    user_msgs = [m for m in history if m.get("role") == "user"]
    if not user_msgs:
        return 25

    points = 25  # baseline

    for msg in user_msgs:
        text = msg.get("content", "").lower()
        # Good signals
        if any(w in text for w in ("competing", "other offer", "alternative")):
            points += 3    # leveraged external option
        if any(w in text for w in ("if you include", "along with", "as well")):
            points += 4    # bundled demand
        if any(w in text for w in ("market", "industry", "data", "research")):
            points += 2    # justified anchor
        # Weak signals
        if any(w in text for w in ("please", "really need", "desperate", "have to")):
            points -= 3    # showed desperation
        if any(w in text for w in ("final offer", "take it or leave")):
            points -= 2    # premature ultimatum reduces credibility

    return max(0, min(50, points))


# ---------------------------------------------------------------------------
# Best / worst move identification (LLM)
# ---------------------------------------------------------------------------

def _identify_best_worst(
    history: list[dict],
    llm: "LLMRouter | None",
) -> tuple[dict, dict]:
    """Return (best_move, worst_move) dicts via LLM, or safe defaults."""
    user_turns = [(i, m) for i, m in enumerate(history) if m.get("role") == "user"]

    if not user_turns:
        return _SAFE_BEST, _SAFE_WORST

    # If only one user turn, no distinction is possible
    if len(user_turns) == 1:
        idx, msg = user_turns[0]
        single = {
            "turn":    idx + 1,
            "summary": _truncate(msg.get("content", ""), 60),
            "reason":  "Only one user turn in this session.",
        }
        return single, single

    # ── Build transcript text ─────────────────────────────────────────────────
    transcript_lines: list[str] = []
    user_turn_counter = 0
    for i, msg in enumerate(history):
        role    = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "user":
            user_turn_counter += 1
            fb = msg.get("critic_feedback")
            line = f"[Turn {i + 1} — USER (move #{user_turn_counter})]: {content}"
            if isinstance(fb, dict):
                s = "; ".join(fb.get("strengths",  []))
                w = "; ".join(fb.get("weaknesses", []))
                if s: line += f"\n  Strengths: {s}"
                if w: line += f"\n  Weaknesses: {w}"
        else:
            line = f"[Turn {i + 1} — OPPONENT]: {content}"
        transcript_lines.append(line)

    transcript = "\n".join(transcript_lines)

    if llm is None:
        try:
            from parley_ai.llm.router import LLMRouter
            llm = LLMRouter()
        except Exception:
            return _fallback_best_worst(user_turns)

    try:
        raw = llm.chat(
            system=_BEST_WORST_SYSTEM,
            messages=[{
                "role":    "user",
                "content": f"Transcript:\n\n{transcript}\n\nIdentify best and worst user move.",
            }],
            json_mode=True,
            temperature=0.2,
        )
        data    = json.loads(raw)
        best    = _validated_move(data.get("best_move"),  user_turns)
        worst   = _validated_move(data.get("worst_move"), user_turns)
        return best, worst

    except Exception as exc:
        log.warning("Scorer: best/worst LLM call failed (%s) — using fallback.", exc)
        return _fallback_best_worst(user_turns)


def _validated_move(raw: object, user_turns: list) -> dict:
    """Validate an LLM-returned move dict; substitute safe defaults if invalid."""
    if not isinstance(raw, dict):
        return _fallback_best_worst(user_turns)[0]

    turn    = raw.get("turn")
    summary = raw.get("summary", "")
    reason  = raw.get("reason",  "")

    max_turn = max(i + 1 for i, _ in user_turns)
    if not isinstance(turn, int) or not (1 <= turn <= max_turn):
        turn = user_turns[0][0] + 1

    return {
        "turn":    turn,
        "summary": str(summary)[:120] or "User move",
        "reason":  str(reason)[:200]  or "No reason provided.",
    }


def _fallback_best_worst(user_turns: list) -> tuple[dict, dict]:
    """Simple heuristic fallback when the LLM is unavailable."""
    # Best = first turn with a tactical signal; worst = last turn
    best_idx, best_msg  = user_turns[0]
    worst_idx, worst_msg = user_turns[-1]

    for idx, msg in user_turns:
        text = msg.get("content", "").lower()
        if any(w in text for w in ("competing", "if you include", "market")):
            best_idx, best_msg = idx, msg
            break

    return (
        {
            "turn":    best_idx + 1,
            "summary": _truncate(best_msg.get("content", ""), 60),
            "reason":  "Tactical signal detected in this move.",
        },
        {
            "turn":    worst_idx + 1,
            "summary": _truncate(worst_msg.get("content", ""), 60),
            "reason":  "Final move — often the weakest concession point.",
        },
    )


def _truncate(text: str, n: int) -> str:
    return text[:n].rstrip() + ("…" if len(text) > n else "")
