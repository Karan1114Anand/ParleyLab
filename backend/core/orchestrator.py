"""
Orchestrator — the central coordinator for every negotiation turn.

Six-stage pipeline (all server-side, one HTTP call per turn):
  1  User message arrives
  2  parse_move        →  parsed dict (LLM, low temp, JSON)
  3  State update      →  new observation vector
  4  StrategyPolicy    →  strategic action (RL, sub-ms)
  5a generate_opponent_response → natural-language reply   ⎤  run in
  5b get_critic_feedback        → coaching feedback        ⎦  parallel
  6  Return user-safe payload to FastAPI route

All AI/ML logic lives in the root parley_ai/ package.
init_singletons() must be called once at FastAPI lifespan startup.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np

# Approximate exchange rates (USD → target currency)
_EXCHANGE_RATES: Dict[str, float] = {
    "USD": 1, "GBP": 0.79, "INR": 83.5, "EUR": 0.92, "JPY": 155,
    "CNY": 7.25, "CAD": 1.36, "AUD": 1.55, "BRL": 5.0, "KRW": 1350,
    "MXN": 17.2, "SGD": 1.34, "AED": 3.67, "ZAR": 18.5, "NGN": 1550,
    "SEK": 10.8, "CHF": 0.88, "RUB": 92,
}

# Currency code → symbol for formatting value_unit labels
_CURRENCY_SYMBOLS: Dict[str, str] = {
    "USD": "$", "GBP": "£", "INR": "₹", "EUR": "€", "JPY": "¥",
    "CNY": "¥", "CAD": "C$", "AUD": "A$", "BRL": "R$", "KRW": "₩",
    "MXN": "MX$", "SGD": "S$", "AED": "د.إ", "ZAR": "R", "NGN": "₦",
    "SEK": "kr", "CHF": "CHF", "RUB": "₽",
}

from core.scenarios import get_scenario
from core.state import (
    Message,
    SessionState,
    UserBrief,
    create_session_id,
    get_session,
    save_session,
)

# ── Root parley_ai imports ─────────────────────────────────────────────────────
# sys.path is extended in main.py so these resolve to the project-root package.
from parley_ai.rl.policy import StrategyPolicy
from parley_ai.llm.router import LLMRouter
from parley_ai.agents.move_parser import parse_move as _parse_move_fn
from parley_ai.agents.opponent import generate_opponent_response as _gen_response_fn
from parley_ai.agents.critic import get_critic_feedback as _get_feedback_fn

logger = logging.getLogger(__name__)

# ── Module-level singletons (loaded once at startup) ──────────────────────────

_policy: Optional[StrategyPolicy] = None
_llm: Optional[LLMRouter] = None
_llm_provider: str = "gemini"


def init_singletons() -> None:
    """Load the PPO model and instantiate the LLM router. Called once at startup."""
    global _policy, _llm, _llm_provider

    # ── RL Policy ─────────────────────────────────────────────────────────────
    model_path = os.getenv("RL_MODEL_PATH") or None
    _policy = StrategyPolicy(model_path=model_path)

    if not _policy.is_loaded:
        logger.warning(
            "[WARNING] Running in DEGRADED MODE: PPO policy inactive, "
            "defaulting to deterministic heuristics. "
            "Place models/best_model.zip in the project root to activate full RL inference."
        )
    else:
        logger.info("StrategyPolicy: PPO model active — sub-ms CPU inference ready.")

    # ── LLM router ────────────────────────────────────────────────────────────
    model_name = os.getenv("PARLEYLAB_MODEL", "gemini-2.0-flash")
    provider = os.getenv("PARLEYLAB_LLM_PROVIDER", "gemini")
    _llm = LLMRouter(provider=provider, model=model_name)
    _llm_provider = provider

    logger.info(
        "Orchestrator ready — provider=%s model=%s rl_loaded=%s",
        _llm_provider,
        model_name,
        _policy.is_loaded,
    )


def get_llm_provider() -> str:
    return _llm_provider


def is_rl_loaded() -> bool:
    return _policy is not None and _policy.is_loaded


# ── Public API ────────────────────────────────────────────────────────────────

def _randomize_amount(base: float, pct: float = 0.15) -> float:
    """Return base ± pct (default ±15%), rounded to a nice number."""
    low = base * (1 - pct)
    high = base * (1 + pct)
    val = random.uniform(low, high)
    # Round to nearest 500 for large values, 5 for small
    if abs(val) >= 1000:
        return round(val / 500) * 500
    elif abs(val) >= 50:
        return round(val / 5) * 5
    else:
        return round(val, 1)


def _convert_amount(amount: float, currency: str) -> float:
    """Convert a USD-denominated amount to the target currency."""
    rate = _EXCHANGE_RATES.get(currency, 1.0)
    converted = amount * rate
    if abs(converted) >= 1000:
        return round(converted / 500) * 500
    elif abs(converted) >= 50:
        return round(converted / 5) * 5
    else:
        return round(converted, 1)


def _make_value_unit(original_unit: str, currency: str) -> str:
    """
    Replace the currency portion of a value_unit like 'USD per year'
    with the user's chosen currency code.
    """
    # For percentage-based scenarios (equity), don't change the unit
    if "%" in original_unit:
        return original_unit
    # Replace 'USD' with the target currency code
    return original_unit.replace("USD", currency)


def start_session(
    scenario_id: str,
    user_name: Optional[str] = None,
    currency: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new negotiation session.

    Returns the user-safe session start payload (no hidden state).
    Raises ValueError if scenario_id is unknown.
    """
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise ValueError(f"Unknown scenario: '{scenario_id}'")

    currency = (currency or "USD").upper()
    if currency not in _EXCHANGE_RATES:
        currency = "USD"

    session_id = create_session_id()
    now = datetime.utcnow()
    hidden = scenario["opponent_hidden"]
    brief = scenario["user_brief"]
    original_unit = scenario["value_unit"]
    is_percentage = "%" in original_unit

    # ── Randomize base amounts (in USD) then convert ─────────────────────────
    if is_percentage:
        # Equity: randomize within ±5 points
        user_target  = round(float(brief["target"]) + random.uniform(-5, 5))
        user_batna   = round(float(brief["batna"])  + random.uniform(-3, 3))
        opp_target   = round(float(hidden["target"]) + random.uniform(-3, 3))
        opp_batna    = round(float(hidden["batna"])  + random.uniform(-3, 3))
        opening      = round(float(scenario["opening_offer"]) + random.uniform(-5, 5))
        value_unit   = original_unit
    else:
        user_target  = _convert_amount(_randomize_amount(float(brief["target"])), currency)
        user_batna   = _convert_amount(_randomize_amount(float(brief["batna"])), currency)
        opp_target   = _convert_amount(_randomize_amount(float(hidden["target"])), currency)
        opp_batna    = _convert_amount(_randomize_amount(float(hidden["batna"])), currency)
        opening      = _convert_amount(_randomize_amount(float(scenario["opening_offer"])), currency)
        value_unit   = _make_value_unit(original_unit, currency)

    # Build context with the user's name if provided
    context = brief["context"]
    if user_name:
        context = f"Your name is {user_name}. " + context

    state = SessionState(
        session_id=session_id,
        scenario_id=scenario_id,
        created_at=now,
        last_active_at=now,
        user_role=scenario["user_role"],
        opponent_role=scenario["opponent_role"],
        user_brief=UserBrief(
            target=user_target,
            batna=user_batna,
            context=context,
        ),
        opening_offer=opening,
        max_turns=int(scenario["max_turns"]),
        value_unit=value_unit,
        opponent_target=opp_target,
        opponent_batna=opp_batna,
        opponent_persona=hidden["persona"],
        opponent_urgency=hidden["urgency"],
        opponent_current_offer=opening,
        user_name=user_name or "",
        difficulty=0.5,              # TODO: replace with profile lookup in Fix 2
    )

    opener = _generate_opener(state)
    state.history.append(Message(role="opponent", content=opener, turn=0))
    state.opponent_offers.append(state.opening_offer)

    save_session(state)

    return {
        "session_id":            state.session_id,
        "user_role":             state.user_role,
        "opponent_role":         state.opponent_role,
        "user_brief":            state.user_brief.to_dict(),
        "opening_offer":         state.opening_offer,
        "opponent_opener":       opener,
        "max_turns":             state.max_turns,
        "value_unit":            state.value_unit,
        "scenario_display_name": scenario.get("display_name", scenario_id),
    }


