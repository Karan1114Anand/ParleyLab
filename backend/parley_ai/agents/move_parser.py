"""
MoveParser — converts free-form negotiation text into structured primitives.

Uses a constrained LLM call (low temperature, JSON mode) to extract:
  primary_move, offered_value, concession, signals, tone, anchors_used

On any failure it returns a safe default ParsedMove so the session continues.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from parley_ai.llm.base import LLMClient

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────────
_SYSTEM = """You are a precise negotiation-move parser. Extract structured data from the user's negotiation message.

Return ONLY valid JSON — no markdown, no explanation — matching this exact schema:
{
  "primary_move": "<one of: anchor | counteroffer | concession | rejection | acceptance | bluff | information_share | question>",
  "offered_value": <number | null>,
  "concession": <number | null — amount moved from their last offer, positive means moved toward opponent>,
  "signals": [<tactical signals, e.g. "competing_bid_disclosure", "time_pressure", "bundled_demand">],
  "tone": "<one of: collaborative | assertive | aggressive | defensive | neutral>",
  "anchors_used": [<anchors referenced, e.g. "market_rate", "competing_offer_at_85k">]
}

Rules:
- If a specific numeric offer is made, set offered_value.
- If the user explicitly accepts the opponent's offer, set primary_move = "acceptance".
- Keep signals and anchors_used as short snake_case labels.
- When uncertain, prefer "counteroffer" for primary_move and "neutral" for tone.
"""


@dataclass
class ParsedMove:
    primary_move: str = "counteroffer"
    offered_value: Optional[float] = None
    concession: Optional[float] = None
    signals: List[str] = field(default_factory=list)
    tone: str = "neutral"
    anchors_used: List[str] = field(default_factory=list)
    raw_message: str = ""

    @classmethod
    def default(cls, message: str) -> "ParsedMove":
        """Safe fallback when LLM parsing fails."""
        return cls(raw_message=message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_move": self.primary_move,
            "offered_value": self.offered_value,
            "concession": self.concession,
            "signals": self.signals,
            "tone": self.tone,
            "anchors_used": self.anchors_used,
        }


class MoveParser:
    """
    Parses a raw user message into a ParsedMove using an LLM.

    The last few turns of conversation history are passed as context so
    the parser can detect concessions relative to prior offers.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def parse(self, message: str, history: List[Dict[str, str]]) -> ParsedMove:
        """
        Parse ``message`` and return a ParsedMove.

        Never raises — on any error returns ParsedMove.default(message).
        """
        context = history[-6:] if len(history) > 6 else history  # last 3 exchanges
        messages = [
            *context,
            {
                "role": "user",
                "content": f"Parse this negotiation move and return JSON: {message}",
            },
        ]

        try:
            raw = self._llm.chat(
                system=_SYSTEM,
                messages=messages,
                response_format="json",
                temperature=0.1,  # near-deterministic for parsing
            )
            data = _safe_json(raw)
            return ParsedMove(
                primary_move=data.get("primary_move", "counteroffer"),
                offered_value=_to_float(data.get("offered_value")),
                concession=_to_float(data.get("concession")),
                signals=data.get("signals", []),
                tone=data.get("tone", "neutral"),
                anchors_used=data.get("anchors_used", []),
                raw_message=message,
            )
        except Exception as exc:
            logger.warning("MoveParser.parse failed: %s — using default.", exc)
            return ParsedMove.default(message)


# ── Utilities ──────────────────────────────────────────────────────────────────

def _safe_json(text: str) -> dict:
    """Parse JSON, stripping markdown fences if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(l for l in lines if not l.startswith("```")).strip()
    return json.loads(stripped)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
