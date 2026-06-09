"""
Scenario router — POST /api/scenario/start, GET /api/scenario/list

Pure transport layer: validates input → calls orchestrator → validates output.
No business logic lives here.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from core.orchestrator import start_session
from core.scenarios import list_scenarios_safe
from schemas.requests import StartScenarioRequest
from schemas.responses import (
    StartScenarioResponse,
    ScenarioListResponse,
    ScenarioItem,
    UserBriefSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["Scenario"])


@router.get(
    "/list",
    response_model=ScenarioListResponse,
    summary="List all available negotiation scenarios",
    responses={
        200: {"description": "Scenario library loaded successfully."},
        503: {"description": "Scenario files could not be loaded."},
    },
)
async def list_scenarios() -> ScenarioListResponse:
    """
    Returns all available scenario summaries.
    No hidden opponent data is included.
    """
    try:
        raw = list_scenarios_safe()
        items = [ScenarioItem(**s) for s in raw]
        return ScenarioListResponse(scenarios=items, count=len(items))
    except Exception as exc:
        logger.error("list_scenarios failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scenario library unavailable — check server logs.",
        )


@router.post(
    "/start",
    response_model=StartScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialise a new negotiation session",
    responses={
        201: {"description": "Session created. Opponent opening statement included."},
        400: {"description": "Invalid scenario_id format."},
        404: {"description": "Scenario not found in library."},
        500: {"description": "Internal error initialising session."},
        503: {"description": "LLM unavailable — could not generate opener."},
    },
)
async def start_scenario(body: StartScenarioRequest) -> StartScenarioResponse:
    """
    Creates a new negotiation session from a scenario template.

    The opponent generates an in-character opening statement via the LLM.
    All hidden state (opponent target, BATNA, persona) is stored server-side only.

    Returns the full session bootstrap payload the frontend stores in sessionStorage.
    """
    try:
        result = start_session(
            body.scenario_id,
            user_name=body.user_name,
            currency=body.currency,
        )

        return StartScenarioResponse(
            session_id=result["session_id"],
            user_role=result["user_role"],
            opponent_role=result["opponent_role"],
            user_brief=UserBriefSchema(
                target=result["user_brief"]["target"],
                batna=result["user_brief"]["batna"],
                context=result["user_brief"]["context"],
            ),
            opening_offer=result["opening_offer"],
            opponent_opener=result["opponent_opener"],
            max_turns=result["max_turns"],
            value_unit=result["value_unit"],
            scenario_display_name=result["scenario_display_name"],
        )

    except ValueError as exc:
        # Unknown scenario_id
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    except RuntimeError as exc:
        msg = str(exc)
        if "GEMINI_API_KEY" in msg or "GeminiClient" in msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM is not configured. Set GEMINI_API_KEY in .env and restart.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session initialisation failed: {msg}",
        )

    except Exception as exc:
        logger.exception("Unexpected error in start_scenario: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred.",
        )
