"""LLM provider router with automatic Gemini → Ollama fallback.

Primary provider: configured by PARLEYLAB_LLM_PROVIDER (default: "gemini").
Fallback:         Ollama phi3:latest — fastest free local model.

When Gemini returns a ConnectionError (includes 429 rate-limit, 401/403 auth
failures, or network unreachability), the router silently falls back to Ollama
and stays there for the lifetime of the process. All calls are tracked via
parley_ai.llm.tracker for the /api/status/llm endpoint.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from parley_ai.llm.base import LLMClient
from parley_ai.llm.ollama import OllamaClient
from parley_ai.llm.tracker import get_tracker

load_dotenv()

log = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = {"ollama", "gemini", "groq"}
_FALLBACK_MODEL = os.getenv("PARLEYLAB_FALLBACK_OLLAMA_MODEL", "phi3:latest")


class LLMRouter(LLMClient):
    """Routes chat() to the configured LLM provider.

    Auto-fallback: when the primary provider is Gemini and it raises a
    ConnectionError (rate limit, auth failure, or network issue), the router
    switches to Ollama (phi3:latest by default) and stays on Ollama for all
    subsequent calls.

    All call outcomes are recorded in the module-level LlmTracker so the
    /api/status/llm endpoint can return live usage stats.

    Args:
        provider: "gemini" or "ollama". Defaults to PARLEYLAB_LLM_PROVIDER env
            var, or "gemini" if not set.
        model: Model override for the primary client.
        base_url: Ollama base URL override (ignored for Gemini).
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        provider = (
            provider or os.getenv("PARLEYLAB_LLM_PROVIDER", "gemini")
        ).lower().strip()

        if provider not in _SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unknown provider {provider!r}. "
                f"Supported: {sorted(_SUPPORTED_PROVIDERS)}."
            )

        self.provider = provider
        self._active_provider = provider

        if provider == "ollama":
            self._client: LLMClient = OllamaClient(model=model, base_url=base_url)
            self._fallback: LLMClient | None = None
            log.info("LLMRouter → Ollama (model=%s)", self._client.model)

        elif provider == "gemini":
            from parley_ai.llm.gemini import GeminiClient
            self._client = GeminiClient(model=model)
            # Pre-build the fallback client so switching costs nothing at call time
            self._fallback = OllamaClient(model=_FALLBACK_MODEL, base_url=base_url)
            log.info(
                "LLMRouter → Gemini (model=%s) | fallback=%s",
                self._client.model, _FALLBACK_MODEL,
            )

        elif provider == "groq":
            from parley_ai.llm.groq import GroqClient
            self._client = GroqClient(model=model)
            self._fallback = OllamaClient(model=_FALLBACK_MODEL, base_url=base_url)
            log.info(
                "LLMRouter → Groq (model=%s) | fallback=%s",
                self._client.model, _FALLBACK_MODEL,
            )

        get_tracker().current_provider = self._active_provider

    @property
    def active_provider(self) -> str:
        return self._active_provider

    def chat(
        self,
        system: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Delegate to the active provider; fall back to Ollama on Gemini failure.

        Raises:
            ConnectionError: If Ollama is unreachable (no further fallback).
            TimeoutError: Provider timed out.
            RuntimeError: Unexpected provider response.
        """
        tracker = get_tracker()

        if self._active_provider in ("gemini", "groq"):
            tracker.gemini_started()
            try:
                result = self._client.chat(
                    system=system,
                    messages=messages,
                    json_mode=json_mode,
                    temperature=temperature,
                )
                tracker.gemini_ok()
                return result

            except ConnectionError as exc:
                msg = str(exc)
                if "429" in msg:
                    tracker.gemini_rate_limited(msg)
                    reason = "rate limit (429)"
                else:
                    tracker.gemini_failed(msg)
                    reason = f"{self._active_provider}: {msg[:80]}"

                if self._fallback is not None:
                    log.warning(
                        "Gemini failed (%s) — auto-switching to Ollama/%s",
                        reason, _FALLBACK_MODEL,
                    )
                    tracker.switched_to_ollama(reason)
                    self._active_provider = "ollama"
                    self._client = self._fallback
                    self._fallback = None
                    # Fall through to Ollama call below
                else:
                    log.error("Gemini failed and no Ollama fallback available: %s", exc)
                    raise

        # Ollama path — reached either as primary provider or after fallback switch
        if self._active_provider == "ollama":
            tracker.ollama_started()
            try:
                result = self._client.chat(
                    system=system,
                    messages=messages,
                    json_mode=json_mode,
                    temperature=temperature,
                )
                tracker.ollama_ok()
                return result
            except Exception as exc:
                tracker.ollama_failed(str(exc))
                log.error("Ollama call failed: %s", exc)
                raise

        raise RuntimeError(f"Unknown active provider: {self._active_provider!r}")
