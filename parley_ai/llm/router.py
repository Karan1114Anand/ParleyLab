from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from parley_ai.llm.base import LLMClient
from parley_ai.llm.ollama import OllamaClient
from parley_ai.llm.tracker import get_tracker

load_dotenv()

log = logging.getLogger(__name__)

_FALLBACK_MODEL = os.getenv("PARLEYLAB_FALLBACK_OLLAMA_MODEL", "phi3:latest")

class LLMRouter(LLMClient):
    def __init__(
        self,
        agent_role: str = "opponent",
        base_url: str | None = None,
    ) -> None:
        self.role = agent_role.upper()
        
        # Route based on the agent's specific role
        if self.role == "OPPONENT":
            self.provider = os.getenv("PARLEYLAB_OPPONENT_PROVIDER", "openrouter").lower()
            self.model = os.getenv("PARLEYLAB_OPPONENT_MODEL", "google/gemma-2-9b-it:free")
        elif self.role == "PARSER":
            self.provider = os.getenv("PARLEYLAB_PARSER_PROVIDER", "openrouter").lower()
            self.model = os.getenv("PARLEYLAB_PARSER_MODEL", "google/gemma-2-9b-it:free")
        else:
            # Default fallback for Critic or any other unhandled role
            self.provider = os.getenv("PARLEYLAB_CRITIC_PROVIDER", "gemini").lower()
            self.model = os.getenv("PARLEYLAB_CRITIC_MODEL", "gemini-3.5-flash")

        self._active_provider = self.provider
        self._fallback = OllamaClient(model=_FALLBACK_MODEL, base_url=base_url)

        if self.provider == "openrouter":
            from parley_ai.llm.openrouter import OpenRouterClient
            self._client = OpenRouterClient(model=self.model)
        elif self.provider == "gemini":
            from parley_ai.llm.gemini import GeminiClient
            self._client = GeminiClient(model=self.model)
        elif self.provider == "ollama":
            self._client = OllamaClient(model=self.model, base_url=base_url)
            self._fallback = None
        else:
            raise ValueError(f"Unknown provider {self.provider!r}")

        log.info(
            "LLMRouter [%s] → %s (model=%s) | fallback=%s",
            self.role, self.provider.capitalize(), self._client.model, _FALLBACK_MODEL
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
        tracker = get_tracker()
        
        # Primary Call for Cloud Providers
        if self._active_provider in ("gemini", "openrouter", "deepseek"):
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
                        "%s failed (%s) — auto-switching to Ollama/%s",
                        self._active_provider.title(), reason, _FALLBACK_MODEL,
                    )
                    tracker.switched_to_ollama(reason)
                    self._active_provider = "ollama"
                    get_tracker().current_provider = "ollama"
                    self._client = self._fallback
                    self._fallback = None
                    # Fall through to Ollama call below
                else:
                    log.error("Provider failed and no Ollama fallback available: %s", exc)
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