async def process_move(session_id: str, user_message: str) -> Dict[str, Any]:
    """
    Process one user move through the full 6-stage pipeline.

    Raises KeyError if session not found.
    Raises RuntimeError("session_already_complete") if session ended.
    """
    state = get_session(session_id)
    if state is None:
        raise KeyError(session_id)
    if state.is_complete:
        raise RuntimeError("session_already_complete")

    state.last_active_at = datetime.utcnow()
    state.turn += 1

    # ── Stage 2: Parse move ───────────────────────────────────────────────────
    parsed = _parse_move_fn(user_message, state.to_llm_history(), llm=_llm)
    # parsed = {primary_move, offered_value, signals, tone}

    # ── Add user message to history ───────────────────────────────────────────
    state.history.append(Message(role="user", content=user_message, turn=state.turn))
    if parsed.get("offered_value") is not None:
        state.user_offers.append(float(parsed["offered_value"]))

    # ── Stage 3: Build observation ────────────────────────────────────────────
    obs = _build_observation(state)

    # ── Stage 4: RL action ────────────────────────────────────────────────────
    if _policy:
        action_result = _policy.predict(obs.tolist())
    else:
        action_result = {"action_id": 1, "action_name": "Concede Small",
                         "description": "Opponent moves slightly toward your offer."}
    action_int = action_result["action_id"]
    state.strategic_history.append(action_int)

    new_offer = _apply_action(state, action_int)

    # ── Walk-away short-circuit ───────────────────────────────────────────────
    if action_int == 4:
        walk_msg = (
            "I appreciate the time we've spent on this, but I need to be honest — "
            "we're too far apart. I'll need to explore other options. "
            "If your position changes, please do reach out."
        )
        state.history.append(Message(role="opponent", content=walk_msg, turn=state.turn))
        state.is_complete = True
        state.outcome = "walked_away"
        save_session(state)
        return {
            "turn_number":            state.turn,
            "opponent_response":      walk_msg,
            "opponent_current_offer": state.opponent_current_offer,
            "critic_feedback":        None,
            "is_complete":            True,
            "outcome":                "walked_away",
        }

    # ── Deal acceptance check ─────────────────────────────────────────────────
    deal_closed = parsed.get("primary_move") == "accept" or _offers_converged(
        state.user_offers[-1] if state.user_offers else None,
        new_offer,
    )

    # ── Stage 5a + 5b: Parallel LLM calls ────────────────────────────────────
    hidden_ctx = {
        "target":        state.opponent_target,
        "batna":         state.opponent_batna,
        "persona":       state.opponent_persona,
        "urgency":       state.opponent_urgency,
        "current_offer": new_offer,
        "value_unit":    state.value_unit,
        "opponent_role": state.opponent_role,
        "user_role":     state.user_role,
        "user_name":     state.user_name,
    }

    opponent_response, critic_feedback = await asyncio.gather(
        asyncio.to_thread(
            _gen_response_fn,
            action_result,           # {action_id, action_name, description}
            hidden_ctx,
            state.to_llm_history(),  # includes current user turn
            parsed,
            _llm,
        ),
        asyncio.to_thread(
            _get_feedback_fn,
            parsed,
            state.to_llm_history(),
            _llm,
        ),
    )
    # Both functions return plain strings / dicts — no .to_dict() needed.

    # ── Update state ──────────────────────────────────────────────────────────
    state.opponent_current_offer = new_offer
    state.opponent_offers.append(new_offer)
    state.history.append(Message(role="opponent", content=opponent_response, turn=state.turn))
    state.critic_feedbacks.append(critic_feedback)

    if deal_closed:
        state.is_complete = True
        state.outcome = "deal_closed"
        state.final_deal_value = _compute_deal_value(
            state.user_offers[-1] if state.user_offers else None,
            new_offer,
        )
    elif state.turn >= state.max_turns:
        state.is_complete = True
        state.outcome = "timeout"

    save_session(state)

    return {
        "turn_number":            state.turn,
        "opponent_response":      opponent_response,
        "opponent_current_offer": new_offer,
        "critic_feedback":        critic_feedback,
        "is_complete":            state.is_complete,
        "outcome":                state.outcome,
    }


