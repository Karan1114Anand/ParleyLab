"""DeepSeek LLM client — primary provider for the opponent agent."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from parley_ai.llm.base import LLMClient

load_dotenv()

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "deepseek-chat"


class DeepSeekClient(LLMClient):
    """Sends chat requests to DeepSeek API via the standard OpenAI Python SDK.

    Reads ``DEEPSEEK_API_KEY`` from the environment.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        import openai

        self.model = model or _DEFAULT_MODEL
        self._api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.timeout = timeout
        
        # We only pass api_key and base_url to the client.
        # Key validation is deferred to chat() so that construction never raises
        # if keys are missing but the client is initialized.
        self._client = openai.OpenAI(
            api_key=self._api_key or "missing",
            base_url="https://api.deepseek.com",
            timeout=self.timeout
        )

    def chat(
        self,
        system: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat request to DeepSeek and return the reply text."""
        import openai
        
        if not self._api_key:
            raise ConnectionError(
                "DEEPSEEK_API_KEY is not set. Add it to your .env file: "
                "DEEPSEEK_API_KEY=your-key-here"
            )

        # Map to OpenAI format
        api_messages = [{"role": "system", "content": system}]
        for m in messages:
            role = m.get("role")
            if role not in ("user", "assistant"):
                raise ValueError(f"Invalid message role {role!r}.")
            api_messages.append({"role": role, "content": m["content"]})

        log.debug("DeepSeek request → model=%s  json_mode=%s", self.model, json_mode)

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("DeepSeek returned an empty response.")
            
            log.debug("DeepSeek reply (%d chars)", len(content))
            return content

        except openai.APIConnectionError as exc:
            raise ConnectionError(f"DeepSeek API is not reachable: {exc}") from exc
        except openai.APITimeoutError as exc:
            raise TimeoutError(f"DeepSeek request timed out: {exc}") from exc
        except openai.RateLimitError as exc:
            raise ConnectionError(f"DeepSeek rate limit exceeded (429): {exc}") from exc
        except openai.AuthenticationError as exc:
            raise ConnectionError(f"DeepSeek authentication failed (401/403): {exc}") from exc
        except openai.APIError as exc:
            # 5xx or other API errors
            raise ConnectionError(f"DeepSeek unavailable: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Unexpected error communicating with DeepSeek: {exc}") from exc
