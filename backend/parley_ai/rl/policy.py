"""
PPOPolicy — thin wrapper around the trained Stable-Baselines3 PPO model.

Responsibilities:
  - Load best_model.zip at startup (non-fatal on failure — healthz reports it)
  - Expose predict(obs) -> int (returns strategic action 0-4)
  - Provide a heuristic fallback if the model isn't loaded
  - Expose action_label(int) -> str for logging / reveal
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Action vocabulary ──────────────────────────────────────────────────────────
ACTION_MEANINGS: dict[int, str] = {
    0: "Hold Firm",
    1: "Concede Small",   # 5% toward user
    2: "Concede Large",   # 15% toward user
    3: "Bluff",           # 5% away from user
    4: "Walk Away",
}

# ── Observation schema (7-dim, all normalised to [0, 1]) ─────────────────────
# [0] own_offer_norm
# [1] opponent_offer_norm
# [2] turn_norm
# [3] own_concession_rate
# [4] opponent_concession_rate
# [5] gap_norm
# [6] turns_since_last_concession_norm


def _default_model_path() -> str:
    """Resolve best_model.zip relative to this file's location in the tree."""
    # backend/parley_ai/rl/policy.py → up 4 levels → project root / models
    here = Path(__file__).resolve()
    project_root = here.parent.parent.parent.parent  # backend/ → project root
    return str(project_root / "models" / "best_model.zip")


class PPOPolicy:
    """
    Wraps the trained Stable-Baselines3 PPO negotiation policy.

    Loading is non-fatal: if the model file is missing or SB3 is unavailable,
    ``is_loaded`` returns False and ``predict`` uses a simple heuristic fallback.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        resolved_path = model_path or os.getenv("RL_MODEL_PATH") or _default_model_path()
        self._model = None
        self._loaded = False

        try:
            from stable_baselines3 import PPO  # type: ignore

            if not Path(resolved_path).exists():
                raise FileNotFoundError(f"Model file not found: {resolved_path}")

            self._model = PPO.load(resolved_path, device="cpu")
            self._loaded = True
            logger.info("PPO policy loaded from %s", resolved_path)
        except ImportError:
            logger.warning("stable_baselines3 not installed — using heuristic policy.")
        except FileNotFoundError as exc:
            logger.error("PPO model load failed: %s — using heuristic policy.", exc)
        except Exception as exc:
            logger.error("Unexpected PPO load error: %s — using heuristic policy.", exc)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, obs: np.ndarray) -> int:
        """
        Given a 7-dimensional normalised observation, return an action (0-4).

        Falls back to a simple rule-based heuristic if the model isn't loaded.
        """
        if self._loaded and self._model is not None:
            try:
                action, _ = self._model.predict(obs, deterministic=True)
                return int(action)
            except Exception as exc:
                logger.error("PPO predict error: %s — using heuristic.", exc)
        return self._heuristic(obs)

    def action_label(self, action: int) -> str:
        return ACTION_MEANINGS.get(action, "Unknown")

    @staticmethod
    def _heuristic(obs: np.ndarray) -> int:
        """
        Simple rule-based fallback when the PPO model is unavailable.

        Rules:
          - Near deadline (turn_norm > 0.8): always Concede Small
          - Gap < 5%: Hold Firm (almost there)
          - Default: Concede Small
        """
        turn_norm = float(obs[2]) if len(obs) > 2 else 0.5
        gap_norm = float(obs[5]) if len(obs) > 5 else 0.5

        if turn_norm > 0.8:
            return 1  # Concede Small — deadline pressure
        if gap_norm < 0.05:
            return 0  # Hold Firm — nearly at agreement
        return 1      # Concede Small as sensible default
