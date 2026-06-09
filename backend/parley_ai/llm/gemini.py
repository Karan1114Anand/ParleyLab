"""
GeminiClient — robust Google Gemini LLM implementation for ParleyLab.

Uses the new `google-genai` SDK (google.genai ≥ 1.0, shipped as google-genai 2.x).

Features:
  - Auto-loads GEMINI_API_KEY from environment / .env
  - Exponential backoff retry (up to max_retries attempts)
  - JSON mode via response_mime_type
  - Strict message role normalisation to satisfy Gemini's alternation constraint
  - Detailed logging at every stage for hackathon-friendly debugging
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from parley_ai.llm.base import LLMClient

logger = logging.getLogger(__name__)


class GeminiClient(LLMClient):
    """
    Concrete LLMClient backed by the Google Gemini API (google-genai SDK ≥ 2.x).

    Environment variables
    ─────────────────────
    GEMINI_API_KEY   Required. Your Gemini API key.

    Parameters
    ──────────
    api_key      Override the env var at construction time (useful for tests).
    model_name   Gemini model to use. Default: gemini-2.0-flash.
    max_retries  Number of retry attempts before raising. Default: 3.
    retry_delay  Base delay in seconds for the exponential backoff. Default: 1.5.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash",
        max_retries: int = 3,
        retry_delay: float = 1.5,
    ) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file or pass api_key= explicitly."
            )
        self._client = genai.Client(api_key=key)
        self._model_name = model_name
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        logger.info("GeminiClient ready — model=%s", model_name)

    # ── Public API ─────────────────────────────────────────────────────────────

    def chat(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        response_format: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat request to Gemini and return the response text.

        Parameters
        ──────────
        system          System instruction string.
        messages        OpenAI-style list: [{"role": "user"|"assistant", "content": "..."}]
        response_format Pass "json" to enable structured JSON output mode.
        temperature     0.1 for deterministic (parsers/critics), 0.8 for creative (opponent).
        """
        config = self._build_config(system, temperature, response_format)
        contents = self._normalise_messages(messages)

        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.debug(
                    "Gemini request attempt %d/%d — %d messages, temp=%.2f",
                    attempt, self._max_retries, len(contents), temperature,
                )
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=contents,
                    config=config,
                )
                # Guard: response.text can be None when content is blocked
                text = response.text
                if text is None:
                    # Attempt to extract a finish reason for debugging
                    reason = getattr(
                        response.candidates[0] if response.candidates else None,
                        "finish_reason", "UNKNOWN"
                    ) if response else "NO_RESPONSE"
                    raise RuntimeError(
                        f"Gemini returned no text (finish_reason={reason}). "
                        "The content may have been blocked by safety filters."
                    )
                text = text.strip()
                logger.debug("Gemini response (%d chars): %s…", len(text), text[:120])
                return text
            except Exception as exc:
                last_exc = exc
                err_str = str(exc)
                # Detect quota/rate-limit errors — no point retrying immediately
                is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                is_auth  = "401" in err_str or "UNAUTHENTICATED" in err_str
                if is_quota:
                    logger.error(
                        "Gemini quota exceeded (attempt %d/%d): %s",
                        attempt, self._max_retries, err_str[:200],
                    )
                    raise RuntimeError(
                        "Gemini API quota exhausted. Please check your API key's "
                        "rate limits at https://ai.dev/rate-limit or use a paid key."
                    ) from exc
                if is_auth:
                    logger.error("Gemini authentication failed: %s", err_str[:200])
                    raise RuntimeError(
                        "Gemini API key is invalid or not an API key. "
                        "Keys must start with 'AIza'. Get one at https://aistudio.google.com/apikey"
                    ) from exc
                wait = self._retry_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Gemini attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt, self._max_retries, exc, wait,
                )
                if attempt < self._max_retries:
                    time.sleep(wait)

        raise RuntimeError(
            f"GeminiClient failed after {self._max_retries} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _build_config(
        system: str, temperature: float, response_format: Optional[str]
    ) -> types.GenerateContentConfig:
        """Build a GenerateContentConfig with system instruction and optional JSON mode."""
        kwargs: Dict[str, Any] = {
            "system_instruction": system,
            "temperature": temperature,
            "max_output_tokens": 2048,
        }
        if response_format == "json":
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _normalise_messages(
        messages: List[Dict[str, Any]],
    ) -> List[types.Content]:
        """
        Convert OpenAI-style messages to google.genai Content objects.

        Gemini requires:
          1. Messages alternate between "user" and "model" roles.
          2. The last message must be from "user".

        Consecutive same-role messages are merged.
        """
        result: List[types.Content] = []
        for msg in messages:
            raw_role = msg.get("role", "user")
            role = "user" if raw_role in ("user", "human") else "model"
            content = str(msg.get("content", ""))

            if result and result[-1].role == role:
                # Merge consecutive same-role messages
                existing_text = result[-1].parts[0].text  # type: ignore[union-attr]
                result[-1] = types.Content(
                    role=role,
                    parts=[types.Part(text=existing_text + "\n\n" + content)],
                )
            else:
                result.append(
                    types.Content(role=role, parts=[types.Part(text=content)])
                )

        # Gemini requires the last turn to be "user"
        if not result:
            result.append(
                types.Content(role="user", parts=[types.Part(text="Please respond.")])
            )
        elif result[-1].role == "model":
            result.append(
                types.Content(role="user", parts=[types.Part(text="Continue.")])
            )

        return result

    @staticmethod
    def extract_json(text: str) -> dict:
        """
        Best-effort JSON extraction from a response that may contain markdown fences.
        """
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            inner = "\n".join(line for line in lines if not line.startswith("```"))
            stripped = inner.strip()
        return json.loads(stripped)
