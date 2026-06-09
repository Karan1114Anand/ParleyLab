"""PPO policy loader and inference wrapper."""

from __future__ import annotations

from pathlib import Path

import numpy as np

ACTION_MAP: dict[int, tuple[str, str]] = {
    0: ("Hold Firm",     "Opponent maintains their position."),
    1: ("Concede Small", "Opponent moves slightly toward your offer."),
    2: ("Concede Large", "Opponent makes a significant concession."),
    3: ("Bluff",         "Opponent moves away from your offer — testing your resolve."),
    4: ("Walk Away",     "Opponent walks away from the negotiation."),
}

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "best_model.zip"


class StrategyPolicy:
    """Wraps a trained Stable-Baselines3 PPO model for single-turn inference.

    Load once at startup, call ``predict`` on every turn. The forward pass
    is a single MLP evaluation — sub-millisecond on CPU.

    Example::

        policy = StrategyPolicy()
        result = policy.predict([0.78, 0.92, 0.3, 0.05, 0.12, 0.14, 0.20])
        # {'action_id': 0, 'action_name': 'Hold Firm', 'description': '...'}
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        """Load the PPO model from disk.

        Args:
            model_path: Path to the ``.zip`` model file produced by
                Stable-Baselines3. Defaults to ``models/best_model.zip``
                relative to the project root.

        Raises:
            FileNotFoundError: If no model file exists at ``model_path``.
            ImportError: If ``stable-baselines3`` is not installed.
        """
        try:
            from stable_baselines3 import PPO
        except ImportError as exc:
            raise ImportError(
                "stable-baselines3 is required. "
                "Install it with: pip install stable-baselines3"
            ) from exc

        path = Path(model_path) if model_path is not None else _DEFAULT_MODEL_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"PPO model not found at '{path}'. "
                "Ensure models/best_model.zip exists in the project root."
            )

        self._model = PPO.load(str(path), device="cpu")

    def predict(self, state_vector: list[float]) -> dict:
        """Run one forward pass and return the opponent's strategic action.

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

        obs = np.array(state_vector, dtype=np.float32)
        action_array, _ = self._model.predict(obs, deterministic=True)
        action_id = int(action_array)
        name, description = ACTION_MAP[action_id]

        return {
            "action_id":   action_id,
            "action_name": name,
            "description": description,
        }
