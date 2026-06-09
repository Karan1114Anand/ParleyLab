"""Status endpoints — LLM provider health and usage statistics.

GET /api/status/llm  →  live Gemini + Ollama usage counters and event log
"""
from __future__ import annotations

from fastapi import APIRouter
from parley_ai.llm.tracker import get_tracker

router = APIRouter(prefix="/api/status", tags=["Status"])


@router.get(
    "/llm",
    summary="LLM provider usage statistics",
    responses={
        200: {"description": "Real-time usage stats for Gemini and Ollama."},
    },
)
async def llm_status() -> dict:
    """Returns live usage counters, rate-limit hits, fallback state, and the
    last 20 LLM events. Safe to poll at any frequency — it's a pure in-memory
    read with a threading.Lock guard."""
    return get_tracker().snapshot()
