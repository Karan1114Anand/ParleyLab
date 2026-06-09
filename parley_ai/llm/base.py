"""Abstract base class for all LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Common interface every LLM provider must implement.

    Agents talk to this interface only — the concrete provider (Ollama,
    Gemini, …) is chosen at construction time and never referenced again.
    """

    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Send a multi-turn chat request and return the assistant reply.

        Args:
            system: The system prompt that sets the assistant's persona and
                task. Passed as a top-level system message (Ollama) or as a
                ``system_instruction`` block (Gemini).
            messages: Ordered conversation history. Each element must be a
                dict with keys:

                - ``"role"`` (str): ``"user"`` or ``"assistant"``.
                - ``"content"`` (str): The message text.

            json_mode: When ``True``, instruct the model to return a raw
                JSON string and nothing else. Callers are responsible for
                parsing the result with ``json.loads()``.
            temperature: Sampling temperature in ``[0.0, 2.0]``. Lower
                values make output more deterministic. Defaults to ``0.7``.

        Returns:
            The assistant's reply as a plain string. When ``json_mode`` is
            ``True`` the string should be parseable by ``json.loads()``.

        Raises:
            ConnectionError: If the provider endpoint is unreachable.
            RuntimeError: If the provider returns an unexpected response
                structure or a non-2xx HTTP status.
            ValueError: If ``messages`` contains an entry with an
                unrecognised role, or if ``temperature`` is out of range.
        """