async def evaluate_move(
    session_id: str,
    user_message: str,
    turn_number: int,
) -> Dict[str, Any]:
    """
    Run the critic independently for a specific user message (read-only).

    Designed to be called from POST /api/chat/evaluate after the opponent
    reply has already been delivered — coaching feedback loads asynchronously.

    Raises KeyError if session not found.
    """
    state = get_session(session_id)
    if state is None:
        raise KeyError(session_id)

    history = state.to_llm_history()
    parsed  = _parse_move_fn(user_message, history, llm=_llm)

    feedback = await asyncio.to_thread(_get_feedback_fn, parsed, history, _llm)

    logger.debug(
        "evaluate_move session=%s turn=%d concept=%s",
        session_id, turn_number, feedback.get("concept_tag"),
    )
    return feedback


def reveal_session(session_id: str) -> Dict[str, Any]:
    """
    Return the full reveal payload after the session ends.

    Raises KeyError if not found, PermissionError if session still active.
    """
    state = get_session(session_id)
    if state is None:
        raise KeyError(session_id)
    if not state.is_complete:
        raise PermissionError("session_not_complete")
    return state.to_reveal_dict()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_opener(state: SessionState) -> str:
    """Ask the LLM to generate an in-character opening statement."""
    name_part = f" named {state.user_name}" if getattr(state, 'user_name', '') else ""
    greet_part = f"Address the {state.user_role}{' by their name (' + state.user_name + ')' if getattr(state, 'user_name', '') else ''} warmly. " if getattr(state, 'user_name', '') else ""

    if _llm is None:
        prefix = f"Hello{' ' + state.user_name if getattr(state, 'user_name', '') else ''}! "
        return (
            f"{prefix}I'd like to propose {state.opening_offer} {state.value_unit} "
            "as our starting point for this discussion."
        )
    system = (
        f"You are a {state.opponent_role} opening a negotiation with a {state.user_role}{name_part}.\n\n"
        f"PERSONA: {state.opponent_persona}\n"
        f"URGENCY CONTEXT: {state.opponent_urgency}\n\n"
        f"Your opening offer is {state.opening_offer} {state.value_unit}.\n\n"
        f"{greet_part}"
        "Make a warm, professional opening statement that presents your offer naturally. "
        "Keep it to 2–3 sentences. Do NOT reveal your target or walk-away price."
    )
    try:
        return _llm.chat(
            system=system,
            messages=[{"role": "user", "content": "Start the negotiation."}],
            temperature=0.8,
        )
    except Exception as exc:
        logger.warning("Opener generation failed: %s", exc)
        prefix = f"Hello{' ' + state.user_name if getattr(state, 'user_name', '') else ''}! "
        return (
            f"{prefix}Thank you for meeting with me. I'd like to propose "
            f"{state.opening_offer} {state.value_unit} to get us started."
        )


