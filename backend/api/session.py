"""
Session endpoints — create, run, and reveal negotiation sessions.

POST /session/start           Create a new session from a scenario.
POST /session/{id}/move       Submit one user move; receive opponent + critic.
GET  /session/{id}/reveal     Get hidden state + score after session ends.
GET  /session/scenarios       List available scenario summaries.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import orchestrator
from core.scenarios import list_scenarios_safe

router = APIRouter(prefix="/session", tags=["Session"])


# ── Request models ─────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1, description="e.g. 'salary_v1'")


class MoveRequest(BaseModel):
    user_message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's negotiation move in plain text.",
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/scenarios", summary="List all available scenarios")
async def list_scenarios():
    """Returns a user-safe list of all negotiation scenarios."""
    return list_scenarios_safe()


@router.post("/start", summary="Create a new negotiation session")
async def start_session(body: StartRequest):
    """
    Initialise a session from the given scenario_id.

    Returns session metadata and the opponent's opening statement.
    Hidden opponent state is never included.
    """
    try:
        return orchestrator.start_session(body.scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to start session: {exc}"
        ) from exc


@router.post("/{session_id}/move", summary="Submit a negotiation move")
async def submit_move(session_id: str, body: MoveRequest):
    """
    Process the user's move through the full 6-stage pipeline.

    Returns the opponent's response and real-time critic feedback.
    Raises 404 if session not found, 409 if session already complete,
    422 if message is empty.
    """
    try:
        return await orchestrator.process_move(session_id, body.user_message)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")
    except RuntimeError as exc:
        if "session_already_complete" in str(exc):
            raise HTTPException(status_code=409, detail="session_already_complete")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error processing move: {exc}"
        ) from exc


@router.get("/{session_id}/reveal", summary="Reveal hidden state after session ends")
async def reveal_session(session_id: str):
    """
    Returns the opponent's full hidden context and the user's performance score.

    Only available after the session has ended (is_complete = true).
    Raises 409 if called while the session is still active.
    """
    try:
        return orchestrator.reveal_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail="session_not_complete — call this endpoint after the negotiation ends.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error revealing session: {exc}"
        ) from exc
