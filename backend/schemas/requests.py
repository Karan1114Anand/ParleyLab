"""
Request schemas for all ParleyLab API endpoints.

Every field is validated before it reaches any business logic.
Pydantic v2 is used throughout — FastAPI 0.111+ ships with it by default.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# ── POST /api/scenario/start ───────────────────────────────────────────────────

class StartScenarioRequest(BaseModel):
    """Initialise a new negotiation session from a scenario template."""
    scenario_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
        description="Scenario identifier, e.g. 'salary_v1'",
        examples=["salary_v1", "rent_v1", "freelance_v1", "equity_v1"],
    )


# ── POST /api/chat/message ─────────────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    """Send the user's negotiation move and receive the opponent's reply."""
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Session ID returned by /api/scenario/start",
        examples=["sess_a1b2c3d4"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's negotiation move in plain text.",
        examples=["I'm looking for $92,000 based on market data and my competing offer."],
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be blank or whitespace-only.")
        return v.strip()


# ── POST /api/chat/evaluate ────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    """Trigger the Critic Agent to evaluate a specific user message."""
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Session ID for the active negotiation.",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's message to evaluate (same text sent to /api/chat/message).",
    )
    turn_number: int = Field(
        ...,
        ge=1,
        description="The turn number this message belongs to (for context logging).",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be blank.")
        return v.strip()
