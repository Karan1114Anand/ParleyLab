"""
ParleyLab — FastAPI Application Entry Point

Run (from backend/ directory):
    uvicorn main:app --reload --port 8000

Prerequisites:
    - .env at project root containing GEMINI_API_KEY
    - models/best_model.zip present (PPO weights)
    - pip install -r requirements.txt
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# ── Ensure the project root is on sys.path so `import parley_ai` resolves ─────
# backend/ is the working directory when uvicorn runs, so the root parley_ai/
# package would otherwise be invisible. This must happen before any parley_ai
# imports elsewhere in the process.
import sys
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.join(_here, "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Load .env from project root (one level above backend/) ────────────────────
load_dotenv(dotenv_path=os.path.join(_here, "..", ".env"))

# ── FastAPI + middleware imports (after env is loaded) ────────────────────────
import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Routers
from api.health import router as health_router
from api.session import router as session_router      # legacy /session/* routes kept for backward compat
from api.scenario import router as scenario_router    # new /api/scenario/*
from api.chat import router as chat_router            # new /api/chat/*
from api.status import router as status_router        # new /api/status/*

from core.orchestrator import init_singletons, get_llm_provider
from schemas.responses import ErrorResponse, ErrorDetail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan — warm up all singletons once ────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("═══════════════════════════════════════════════")
    logger.info("           ParleyLab Backend Starting          ")
    logger.info("═══════════════════════════════════════════════")
    try:
        init_singletons()
        logger.info(
            "Orchestrator ready — provider=%s", get_llm_provider()
        )
    except Exception as exc:
        logger.error("Startup failed: %s", exc)
        logger.warning(
            "Server started in degraded mode — LLM features may not work. "
            "Check GEMINI_API_KEY in .env."
        )
    yield
    logger.info("ParleyLab backend shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ParleyLab API",
    description=(
        "AI Negotiation Coach powered by Reinforcement Learning + Gemini LLM.\n\n"
        "**New endpoints (v2):**\n"
        "- `POST /api/scenario/start` — initialise a session\n"
        "- `POST /api/chat/message`   — submit negotiation move\n"
        "- `POST /api/chat/evaluate`  — get critic coaching asynchronously\n\n"
        "**Legacy endpoints (v1, kept for backward compat):**\n"
        "- `POST /session/start`\n"
        "- `POST /session/{id}/move`\n"
        "- `GET  /session/{id}/reveal`"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health",   "description": "Server liveness and readiness checks."},
        {"name": "Scenario", "description": "Scenario library and session initialisation."},
        {"name": "Chat",     "description": "Negotiation turn processing and coaching."},
        {"name": "Session",  "description": "Legacy v1 session endpoints."},
    ],
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow-listed origins ensure the Next.js dev server (port 3000/3001) and any
# production origin can make cross-origin requests without preflight failures.

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:3003",
    "http://127.0.0.1:3003",
    # Add your production domain here, e.g.:
    # "https://parleylab.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,  # Cache preflight for 10 min
)


# ── Global exception handlers ─────────────────────────────────────────────────

def _error_json(error: str, detail: str, errors: list[dict] = None, status_code: int = 500) -> JSONResponse:
    body = ErrorResponse(
        error=error,
        detail=detail,
        errors=[ErrorDetail(**e) for e in (errors or [])],
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    422 Unprocessable Entity — Pydantic validation failed.

    Maps each error to a {field, message} pair so the frontend can
    highlight individual form fields.
    """
    errors = []
    for err in exc.errors():
        loc = " → ".join(str(p) for p in err.get("loc", []) if p != "body")
        errors.append({"field": loc or None, "message": err["msg"]})

    logger.warning(
        "Validation error on %s %s: %s",
        request.method, request.url.path, errors,
    )
    return _error_json(
        error="validation_error",
        detail="Request payload failed validation. See `errors` for field details.",
        errors=errors,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Map all HTTPExceptions to the standard ErrorResponse envelope.

    Specific error codes are mapped from common HTTP status codes.
    """
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "unprocessable",
        500: "internal_error",
        503: "service_unavailable",
        504: "gateway_timeout",
    }
    error_code = code_map.get(exc.status_code, f"http_{exc.status_code}")
    return _error_json(
        error=error_code,
        detail=str(exc.detail),
        status_code=exc.status_code,
    )


@app.exception_handler(asyncio.TimeoutError)
async def timeout_exception_handler(request: Request, exc: asyncio.TimeoutError) -> JSONResponse:
    """Catch any asyncio.TimeoutError not already wrapped by a route handler."""
    logger.error("Unhandled TimeoutError on %s", request.url.path)
    return _error_json(
        error="gateway_timeout",
        detail="The AI backend did not respond in time. Please retry.",
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """400 for business-logic validation failures (unknown scenario, etc.)."""
    return _error_json(
        error="bad_request",
        detail=str(exc),
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
    """403 for accessing results on an incomplete session."""
    return _error_json(
        error="forbidden",
        detail=str(exc),
        status_code=status.HTTP_403_FORBIDDEN,
    )


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    """404 for missing session IDs not caught at the route level."""
    return _error_json(
        error="not_found",
        detail=f"Resource '{exc.args[0]}' not found.",
        status_code=status.HTTP_404_NOT_FOUND,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for any unhandled exception — always returns 500."""
    logger.exception(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
    )
    return _error_json(
        error="internal_error",
        detail="An unexpected server error occurred. Please check server logs.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ── Routers ───────────────────────────────────────────────────────────────────

# v2 routes (new canonical paths)
app.include_router(scenario_router)   # /api/scenario/*
app.include_router(chat_router)       # /api/chat/*
app.include_router(status_router)     # /api/status/*

# v1 routes (backward compat — legacy session endpoints)
app.include_router(session_router)    # /session/*
app.include_router(health_router)     # /healthz


# ── Root redirect ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "ParleyLab API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/healthz",
        "endpoints": {
            "scenario_list":  "GET  /api/scenario/list",
            "scenario_start": "POST /api/scenario/start",
            "chat_message":   "POST /api/chat/message",
            "chat_evaluate":  "POST /api/chat/evaluate",
        },
    }
