"""Gemini LLM client — future fallback for ParleyLab.

This provider is implemented but NOT used in the demo. Ollama is the
primary (and only active) provider. Switch by setting
``PARLEYLAB_LLM_PROVIDER=gemini`` and providing ``GEMINI_API_KEY``.
"""

from __future__ import annotations

import logging
import os

import requests
from dotenv import load_dotenv

from parley_ai.llm.base import LLMClient

load_dotenv()

log = logging.getLogger(__name__)

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_DEFAULT_MODEL = "gemini-2.0-flash"
_VALID_ROLES = {"user", "assistant"}
_ROLE_MAP = {"user": "user", "assistant": "model"}
_JSON_INSTRUCTION = "Reply ONLY with valid JSON, no preamble or explanation."


class GeminiClient(LLMClient):
    """Sends chat requests to Google's Gemini API.

    Reads ``GEMINI_API_KEY`` from the environment. Not used in the demo —
    Ollama is the primary provider. This implementation is ready to activate
    without code changes: set ``PARLEYLAB_LLM_PROVIDER=gemini`` in your
    ``.env`` file.

    Example::

        client = GeminiClient()
        reply = client.chat(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Say hello."}],
        )

    Args:
        model: Gemini model name. Defaults to ``"gemini-2.0-flash"``.
        api_key: Gemini API key. Defaults to the ``GEMINI_API_KEY``
            environment variable.
        timeout: Per-request timeout in seconds. Defaults to ``30``.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.model = model or _DEFAULT_MODEL
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        # Key validation is deferred to chat() so that construction never raises —
        # this lets the fallback chain in __init__.py catch ConnectionError cleanly.
        self.timeout = timeout
        self._session = requests.Session()

    def chat(
        self,
        system: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat request to Gemini and return the reply text.

        Args:
            system: System prompt. Sent as a ``system_instruction`` block.
                When ``json_mode`` is ``True``, a JSON-only instruction is
                appended to this prompt.
            messages: Conversation history — list of dicts with keys
                ``"role"`` (``"user"`` or ``"assistant"``) and
                ``"content"`` (str). The role ``"assistant"`` is mapped to
                Gemini's ``"model"`` role internally.
            json_mode: When ``True``, appends a strict JSON-only instruction
                to the system prompt.
            temperature: Sampling temperature forwarded to Gemini's
                ``generationConfig``.

        Returns:
            The assistant's reply as a string.

        Raises:
            ValueError: If any message has a role other than
                ``"user"`` or ``"assistant"``.
            ConnectionError: If the Gemini API endpoint is unreachable.
            RuntimeError: If Gemini returns a non-2xx response, a safety
                block, or an unexpected response structure.
        """
        if not self._api_key:
            raise ConnectionError(
                "GEMINI_API_KEY is not set. Add it to your .env file: "
                "GEMINI_API_KEY=your-key-here"
            )

        for m in messages:
            if m.get("role") not in _VALID_ROLES:
                raise ValueError(
                    f"Invalid message role {m.get('role')!r}. "
                    f"Expected one of {_VALID_ROLES}."
                )

        system_text = system
        if json_mode:
            system_text = f"{system}\n\n{_JSON_INSTRUCTION}"

        contents = [
            {
                "role":  _ROLE_MAP[m["role"]],
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]

        payload = {
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents":           contents,
            "generationConfig":   {"temperature": temperature},
        }

        url = f"{_API_BASE}/{self.model}:generateContent"
        log.debug("Gemini request → model=%s  json_mode=%s", self.model, json_mode)

        try:
            response = self._session.post(
                url,
                json=payload,
                params={"key": self._api_key},
                timeout=self.timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(
                "Gemini API is not reachable. Check your internet connection."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise TimeoutError(
                f"Gemini request timed out after {self.timeout}s."
            ) from exc

        if not response.ok:
            # 429 (rate limit), 401/403 (auth), 5xx (server) → ConnectionError
            # so the pipeline fallbacks can catch them cleanly.
            if response.status_code in (429, 401, 403) or response.status_code >= 500:
                raise ConnectionError(
                    f"Gemini unavailable (HTTP {response.status_code}): "
                    f"{response.text[:120]}"
                )
            raise RuntimeError(
                f"Gemini returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
            candidate = data["candidates"][0]
            if candidate.get("finishReason") == "SAFETY":
                raise RuntimeError("Gemini blocked the response for safety reasons.")
            content = candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(
                f"Unexpected Gemini response structure: {response.text[:200]}"
            ) from exc

        log.debug("Gemini reply (%d chars)", len(content))
        return content