def _build_observation(state: SessionState) -> np.ndarray:
    """Build the 7-dimensional normalised state vector for the PPO policy."""
    opp = state.opponent_current_offer
    usr = state.user_offers[-1] if state.user_offers else state.opening_offer

    scale = max(abs(state.opening_offer), 1.0)
    opp_norm  = opp / 100.0
    usr_norm  = usr / 100.0
    turn_norm = state.turn / max(state.max_turns, 1)

    initial_gap = abs(state.opening_offer - state.user_brief.target)
    denom = max(initial_gap, 1.0)

    opp_concession = (
        abs(state.opponent_offers[-1] - state.opponent_offers[0]) / denom
        if len(state.opponent_offers) >= 2 else 0.0
    )
    usr_concession = (
        abs(state.user_offers[-1] - state.user_offers[0]) / denom
        if len(state.user_offers) >= 2 else 0.0
    )

    gap_norm = abs(opp - usr) / scale

    last_concession = 0
    for a in reversed(state.strategic_history):
        if a in (1, 2):
            break
        last_concession += 1
    since_norm = min(last_concession / max(state.max_turns, 1), 1.0)

    obs = np.array(
        [opp_norm, usr_norm, turn_norm, opp_concession, usr_concession, gap_norm, since_norm],
        dtype=np.float32,
    )
    return np.clip(obs, 0.0, 1.0)


def _apply_action(state: SessionState, action: int) -> float:
    """Translate RL action into a new numeric opponent offer.

    Step sizes scale with difficulty (0.0=easy, 1.0=hard):
      Concede Small: 12% of gap (easy) → 5% of gap (hard)
      Concede Large: 30% at easy, 15% at hard
    Hold Firm, Bluff, and Walk Away are unaffected by difficulty.
    """
    current    = state.opponent_current_offer
    user_offer = state.user_offers[-1] if state.user_offers else current
    gap        = abs(current - user_offer)
    d          = max(0.0, min(1.0, getattr(state, "difficulty", 0.5)))

    if action == 0:   # Hold Firm
        return round(current, 2)
    elif action == 1: # Concede Small — 12% at easy, 5% at hard
        step = gap * (0.12 - 0.07 * d)
    elif action == 2: # Concede Large — 30% at easy, 15% at hard
        step = gap * (0.30 - 0.15 * d)
    elif action == 3: # Bluff — unaffected by difficulty
        step = -(gap * 0.05)
    else:             # Walk Away
        return round(current, 2)

    if current > user_offer:
        return round(current - step, 2)
    else:
        return round(current + step, 2)


def _offers_converged(user_offer: Optional[float], opp_offer: float) -> bool:
    if user_offer is None:
        return False
    return abs(user_offer - opp_offer) < 0.01 * max(abs(opp_offer), 1.0)


def _compute_deal_value(user_offer: Optional[float], opp_offer: float) -> float:
    if user_offer is None:
        return opp_offer
    return round((user_offer + opp_offer) / 2, 2)
