"""
Orchestrator — the central coordinator for every negotiation turn.

Six-stage pipeline (all server-side, one HTTP call per turn):
  1  User message arrives
  2  MoveParser  →  ParsedMove (LLM, low temp, JSON)
  3  State update →  new observation vector
  4  PPOPolicy    →  strategic action (RL, sub-ms)
  5a OpponentAgent → natural-language reply   ⎤  run in
  5b CriticAgent  → coaching feedback         ⎦  parallel
  6  Return user-safe payload to FastAPI route

init_singletons() must be called once at FastAPI lifespan startup.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np

from core.scenarios import get_scenario
from core.state import (
    Message,
    SessionState,
    UserBrief,
    create_session_id,
    get_session,
    save_session,
)
from parley_ai.agents.critic import CriticAgent
from parley_ai.agents.move_parser import MoveParser
from parley_ai.agents.opponent import HiddenContext, OpponentAgent
from parley_ai.llm.gemini import GeminiClient
from parley_ai.rl.policy import PPOPolicy

logger = logging.getLogger(__name__)

# ── Module-level singletons (loaded once at startup) ──────────────────────────

_policy: Optional[PPOPolicy] = None
_move_parser: Optional[MoveParser] = None
_opponent_agent: Optional[OpponentAgent] = None
_critic_agent: Optional[CriticAgent] = None
_llm_provider: str = "gemini"


def init_singletons() -> None:
    """Load the PPO model and instantiate LLM-backed agents. Called once at startup."""
    global _policy, _move_parser, _opponent_agent, _critic_agent, _llm_provider

    # ── RL Policy ─────────────────────────────────────────────────────────────
    model_path = os.getenv("RL_MODEL_PATH") or None  # PPOPolicy auto-detects if None
    _policy = PPOPolicy(model_path=model_path)

    # ── Shared LLM client ─────────────────────────────────────────────────────
    model_name = os.getenv("PARLEYLAB_MODEL", "gemini-2.0-flash")
    llm = GeminiClient(model_name=model_name)
    _llm_provider = "gemini"

    # ── Agents ────────────────────────────────────────────────────────────────
    _move_parser = MoveParser(llm=llm)
    _opponent_agent = OpponentAgent(llm=llm)
    _critic_agent = CriticAgent(llm=llm)

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

def start_session(scenario_id: str) -> Dict[str, Any]:
    """
    Create a new negotiation session.

    Returns the user-safe session start payload (no hidden state).
    Raises ValueError if scenario_id is unknown.
    """
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise ValueError(f"Unknown scenario: '{scenario_id}'")

    session_id = create_session_id()
    now = datetime.utcnow()
    hidden = scenario["opponent_hidden"]
    brief = scenario["user_brief"]

    state = SessionState(
        session_id=session_id,
        scenario_id=scenario_id,
        created_at=now,
        last_active_at=now,
        user_role=scenario["user_role"],
        opponent_role=scenario["opponent_role"],
        user_brief=UserBrief(
            target=float(brief["target"]),
            batna=float(brief["batna"]),
            context=brief["context"],
        ),
        opening_offer=float(scenario["opening_offer"]),
        max_turns=int(scenario["max_turns"]),
        value_unit=scenario["value_unit"],
        # Hidden
        opponent_target=float(hidden["target"]),
        opponent_batna=float(hidden["batna"]),
        opponent_persona=hidden["persona"],
        opponent_urgency=hidden["urgency"],
        opponent_current_offer=float(scenario["opening_offer"]),
    )

    # Generate an in-character opener from the opponent
    opener = _generate_opener(state, scenario)

    state.history.append(Message(role="opponent", content=opener, turn=0))
    state.opponent_offers.append(state.opening_offer)

    save_session(state)

    return {
        "session_id": state.session_id,
        "user_role": state.user_role,
        "opponent_role": state.opponent_role,
        "user_brief": state.user_brief.to_dict(),
        "opening_offer": state.opening_offer,
        "opponent_opener": opener,
        "max_turns": state.max_turns,
        "value_unit": state.value_unit,
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
    parsed = _move_parser.parse(user_message, state.to_llm_history())  # type: ignore[union-attr]

    # ── Add user message to history ───────────────────────────────────────────
    state.history.append(Message(role="user", content=user_message, turn=state.turn))
    if parsed.offered_value is not None:
        state.user_offers.append(parsed.offered_value)

    # ── Stage 3: Build observation ────────────────────────────────────────────
    obs = _build_observation(state)

    # ── Stage 4: RL action ────────────────────────────────────────────────────
    action = _policy.predict(obs) if _policy else 1  # type: ignore[union-attr]
    state.strategic_history.append(action)

    # ── Calculate new opponent offer ──────────────────────────────────────────
    new_offer = _apply_action(state, action)

    # ── Walk-away short-circuit ───────────────────────────────────────────────
    if action == 4:
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
            "turn_number": state.turn,
            "opponent_response": walk_msg,
            "opponent_current_offer": state.opponent_current_offer,
            "critic_feedback": None,
            "is_complete": True,
            "outcome": "walked_away",
        }

    # ── Deal acceptance check (before generating response) ───────────────────
    deal_closed = parsed.primary_move == "acceptance" or _offers_converged(
        state.user_offers[-1] if state.user_offers else None,
        new_offer,
    )

    # ── Stage 5a + 5b: Parallel LLM calls ────────────────────────────────────
    hidden_ctx = HiddenContext(
        target=state.opponent_target,
        batna=state.opponent_batna,
        persona=state.opponent_persona,
        urgency=state.opponent_urgency,
        opponent_role=state.opponent_role,
        user_role=state.user_role,
        opening_offer=state.opening_offer,
        value_unit=state.value_unit,
        current_offer=new_offer,
    )

    opponent_response, critic_feedback = await asyncio.gather(
        asyncio.to_thread(
            _opponent_agent.respond,  # type: ignore[union-attr]
            hidden_ctx,
            action,
            state.to_llm_history(),
            parsed,
            new_offer,
        ),
        asyncio.to_thread(
            _critic_agent.evaluate,   # type: ignore[union-attr]
            parsed,
            state.to_llm_history(),
            state.user_role,
        ),
    )

    # ── Update state ──────────────────────────────────────────────────────────
    state.opponent_current_offer = new_offer
    state.opponent_offers.append(new_offer)
    state.history.append(Message(role="opponent", content=opponent_response, turn=state.turn))

    fb_dict = critic_feedback.to_dict()
    state.critic_feedbacks.append(fb_dict)

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
        "turn_number": state.turn,
        "opponent_response": opponent_response,
        "opponent_current_offer": new_offer,
        "critic_feedback": fb_dict,
        "is_complete": state.is_complete,
        "outcome": state.outcome,
    }


async def evaluate_move(
    session_id: str,
    user_message: str,
    turn_number: int,
) -> Dict[str, Any]:
    """
    Run the CriticAgent independently for a specific user message.

    Designed to be called from POST /api/chat/evaluate after the opponent
    reply has already been delivered — so coaching feedback loads asynchronously.

    State is read-only: no session mutation happens here.

    Raises KeyError if session not found.
    Returns critic feedback dict with keys: strengths, weaknesses, suggestion, concept_tag.
    """
    state = get_session(session_id)
    if state is None:
        raise KeyError(session_id)

    # Build the conversation history as of this turn for context
    history = state.to_llm_history()

    # Re-parse the move to get structured primitives for the critic
    parsed = _move_parser.parse(user_message, history)  # type: ignore[union-attr]

    # Run critic in thread pool (it's synchronous)
    feedback = await asyncio.to_thread(
        _critic_agent.evaluate,  # type: ignore[union-attr]
        parsed,
        history,
        state.user_role,
    )

    logger.debug(
        "evaluate_move session=%s turn=%d concept=%s",
        session_id, turn_number, feedback.concept_tag,
    )
    return feedback.to_dict()


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


def _generate_opener(state: SessionState, scenario: Dict[str, Any]) -> str:
    """Ask the OpponentAgent to generate an in-character opening statement."""
    if _opponent_agent is None:
        return (
            f"I'd like to propose {state.opening_offer} {state.value_unit} "
            "as our starting point for this discussion."
        )
    ctx = HiddenContext(
        target=state.opponent_target,
        batna=state.opponent_batna,
        persona=state.opponent_persona,
        urgency=state.opponent_urgency,
        opponent_role=state.opponent_role,
        user_role=state.user_role,
        opening_offer=state.opening_offer,
        value_unit=state.value_unit,
        current_offer=state.opening_offer,
    )
    try:
        system = OpponentAgent.build_opener_system(ctx)
        # Re-use the shared LLM via the OpponentAgent's internal client
        return _opponent_agent._llm.chat(  # noqa: SLF001
            system=system,
            messages=[{"role": "user", "content": "Start the negotiation."}],
            temperature=0.8,
        )
    except Exception as exc:
        logger.warning("Opener generation failed: %s", exc)
        return (
            f"Thank you for meeting with me. I'd like to propose "
            f"{state.opening_offer} {state.value_unit} to get us started."
        )


def _build_observation(state: SessionState) -> np.ndarray:
    """Build the 7-dimensional normalised state vector for the PPO policy."""
    opp = state.opponent_current_offer
    usr = state.user_offers[-1] if state.user_offers else state.opening_offer

    scale = max(abs(state.opening_offer), 1.0)
    opp_norm = opp / 100.0
    usr_norm = usr / 100.0
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

    # Turns since last opponent concession
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
    """Translate RL action into a new numeric opponent offer."""
    current = state.opponent_current_offer
    user_offer = state.user_offers[-1] if state.user_offers else current
    gap = abs(current - user_offer)

    if action == 0:     # Hold Firm
        return round(current, 2)
    elif action == 1:   # Concede Small — 5%
        step = gap * 0.05
    elif action == 2:   # Concede Large — 15%
        step = gap * 0.15
    elif action == 3:   # Bluff — 5% away
        step = -(gap * 0.05)
    else:               # Walk Away — no change (handled separately)
        return round(current, 2)

    # Move toward (or away from) user offer
    if current > user_offer:
        return round(current - step, 2)
    else:
        return round(current + step, 2)


def _offers_converged(user_offer: Optional[float], opp_offer: float) -> bool:
    if user_offer is None:
        return False
    return abs(user_offer - opp_offer) < 0.01 * max(abs(opp_offer), 1.0)


def _compute_deal_value(
    user_offer: Optional[float], opp_offer: float
) -> float:
    """Mid-point if both sides have stated values."""
    if user_offer is None:
        return opp_offer
    return round((user_offer + opp_offer) / 2, 2)
