"""Abstract base class for all LLM clients in ParleyLab."""

from abc import ABC, abstractmethod
from typing import List, Optional


class LLMClient(ABC):
    """
    Unified interface for LLM providers.

    All three agent roles (MoveParser, OpponentAgent, CriticAgent) consume
    this interface. Concrete implementations are GeminiClient and OllamaClient.

    Args:
        system:          System / instruction prompt for the model.
        messages:        Conversation history as a list of
                         {"role": "user"|"assistant", "content": "..."} dicts.
        response_format: Pass "json" to request structured JSON output.
        temperature:     Sampling temperature (0.0 = deterministic, 1.0 = creative).

    Returns:
        The model's response as a plain string (stripped of whitespace).
    """

    @abstractmethod
    def chat(
        self,
        system: str,
        messages: List[dict],
        response_format: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str: ...
