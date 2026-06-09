"""
Chat router — POST /api/chat/message, POST /api/chat/evaluate

Decoupled endpoints:
  /api/chat/message  → full negotiation turn (parse → RL → opponent response)
  /api/chat/evaluate → critic-only evaluation for the last user move

This split lets the UI render the opponent reply immediately, then
load critic feedback asynchronously — reducing perceived latency.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, status

from core.orchestrator import process_move, evaluate_move
from core.state import get_session
from schemas.requests import ChatMessageRequest, EvaluateRequest
from schemas.responses import (
    ChatMessageResponse,
    EvaluateResponse,
    CriticFeedbackSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# LLM hard timeout — guard against runaway API calls in a hackathon demo
_LLM_TIMEOUT_SECONDS = 45


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Submit a user negotiation move",
    responses={
        200: {"description": "Opponent response generated."},
        400: {"description": "Message is blank or malformed."},
        404: {"description": "Session not found."},
        409: {"description": "Session is already complete."},
        504: {"description": "LLM timed out."},
        500: {"description": "Internal pipeline error."},
    },
)
async def send_message(body: ChatMessageRequest) -> ChatMessageResponse:
    """
    Processes one user negotiation move through the full 6-stage pipeline:

      1. MoveParser  — extracts structured move primitives (LLM, low temp)
      2. State update — builds 7-dim observation vector
      3. PPOPolicy   — selects strategic action (0-4)
      4. OpponentAgent — generates in-character dialogue reply (LLM)
      5. State persist — saves updated session

    The Critic Agent is intentionally NOT called here.
    Call POST /api/chat/evaluate to get coaching feedback asynchronously.

    On session completion (deal_closed | walked_away | timeout), is_complete=True
    and outcome is set. Further calls will return 409.
    """
    try:
        result = await asyncio.wait_for(
            process_move(body.session_id, body.message),
            timeout=_LLM_TIMEOUT_SECONDS,
        )

        # Map critic_feedback dict (if any) to schema
        cf = None
        if result.get("critic_feedback"):
            raw_cf = result["critic_feedback"]
            cf = CriticFeedbackSchema(
                strengths=raw_cf.get("strengths", []),
                weaknesses=raw_cf.get("weaknesses", []),
                suggestion=raw_cf.get("suggestion", ""),
                concept_tag=raw_cf.get("concept_tag", "anchoring"),
            )

        return ChatMessageResponse(
            turn_number=result["turn_number"],
            opponent_response=result["opponent_response"],
            opponent_current_offer=result["opponent_current_offer"],
            critic_feedback=cf,
            is_complete=result["is_complete"],
            outcome=result.get("outcome"),
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{body.session_id}' not found.",
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "session_already_complete" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This session has already ended. Start a new session to continue.",
            )
        if "quota exhausted" in msg.lower() or "RESOURCE_EXHAUSTED" in msg:
            logger.error("Gemini quota exceeded: %s", msg[:200])
            raise HTTPException(
                status_code=429,
                detail="Gemini API quota exhausted. Please check your plan at https://ai.dev/rate-limit or use a paid API key.",
            )
        if "not an API key" in msg or "UNAUTHENTICATED" in msg or "AIza" in msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Gemini API key. Keys must start with 'AIza'. Get one at https://aistudio.google.com/apikey",
            )
        if "GeminiClient" in msg or "GEMINI_API_KEY" in msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM unavailable. Check GEMINI_API_KEY and retry.",
            )
        logger.error("process_move RuntimeError: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {msg}",
        )
    except asyncio.TimeoutError:
        logger.warning("LLM timed out for session %s", body.session_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"LLM did not respond within {_LLM_TIMEOUT_SECONDS}s. Please retry.",
        )
    except Exception as exc:
        logger.exception("Unexpected error in send_message: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected server error occurred: {type(exc).__name__}: {str(exc)[:200]}",
        )


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    summary="Evaluate a user move with the Critic Agent",
    responses={
        200: {"description": "Critic feedback returned."},
        400: {"description": "Message is blank or malformed."},
        404: {"description": "Session not found."},
        504: {"description": "Critic Agent timed out."},
        500: {"description": "Evaluation error."},
    },
)
async def evaluate_message(body: EvaluateRequest) -> EvaluateResponse:
    """
    Runs the Critic Agent independently against a specific user message.

    Designed to be called after POST /api/chat/message resolves, so the
    coaching card appears without blocking the opponent reply.

    The Critic sees ONLY the conversation history and the user's move —
    it never receives the opponent's hidden state (target, BATNA, persona).
    """
    try:
        feedback = await asyncio.wait_for(
            evaluate_move(body.session_id, body.message, body.turn_number),
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        return EvaluateResponse(
            session_id=body.session_id,
            turn_number=body.turn_number,
            critic_feedback=CriticFeedbackSchema(
                strengths=feedback.get("strengths", []),
                weaknesses=feedback.get("weaknesses", []),
                suggestion=feedback.get("suggestion", ""),
                concept_tag=feedback.get("concept_tag", "anchoring"),
            ),
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{body.session_id}' not found.",
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Critic Agent timed out after {_LLM_TIMEOUT_SECONDS}s.",
        )
    except Exception as exc:
        msg = str(exc)
        if "quota exhausted" in msg.lower() or "RESOURCE_EXHAUSTED" in msg:
            raise HTTPException(
                status_code=429,
                detail="Gemini API quota exhausted. Please check your plan at https://ai.dev/rate-limit.",
            )
        if "not an API key" in msg or "UNAUTHENTICATED" in msg or "AIza" in msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Gemini API key. Get a valid key at https://aistudio.google.com/apikey",
            )
        logger.exception("Unexpected error in evaluate_message: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {type(exc).__name__}: {msg[:200]}",
        )
