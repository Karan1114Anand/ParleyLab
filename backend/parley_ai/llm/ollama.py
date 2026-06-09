"""
OllamaClient — Local Ollama LLM implementation for ParleyLab.

Falls back gracefully with a "service unavailable" error rather than crashing
so the GeminiClient remains the hot path.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from parley_ai.llm.base import LLMClient

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaClient(LLMClient):
    """
    Concrete LLMClient backed by a locally running Ollama instance.

    Environment variables
    ─────────────────────
    OLLAMA_BASE_URL   Ollama HTTP base URL. Default: http://localhost:11434

    Parameters
    ──────────
    model_name  Ollama model tag, e.g. "llama3.1:8b" or "qwen2.5:7b".
    timeout     HTTP request timeout in seconds. Default: 120.
    """

    def __init__(
        self,
        model_name: str = "llama3.1:8b",
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        self._model = model_name
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self._timeout = timeout
        logger.info("OllamaClient ready — model=%s url=%s", model_name, self._base_url)

    def chat(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        response_format: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if response_format == "json":
            payload["format"] = "json"

        try:
            resp = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"].strip()
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach Ollama at {self._base_url}. "
                "Is Ollama running? (ollama serve)"
            )
        except Exception as exc:
            logger.error("OllamaClient.chat failed: %s", exc)
            raise
