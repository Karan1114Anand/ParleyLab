"""LLM provider router — selects and wraps the active LLM client.

Currently defaults to Ollama only. Gemini is available as an explicit
opt-in but is NEVER activated automatically — Ollama failure raises,
it does not fall back silently.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from parley_ai.llm.base import LLMClient
from parley_ai.llm.ollama import OllamaClient

load_dotenv()

log = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = {"ollama", "gemini"}


class LLMRouter(LLMClient):
    """Routes ``chat()`` calls to the configured LLM provider.

    The active provider is chosen by the ``PARLEYLAB_LLM_PROVIDER``
    environment variable (default: ``"ollama"``). Switching to Gemini
    requires an explicit configuration change — the router never falls
    back silently.

    Ollama failure (connection error, timeout, bad response) is logged and
    re-raised immediately. No retry, no fallback.

    Example::

        # Uses env config (PARLEYLAB_LLM_PROVIDER defaults to "ollama")
        router = LLMRouter()
        reply = router.chat(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Explicit provider + model override
        router = LLMRouter(provider="ollama", model="phi3:latest")

    Args:
        provider: ``"ollama"`` or ``"gemini"``. Defaults to the
            ``PARLEYLAB_LLM_PROVIDER`` environment variable, or
            ``"ollama"`` if not set.
        model: Model tag passed to the underlying client. When ``None``,
            each client reads its own default from the environment.
        base_url: Ollama base URL override (ignored for Gemini).
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        provider = (
            provider or os.getenv("PARLEYLAB_LLM_PROVIDER", "ollama")
        ).lower().strip()

        if provider not in _SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unknown provider {provider!r}. "
                f"Supported: {sorted(_SUPPORTED_PROVIDERS)}."
            )

        if provider == "ollama":
            self._client: LLMClient = OllamaClient(model=model, base_url=base_url)
            log.info("LLMRouter active provider: Ollama (model=%s)", self._client.model)

        elif provider == "gemini":
            from parley_ai.llm.gemini import GeminiClient
            self._client = GeminiClient(model=model)
            log.info("LLMRouter active provider: Gemini (model=%s)", self._client.model)

        self.provider = provider

    def chat(
        self,
        system: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Delegate to the active provider. Logs and re-raises on failure.

        Args:
            system: System prompt.
            messages: Conversation history (``role``/``content`` dicts).
            json_mode: Request JSON-only output.
            temperature: Sampling temperature.

        Returns:
            The assistant's reply as a string.

        Raises:
            ConnectionError: If the Ollama endpoint is unreachable. Gemini
                is NOT tried as a fallback.
            TimeoutError: If the request exceeds the provider's timeout.
            RuntimeError: If the provider returns an unexpected response.
        """
        try:
            return self._client.chat(
                system=system,
                messages=messages,
                json_mode=json_mode,
                temperature=temperature,
            )
        except Exception as exc:
            log.error(
                "LLM call failed [provider=%s, type=%s]: %s",
                self.provider,
                type(exc).__name__,
                exc,
            )
            raise
