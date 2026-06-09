"""Groq LLM client — OpenAI-compatible inference API.

Free tier: ~14,400 req/day, very fast LPU inference.
Get a key at https://console.groq.com/keys

Switch by setting:
    PARLEYLAB_LLM_PROVIDER=groq
    GROQ_API_KEY=gsk_...
    PARLEYLAB_MODEL=llama-3.1-8b-instant   # or llama-3.3-70b-versatile
"""

from __future__ import annotations

import logging
import os

import requests
from dotenv import load_dotenv

from parley_ai.llm.base import LLMClient

load_dotenv()

log = logging.getLogger(__name__)

_API_BASE = "https://api.groq.com/openai/v1/chat/completions"
_DEFAULT_MODEL = "llama-3.1-8b-instant"
_VALID_ROLES = {"user", "assistant"}
_JSON_INSTRUCTION = "Reply ONLY with valid JSON, no preamble or explanation."


class GroqClient(LLMClient):
    """Sends chat requests to Groq's OpenAI-compatible API.

    Args:
        model: Groq model ID. Defaults to ``"llama-3.1-8b-instant"``.
            Other good free options: ``"llama-3.3-70b-versatile"``,
            ``"gemma2-9b-it"``, ``"mixtral-8x7b-32768"``.
        api_key: Groq API key. Defaults to ``GROQ_API_KEY`` env var.
        timeout: Per-request timeout in seconds. Defaults to ``30``.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.model = model or os.getenv("PARLEYLAB_GROQ_MODEL", _DEFAULT_MODEL)
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self.timeout = timeout
        self._session = requests.Session()

    def chat(
        self,
        system: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        if not self._api_key:
            raise ConnectionError(
                "GROQ_API_KEY is not set. Add it to your .env file: "
                "GROQ_API_KEY=gsk_... (get one at https://console.groq.com/keys)"
            )

        for m in messages:
            if m.get("role") not in _VALID_ROLES:
                raise ValueError(
                    f"Invalid message role {m.get('role')!r}. "
                    f"Expected one of {_VALID_ROLES}."
                )

        system_text = f"{system}\n\n{_JSON_INSTRUCTION}" if json_mode else system

        payload: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_text}]
            + [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        log.debug("Groq request → model=%s json_mode=%s", self.model, json_mode)

        try:
            response = self._session.post(
                _API_BASE,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self.timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(
                "Groq API is not reachable. Check your internet connection."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise TimeoutError(
                f"Groq request timed out after {self.timeout}s."
            ) from exc

        if not response.ok:
            if response.status_code in (429, 401, 403) or response.status_code >= 500:
                raise ConnectionError(
                    f"Groq unavailable (HTTP {response.status_code}): "
                    f"{response.text[:120]}"
                )
            raise RuntimeError(
                f"Groq returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(
                f"Unexpected Groq response structure: {response.text[:200]}"
            ) from exc

        log.debug("Groq reply (%d chars)", len(content))
        return content
