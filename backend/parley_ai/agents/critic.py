"""
CriticAgent — evaluates user negotiation moves against negotiation theory.

The critic sees ONLY the user's behaviour and conversation history.
It must NOT receive the opponent's hidden state (target, BATNA, persona)
so its feedback is unbiased and educational.

Output: CriticFeedback(strengths, weaknesses, suggestion, concept_tag)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from parley_ai.agents.move_parser import ParsedMove
from parley_ai.llm.base import LLMClient

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────────
_SYSTEM = """You are an expert negotiation coach. Evaluate the user's most recent move using negotiation theory.

Framework dimensions to consider:
- BATNA awareness: are they protecting their walk-away point?
- Anchoring: did they anchor first and effectively, or react poorly to the opponent's anchor?
- Concession pacing: are they giving ground too fast, too slow, or in smart increments?
- Reciprocity signaling: do they condition their concessions, making the opponent feel they must reciprocate?
- Information control: did they reveal too much, withhold strategically, or ask effective questions?

Return ONLY valid JSON — no markdown, no explanation — matching this exact schema:
{
  "strengths": [<1-2 specific, concrete strengths as short strings>],
  "weaknesses": [<1-2 specific, concrete weaknesses as short strings>],
  "suggestion": "<one actionable tip for the NEXT move — 1-2 sentences, direct and specific>",
  "concept_tag": "<exactly one of: anchoring | batna_awareness | concession_pacing | reciprocity | information_control | bundling | silence | deadline_pressure>"
}

Rules:
- Be honest and specific. Generic praise ("good job") is not useful.
- Focus on technique, not outcome. A tactically strong move can still 'fail' in conversation.
- The suggestion must be forward-looking — what should they do NEXT?
"""


@dataclass
class CriticFeedback:
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestion: str = ""
    concept_tag: str = "anchoring"

    @classmethod
    def default(cls) -> "CriticFeedback":
        return cls(
            strengths=["You engaged actively with the negotiation."],
            weaknesses=["Detailed feedback unavailable for this turn."],
            suggestion=(
                "State your position clearly and explain the value you're bringing "
                "before making any concession."
            ),
            concept_tag="anchoring",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestion": self.suggestion,
            "concept_tag": self.concept_tag,
        }


class CriticAgent:
    """
    Evaluates the user's negotiation move and returns structured coaching feedback.

    Intentionally decoupled from the opponent's hidden state.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def evaluate(
        self,
        parsed_move: ParsedMove,
        history: List[Dict[str, str]],
        user_role: str,
    ) -> CriticFeedback:
        """
        Evaluate the user's most recent move.

        Parameters
        ──────────
        parsed_move  Structured form of the user's move (from MoveParser).
        history      Conversation history WITHOUT opponent hidden state.
        user_role    E.g. "Candidate", "Freelancer".

        Returns CriticFeedback. Never raises — on error returns a safe default.
        """
        context_str = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in history[-8:]
        )
        signals_str = ", ".join(parsed_move.signals) if parsed_move.signals else "none"
        anchors_str = ", ".join(parsed_move.anchors_used) if parsed_move.anchors_used else "none"

        messages = [
            {
                "role": "user",
                "content": (
                    f"Evaluate this negotiation move by the {user_role}.\n\n"
                    f"CONVERSATION SO FAR:\n{context_str}\n\n"
                    f"LATEST MOVE: {parsed_move.raw_message}\n\n"
                    f"PARSED STRUCTURE:\n"
                    f"  Move type: {parsed_move.primary_move}\n"
                    f"  Value offered: {parsed_move.offered_value}\n"
                    f"  Concession made: {parsed_move.concession}\n"
                    f"  Tone: {parsed_move.tone}\n"
                    f"  Signals: {signals_str}\n"
                    f"  Anchors referenced: {anchors_str}\n\n"
                    "Provide your structured coaching critique as JSON."
                ),
            }
        ]

        try:
            raw = self._llm.chat(
                system=_SYSTEM,
                messages=messages,
                response_format="json",
                temperature=0.3,
            )
            data = _safe_json(raw)
            return CriticFeedback(
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                suggestion=data.get("suggestion", ""),
                concept_tag=data.get("concept_tag", "anchoring"),
            )
        except Exception as exc:
            logger.warning("CriticAgent.evaluate failed: %s — using default.", exc)
            return CriticFeedback.default()


def _safe_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(l for l in lines if not l.startswith("```")).strip()
    return json.loads(stripped)
