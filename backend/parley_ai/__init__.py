"""
parley_ai — AI/ML package for ParleyLab.

All AI logic (LLM clients, RL policy, agent wrappers) lives here.
The FastAPI backend imports exclusively from this package.
"""

from parley_ai.llm.base import LLMClient
from parley_ai.llm.gemini import GeminiClient
from parley_ai.rl.policy import PPOPolicy
from parley_ai.agents.move_parser import MoveParser, ParsedMove
from parley_ai.agents.opponent import OpponentAgent, HiddenContext
from parley_ai.agents.critic import CriticAgent, CriticFeedback

__all__ = [
    "LLMClient",
    "GeminiClient",
    "PPOPolicy",
    "MoveParser",
    "ParsedMove",
    "OpponentAgent",
    "HiddenContext",
    "CriticAgent",
    "CriticFeedback",
]
