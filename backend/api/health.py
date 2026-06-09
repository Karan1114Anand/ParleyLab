"""
Health endpoint — GET /healthz

Returns system status including whether the RL model loaded successfully
and which LLM provider is active. Safe to call before creating a session.
"""

from fastapi import APIRouter

from core.orchestrator import get_llm_provider, is_rl_loaded

router = APIRouter(tags=["Health"])


@router.get("/healthz", summary="Liveness check")
async def health_check() -> dict:
    """
    Returns 200 OK with system status.

    Response shape:
        {
          "status": "ok",
          "rl_model_loaded": true,
          "llm_provider": "gemini"
        }
    """
    return {
        "status": "ok",
        "rl_model_loaded": is_rl_loaded(),
        "llm_provider": get_llm_provider(),
    }
