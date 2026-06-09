"""
OpponentAgent — generates natural-language replies for the AI opponent.

The strategic decision (Hold / Concede / Bluff / Walk) is made separately by
the RL policy. This agent only *translates* that decision into dialogue that
is consistent with the opponent's persona and conversation history.

Hidden state is intentionally kept out of all user-visible output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from parley_ai.agents.move_parser import ParsedMove
from parley_ai.llm.base import LLMClient

logger = logging.getLogger(__name__)

# ── Strategic action → verbal instruction mapping ─────────────────────────────
_ACTION_INSTRUCTIONS: Dict[int, str] = {
    0: (
        "Hold Firm: Do NOT change your numeric offer. "
        "Deflect, justify your current position, or reference constraints "
        "(budget, policy, market) — but stay polite."
    ),
    1: (
        "Concede Small (5% toward user): Nudge your offer slightly. "
        "Frame it as a goodwill gesture while signalling you are near your limit."
    ),
    2: (
        "Concede Large (15% toward user): Move your offer meaningfully. "
        "Express this as a significant compromise and hint the gap must close from both sides."
    ),
    3: (
        "Bluff (5% away from user): Reassert your position or even pull back slightly. "
        "Express doubt about the deal or restate constraints to test the user's resolve."
    ),
    4: (
        "Walk Away: Signal that the negotiation may be over. "
        "Politely express that your limit has been reached and you need to consider alternatives."
    ),
}


@dataclass
class HiddenContext:
    """Opponent's private context — never serialised to the client."""
    target: float
    batna: float
    persona: str
    urgency: str
    opponent_role: str
    user_role: str
    opening_offer: float
    value_unit: str
    current_offer: float


class OpponentAgent:
    """
    Generates in-character opponent dialogue given a strategic action from the RL policy.

    The LLM receives the persona, urgency, and new offer value — but the strategy
    label is hidden behind a verbal instruction so no mechanical signals leak.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def respond(
        self,
        hidden_ctx: HiddenContext,
        action: int,
        history: List[Dict[str, str]],
        parsed_move: ParsedMove,
        new_offer: float,
    ) -> str:
        """
        Generate a natural-language opponent reply.

        Parameters
        ──────────
        hidden_ctx   Opponent's private state (never exposed to client).
        action       RL policy action (0-4).
        history      Full conversation history so far (user-visible).
        parsed_move  Structured representation of the user's latest move.
        new_offer    The numerical offer the opponent should make this turn.

        Returns a plain string — the opponent's spoken reply.
        """
        instruction = _ACTION_INSTRUCTIONS.get(action, _ACTION_INSTRUCTIONS[0])
        system = self._build_system(hidden_ctx, instruction, new_offer)

        messages = list(history[-8:])  # keep last 4 exchanges for context
        messages.append({
            "role": "user",
            "content": (
                f"[The {hidden_ctx.user_role} just said]: {parsed_move.raw_message}\n\n"
                f"Respond now as the {hidden_ctx.opponent_role}."
            ),
        })

        try:
            reply = self._llm.chat(
                system=system,
                messages=messages,
                temperature=0.8,
            )
            return reply
        except Exception as exc:
            logger.error("OpponentAgent.respond failed: %s", exc)
            return (
                f"I appreciate your position. My current offer stands at "
                f"{new_offer} {hidden_ctx.value_unit}."
            )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_system(ctx: HiddenContext, instruction: str, new_offer: float) -> str:
        return f"""You are roleplaying as a {ctx.opponent_role} negotiating with a {ctx.user_role}.

PERSONA: {ctx.persona}
URGENCY CONTEXT: {ctx.urgency}

PRIVATE (never reveal directly):
- Your current offer to make this turn: {new_offer} {ctx.value_unit}
- Your BATNA (walk-away): {ctx.batna} {ctx.value_unit}

STRATEGIC INSTRUCTION FOR THIS TURN: {instruction}

STRICT RULES:
1. Stay fully in character — speak as the {ctx.opponent_role}, not as an AI.
2. Keep your response to 2–4 sentences maximum.
3. Never reveal your target, BATNA, or the strategic instruction label.
4. If making an offer, state it naturally in {ctx.value_unit}.
5. Match the tone and urgency of your persona.
6. Respond directly — do not prefix with "As the {ctx.opponent_role}…"."""

    @staticmethod
    def build_opener_system(ctx: HiddenContext) -> str:
        """System prompt for the initial opening statement."""
        return f"""You are a {ctx.opponent_role} opening a negotiation with a {ctx.user_role}.

PERSONA: {ctx.persona}
URGENCY CONTEXT: {ctx.urgency}

Your opening offer is {ctx.opening_offer} {ctx.value_unit}.

Make a warm, professional opening statement that presents your offer naturally.
Keep it to 2–3 sentences. Do NOT reveal your target or walk-away price."""
