"""
parley_ai/rl/policy.py — PPO Strategic Policy Inference Wrapper
================================================================

Wraps a Stable-Baselines3 PPO model for deterministic single-turn inference
at runtime. The policy is loaded once at server startup (via
``core.orchestrator.init_singletons()``) and serves all subsequent requests
via a sub-millisecond MLP forward pass on CPU.

Decoupling Contract
-------------------
This module makes **no network calls** and has **no dependency on any LLM
client**. It is the boundary between the RL control plane (strategic decision)
and the LLM dialogue plane (natural-language rendering). The orchestrator
receives the action dict from ``predict()`` and passes it separately to
``parley_ai.agents.opponent.generate_opponent_response()``.

Degraded Mode
-------------
If the model file is missing or ``stable-baselines3`` is not installed,
``StrategyPolicy`` initialises in a **degraded mode**:

  - ``is_loaded`` → ``False``
  - ``predict()`` returns ``{"action_id": 0, "action_name": "Hold Firm", ...}``

This guarantees the server can start and serve requests without the model
weights present. The orchestrator logs a WARNING when degraded mode is active.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Discrete action space — matches training environment in training/env.py
ACTION_MAP: dict[int, tuple[str, str]] = {
    0: ("Hold Firm",     "Opponent maintains their position."),
    1: ("Concede Small", "Opponent moves slightly toward your offer."),
    2: ("Concede Large", "Opponent makes a significant concession."),
    3: ("Bluff",         "Opponent moves away from your offer — testing your resolve."),
    4: ("Walk Away",     "Opponent walks away from the negotiation."),
}

# Deterministic fallback action used in degraded mode (no model weights)
_DEGRADED_ACTION: dict = {
    "action_id":   0,
    "action_name": "Hold Firm",
    "description": "Opponent maintains their position. [DEGRADED MODE — PPO model not loaded]",
}

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "best_model.zip"


class StrategyPolicy:
    """
    Wraps a trained Stable-Baselines3 PPO model for single-turn inference.

    Load once at startup, call ``predict()`` on every negotiation turn.
    The forward pass is a single MLP evaluation — sub-millisecond on CPU.

    If the model file does not exist or ``stable-baselines3`` is unavailable,
    the policy enters **degraded mode**: ``is_loaded`` is False and all
    ``predict()`` calls return a deterministic ``Hold Firm`` fallback,
    allowing the server to remain operational.

    Example (loaded)::

        policy = StrategyPolicy()
        result = policy.predict([0.78, 0.92, 0.3, 0.05, 0.12, 0.14, 0.20])
        # {'action_id': 0, 'action_name': 'Hold Firm', 'description': '...'}

    Example (degraded)::

        policy = StrategyPolicy(model_path="/nonexistent/model.zip")
        # [WARNING] PPO model not found — running in DEGRADED MODE
        assert policy.is_loaded is False
        result = policy.predict([0.5, 0.5, 0.5, 0.0, 0.0, 0.5, 0.0])
        # Returns Hold Firm fallback silently
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        """
        Attempt to load the PPO model from disk.

        Initialises in degraded mode (no exception raised) if:
          - ``stable-baselines3`` is not installed.
          - The model file does not exist at ``model_path``.

        Args:
            model_path: Path to the ``.zip`` model file produced by
                Stable-Baselines3. Defaults to ``models/best_model.zip``
                relative to the project root.
        """
        self._model = None
        path = Path(model_path) if model_path is not None else _DEFAULT_MODEL_PATH

        # ── Attempt SB3 import ────────────────────────────────────────────────
        try:
            from stable_baselines3 import PPO as _PPO
        except ImportError:
            log.warning(
                "[DEGRADED MODE] stable-baselines3 not installed — "
                "PPO policy inactive, defaulting to deterministic heuristics. "
                "Install with: pip install stable-baselines3"
            )
            return

        # ── Attempt model load ────────────────────────────────────────────────
        if not path.exists():
            log.warning(
                "[DEGRADED MODE] PPO model not found at '%s' — "
                "PPO policy inactive, defaulting to deterministic heuristics. "
                "Run training/train.py to generate weights, or place "
                "best_model.zip in the models/ directory.",
                path,
            )
            return

        try:
            self._model = _PPO.load(str(path), device="cpu")
            log.info(
                "StrategyPolicy loaded successfully from '%s' [CPU inference].", path
            )
        except Exception as exc:
            log.warning(
                "[DEGRADED MODE] Failed to load PPO model from '%s': %s — "
                "PPO policy inactive, defaulting to deterministic heuristics.",
                path, exc,
            )
            self._model = None

    @property
    def is_loaded(self) -> bool:
        """True when the PPO model is loaded and ready to serve predictions."""
        return self._model is not None

    def predict(self, state_vector: list[float]) -> dict:
        """
        Run one forward pass and return the opponent's strategic action.

        In degraded mode (``is_loaded == False``), returns a deterministic
        ``Hold Firm`` action without raising an exception.

        Args:
            state_vector: A 7-element list of floats, each in ``[0.0, 1.0]``,
                in this order:

                0. ``own_offer_norm``
                1. ``opponent_offer_norm``
                2. ``turn_norm``
                3. ``own_concession_rate``
                4. ``opponent_concession_rate``
                5. ``gap_norm``
                6. ``turns_since_last_concession_norm``

        Returns:
            A dict with:

            - ``action_id`` (int): Integer in ``{0, 1, 2, 3, 4}``.
            - ``action_name`` (str): Human-readable label.
            - ``description`` (str): What the action means from the user's
              perspective.

        Raises:
            TypeError: If ``state_vector`` is not a list.
            ValueError: If ``state_vector`` does not have exactly 7 elements,
                or if any element is outside ``[0.0, 1.0]``.
        """
        if not isinstance(state_vector, list):
            raise TypeError(
                f"state_vector must be a list, got {type(state_vector).__name__}."
            )
        if len(state_vector) != 7:
            raise ValueError(
                f"state_vector must have exactly 7 elements, got {len(state_vector)}."
            )
        if any(not (0.0 <= float(v) <= 1.0) for v in state_vector):
            raise ValueError("All elements of state_vector must be in [0.0, 1.0].")

        # Degraded mode: return deterministic fallback without inference
        if self._model is None:
            return _DEGRADED_ACTION.copy()

        obs = np.array(state_vector, dtype=np.float32)
        action_array, _ = self._model.predict(obs, deterministic=True)
        action_id = int(action_array)
        name, description = ACTION_MAP[action_id]

        return {
            "action_id":   action_id,
            "action_name": name,
            "description": description,
        }
