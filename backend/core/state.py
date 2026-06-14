"""
SessionState — in-memory data model for a single negotiation session.

Separation contract:
  to_user_dict()    → only user-safe fields (sent to frontend on every turn)
  to_reveal_dict()  → includes hidden fields (only after session ends)

No database. Dict[session_id, SessionState] held as a module-level singleton.
For production, swap for Redis.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Sub-models ─────────────────────────────────────────────────────────────────

@dataclass
class UserBrief:
    target: float
    batna: float
    context: str

    def to_dict(self) -> Dict[str, Any]:
        return {"target": self.target, "batna": self.batna, "context": self.context}


@dataclass
class Message:
    role: str        # "user" | "opponent"
    content: str
    turn: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "turn": self.turn,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_llm_dict(self) -> Dict[str, str]:
        """For LLM history — maps 'opponent' → 'assistant'."""
        role = "user" if self.role == "user" else "assistant"
        return {"role": role, "content": self.content}


# ── Main state dataclass ───────────────────────────────────────────────────────

@dataclass
class SessionState:
    # Identifiers
    session_id: str
    scenario_id: str
    created_at: datetime
    last_active_at: datetime

    # User-visible
    user_role: str
    opponent_role: str
    user_brief: UserBrief
    opening_offer: float
    max_turns: int
    value_unit: str
    turn: int = 0
    is_complete: bool = False
    outcome: Optional[str] = None       # "deal_closed" | "walked_away" | "timeout"
    final_deal_value: Optional[float] = None

    # Conversation
    history: List[Message] = field(default_factory=list)
    user_offers: List[float] = field(default_factory=list)
    opponent_offers: List[float] = field(default_factory=list)

    # ── HIDDEN — never sent to client in normal responses ──────────────────────
    opponent_target: float = 0.0
    opponent_batna: float = 0.0
    opponent_persona: str = ""
    opponent_urgency: str = ""
    strategic_history: List[int] = field(default_factory=list)
    opponent_current_offer: float = 0.0

    # Performance accumulator
    critic_feedbacks: List[Dict[str, Any]] = field(default_factory=list)

    # User profile info
    user_name: str = ""
    difficulty: float = 0.5          # 0.0 = easy, 1.0 = hard; loaded from user profile

    # ── Helpers ────────────────────────────────────────────────────────────────

    def to_llm_history(self) -> List[Dict[str, str]]:
        """Flat role/content list for LLM context (maps opponent→assistant)."""
        return [m.to_llm_dict() for m in self.history]

    def to_user_dict(self) -> Dict[str, Any]:
        """User-safe snapshot — sent on every turn."""
        return {
            "session_id": self.session_id,
            "scenario_id": self.scenario_id,
            "user_role": self.user_role,
            "opponent_role": self.opponent_role,
            "user_brief": self.user_brief.to_dict(),
            "opening_offer": self.opening_offer,
            "max_turns": self.max_turns,
            "turn": self.turn,
            "is_complete": self.is_complete,
            "outcome": self.outcome,
            "value_unit": self.value_unit,
        }

    def to_reveal_dict(self) -> Dict[str, Any]:
        """Full reveal — only emitted after the session ends."""
        score, rating = self._calculate_score()
        best_move, worst_move = self._identify_key_moves()
        return {
            "outcome": self.outcome,
            "final_deal_value": self.final_deal_value,
            "opponent_hidden": {
                "target": self.opponent_target,
                "batna": self.opponent_batna,
                "persona": self.opponent_persona,
                "urgency": self.opponent_urgency,
            },
            "performance": {
                "score": score,
                "rating": rating,
                "best_move": best_move,
                "worst_move": worst_move,
            },
            "full_transcript": [m.to_dict() for m in self.history],
            "value_unit": self.value_unit,
        }

    def _calculate_score(self) -> tuple[int, str]:
        """Simple score: 100 = hit target, 0 = hit BATNA, adjusted by critique quality."""
        if self.outcome == "deal_closed" and self.final_deal_value is not None:
            t = self.user_brief.target
            b = self.user_brief.batna
            deal = self.final_deal_value
            span = abs(t - b)
            if span > 0:
                # User wants MORE (salary/equity) or LESS (rent)?
                if t > b:
                    raw = (deal - b) / span  # 0 = BATNA, 1 = target
                else:
                    raw = (b - deal) / span
                score = int(max(0.0, min(1.0, raw)) * 100)
            else:
                score = 50
        elif self.outcome == "walked_away":
            score = 30
        else:
            score = 15  # timeout

        # ±10 quality bonus from critic feedback ratio
        if self.critic_feedbacks:
            total_strengths = sum(len(f.get("strengths", [])) for f in self.critic_feedbacks)
            total_weaknesses = sum(len(f.get("weaknesses", [])) for f in self.critic_feedbacks)
            denom = total_strengths + total_weaknesses
            if denom:
                quality_bonus = int((total_strengths / denom) * 20) - 10
                score = max(0, min(100, score + quality_bonus))

        if score >= 85:
            rating = "Excellent"
        elif score >= 70:
            rating = "Good"
        elif score >= 50:
            rating = "Average"
        else:
            rating = "Needs Work"

        return score, rating

    def _identify_key_moves(self) -> tuple[Optional[dict], Optional[dict]]:
        best = None
        worst = None
        for i, fb in enumerate(self.critic_feedbacks):
            turn = i + 1
            if fb.get("strengths") and best is None:
                best = {"turn": turn, "summary": fb["strengths"][0]}
            if fb.get("weaknesses") and worst is None:
                worst = {"turn": turn, "summary": fb["weaknesses"][0]}
        return best, worst


# ── In-memory store ────────────────────────────────────────────────────────────

_SESSIONS: Dict[str, SessionState] = {}


def create_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:8]}"


def get_session(session_id: str) -> Optional[SessionState]:
    return _SESSIONS.get(session_id)


def save_session(state: SessionState) -> None:
    _SESSIONS[state.session_id] = state


def list_session_ids() -> List[str]:
    return list(_SESSIONS.keys())
