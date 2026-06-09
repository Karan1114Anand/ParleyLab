"""Ollama LLM client — primary provider for ParleyLab."""

from __future__ import annotations

import logging
import os

import requests
from dotenv import load_dotenv

from parley_ai.llm.base import LLMClient

load_dotenv()

log = logging.getLogger(__name__)

_CHAT_PATH = "/api/chat"
_VALID_ROLES = {"user", "assistant"}


class OllamaClient(LLMClient):
    """Sends chat requests to a locally running Ollama instance.

    This is the only LLM provider used in the ParleyLab demo. All agents
    that need language generation construct an ``OllamaClient`` (or receive
    one via ``LLMRouter``) and call ``chat()``.

    Example::

        client = OllamaClient(model="phi3:latest")
        reply = client.chat(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Say hello."}],
        )

    Args:
        model: Ollama model tag, e.g. ``"llama3.1:8b"`` or ``"phi3:latest"``.
            Defaults to the ``PARLEYLAB_OLLAMA_MODEL_DEFAULT`` environment
            variable, or ``"llama3.1:8b"`` if the variable is not set.
        base_url: Ollama HTTP base URL. Defaults to the
            ``OLLAMA_BASE_URL`` environment variable, or
            ``"http://localhost:11434"`` if not set.
        timeout: Per-request timeout in seconds. Defaults to ``60``.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model or os.getenv(
            "PARLEYLAB_OLLAMA_MODEL_DEFAULT", "llama3.1:8b"
        )
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def chat(
        self,
        system: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat request to Ollama and return the reply text.

        Args:
            system: System prompt placed as the first message with
                ``role: "system"``.
            messages: Conversation history — list of dicts with keys
                ``"role"`` (``"user"`` or ``"assistant"``) and
                ``"content"`` (str).
            json_mode: When ``True``, sets Ollama's ``format: "json"``
                flag, constraining output to valid JSON. The caller must
                also include JSON-structure instructions in the prompt.
            temperature: Sampling temperature. Passed to Ollama via the
                ``options.temperature`` field.

        Returns:
            The assistant's reply as a string.

        Raises:
            ValueError: If any message has a role other than
                ``"user"`` or ``"assistant"``.
            ConnectionError: If Ollama is not reachable at ``base_url``.
            RuntimeError: If Ollama returns a non-2xx response or an
                unexpected response body.
        """
        for m in messages:
            if m.get("role") not in _VALID_ROLES:
                raise ValueError(
                    f"Invalid message role {m.get('role')!r}. "
                    f"Expected one of {_VALID_ROLES}."
                )

        payload: dict = {
            "model":    self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream":   False,
            "options":  {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"

        url = self.base_url + _CHAT_PATH
        log.debug("Ollama request → %s  model=%s  json_mode=%s", url, self.model, json_mode)

        try:
            response = self._session.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(
                f"Ollama is not reachable at {self.base_url}. "
                "Ensure Ollama is running: `ollama serve`."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout}s. "
                "The model may be loading — try again or use a smaller model."
            ) from exc

        if not response.ok:
            raise RuntimeError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            content = response.json()["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise RuntimeError(
                f"Unexpected Ollama response structure: {response.text[:200]}"
            ) from exc

        log.debug("Ollama reply (%d chars)", len(content))
        return content
