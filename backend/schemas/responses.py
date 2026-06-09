"""
Response schemas for all ParleyLab API endpoints.

Field names and types are designed to EXACTLY match the TypeScript interfaces
in frontend/lib/api.ts so the Zustand store receives zero-surprise payloads.
"""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# ── Shared sub-schemas ─────────────────────────────────────────────────────────

class UserBriefSchema(BaseModel):
    """User's private briefing — shown on the Role Brief screen."""
    target: float = Field(..., description="User's target value (goal).")
    batna: float  = Field(..., description="User's Best Alternative To Negotiated Agreement.")
    context: str  = Field(..., description="Scenario context paragraph shown to the user.")

    model_config = {"json_schema_extra": {"examples": [
        {"target": 95000.0, "batna": 80000.0, "context": "You have a competing offer at $85K…"}
    ]}}


class CriticFeedbackSchema(BaseModel):
    """Structured coaching feedback from the Critic Agent."""
    strengths:    List[str] = Field(default_factory=list, description="1–2 concrete strengths.")
    weaknesses:   List[str] = Field(default_factory=list, description="1–2 areas to improve.")
    suggestion:   str       = Field("",  description="One actionable tip for the next move.")
    concept_tag:  str       = Field("anchoring", description="Primary negotiation concept illustrated.")

    model_config = {"json_schema_extra": {"examples": [
        {
            "strengths": ["Good use of competing offer as leverage."],
            "weaknesses": ["Conceded 8% in a single move — too fast."],
            "suggestion": "Anchor your next number to market data before conceding further.",
            "concept_tag": "anchoring",
        }
    ]}}


# ── POST /api/scenario/start → StartScenarioResponse ──────────────────────────

class StartScenarioResponse(BaseModel):
    """
    Full session initialisation payload.

    Stored in sessionStorage by the frontend and consumed by the
    negotiation page. All fields must match StartSessionResponse in lib/api.ts.
    """
    session_id:            str            = Field(..., description="Unique session ID (e.g. 'sess_a1b2c3d4').")
    user_role:             str            = Field(..., description="Role label for the user (e.g. 'Candidate').")
    opponent_role:         str            = Field(..., description="Role label for the AI opponent.")
    user_brief:            UserBriefSchema
    opening_offer:         float          = Field(..., description="Opponent's first numeric offer.")
    opponent_opener:       str            = Field(..., description="Opponent's in-character opening statement.")
    max_turns:             int            = Field(..., ge=1, description="Maximum number of negotiation turns.")
    value_unit:            str            = Field(..., description="Unit label (e.g. 'USD per year').")
    scenario_display_name: str            = Field(..., description="Human-readable scenario name.")


# ── POST /api/chat/message → ChatMessageResponse ───────────────────────────────

class ChatMessageResponse(BaseModel):
    """
    Result of one negotiation turn.

    critic_feedback is always None here — call /api/chat/evaluate to get it
    asynchronously so the opponent reply renders immediately.
    Matches MoveResponse in lib/api.ts.
    """
    turn_number:           int                                                       = Field(..., ge=1)
    opponent_response:     str                                                       = Field(...)
    opponent_current_offer:float                                                     = Field(...)
    critic_feedback:       Optional[CriticFeedbackSchema]                            = Field(None)
    is_complete:           bool                                                      = Field(...)
    outcome:               Optional[Literal["deal_closed", "walked_away", "timeout"]] = Field(None)


# ── POST /api/chat/evaluate → EvaluateResponse ────────────────────────────────

class EvaluateResponse(BaseModel):
    """Critic Agent feedback for a specific user message."""
    session_id:      str                 = Field(..., description="Echo of the evaluated session.")
    turn_number:     int                 = Field(..., ge=1)
    critic_feedback: CriticFeedbackSchema


# ── GET /api/scenario/list → ScenarioListResponse ─────────────────────────────

class ScenarioItem(BaseModel):
    id:           str
    display_name: str
    user_role:    str
    opponent_role:str
    icon:         str
    description:  str
    max_turns:    int
    value_unit:   str


class ScenarioListResponse(BaseModel):
    scenarios: List[ScenarioItem]
    count:     int


# ── Error responses ────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """Structured error detail item (matches FastAPI validation error shape)."""
    field:   Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    """
    Standard error envelope.

    All non-2xx responses use this shape so the frontend can pattern-match
    on `code` without parsing the detail string.
    """
    error:  str               = Field(..., description="Short machine-readable error code.")
    detail: str               = Field(..., description="Human-readable explanation.")
    errors: List[ErrorDetail] = Field(default_factory=list, description="Per-field validation errors.")

    model_config = {"json_schema_extra": {"examples": [
        {"error": "session_not_found",  "detail": "No session with id 'sess_abc123'.", "errors": []},
        {"error": "validation_error",   "detail": "Request payload is invalid.",       "errors": [
            {"field": "scenario_id", "message": "string does not match pattern '^[a-z0-9_]+$'"}
        ]},
        {"error": "ai_timeout",         "detail": "LLM did not respond within 30s.",  "errors": []},
        {"error": "session_complete",   "detail": "This session has already ended.",   "errors": []},
    ]}}
