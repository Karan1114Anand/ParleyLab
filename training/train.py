"""
training/train.py — PPO Training Entrypoint
============================================

Trains a Proximal Policy Optimization (PPO) agent on the ``NegotiationEnv``
Farama-Gymnasium custom environment. The trained policy weights are saved to
the ``models/`` directory and consumed at runtime by ``parley_ai/rl/policy.py``
for sub-millisecond strategic action inference.

The environment and evaluation logic are isolated in their own modules:
  - ``training/env.py``  — ``NegotiationEnv`` (custom Gymnasium environment)
  - ``training/eval.py`` — ``evaluate()`` and greedy baseline comparison

Architecture
------------
  PPO policy: MlpPolicy  [64 × 64 ReLU network, shared actor-critic trunk]
  Algorithm : Proximal Policy Optimization (Schulman et al., 2017)
  Objective : Clip-ratio surrogate loss + entropy regularisation + value loss
  Entropy   : Annealed from 0.05 → 0.005 over training to shift from
              exploration to deterministic greedy exploitation

Hyperparameters (300k-step run)
-------------------------------
  learning_rate : 3e-4 (Adam)
  n_steps       : 2048  (rollout buffer length)
  batch_size    : 64
  n_epochs      : 10
  gamma         : 0.99  (discount factor)
  gae_lambda    : 0.95  (GAE advantage estimation)
  clip_range    : 0.2   (PPO clip ratio)
  vf_coef       : 0.5   (value loss coefficient)
  max_grad_norm : 0.5

Usage::

    # Train from scratch
    python -m training.train --timesteps 300000

    # Evaluate a checkpoint
    python -m training.eval --model_path models/best_model --episodes 200
"""

from __future__ import annotations

import json
import logging
import os

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

from training.env import NegotiationEnv

log = logging.getLogger(__name__)


# ── Entropy annealing callback ─────────────────────────────────────────────────

class EntropyAnnealCallback(BaseCallback):
    """
    Linearly decay the PPO entropy coefficient over the training run.

    SB3's ``ent_coef`` does not natively accept a schedule, so we update
    ``model.ent_coef`` at every step via this callback.

    Args:
        start: Initial entropy coefficient (high exploration).
        end:   Final entropy coefficient (near-greedy exploitation).
        total_timesteps: Reference denominator for progress calculation.
    """

    def __init__(
        self,
        start: float = 0.05,
        end: float = 0.005,
        total_timesteps: int = 300_000,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self.start            = start
        self.end              = end
        self.total_timesteps  = total_timesteps

    def _on_step(self) -> bool:
        progress            = self.num_timesteps / self.total_timesteps
        new_ent             = self.start + (self.end - self.start) * progress
        self.model.ent_coef = new_ent
        return True


# ── Training entrypoint ────────────────────────────────────────────────────────

def train(
    total_timesteps: int = 300_000,
    save_dir: str = "models",
    log_dir: str = "logs",
) -> PPO:
    """
    Train a PPO agent on the buyer-side negotiation environment.

    Checkpoints are saved every 50k steps to ``save_dir/``. The best model
    by mean evaluation reward is saved as ``best_model.zip`` (the file
    consumed by ``StrategyPolicy`` at runtime).

    Args:
        total_timesteps: Total environment steps across all episodes.
        save_dir: Directory for model checkpoints and metadata.
        log_dir: Directory for Monitor CSVs and EvalCallback logs.

    Returns:
        The trained ``PPO`` model instance.

    Raises:
        ImportError: If ``stable-baselines3`` is not installed.
    """
    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(log_dir,  exist_ok=True)

    # ── Environment setup ────────────────────────────────────────────────────
    env_train = Monitor(NegotiationEnv(max_turns=10, agent_is_seller=False), log_dir)
    env_eval  = Monitor(NegotiationEnv(max_turns=10, agent_is_seller=False))

    log.info("Validating environment against Gymnasium API specification...")
    check_env(NegotiationEnv(max_turns=10, agent_is_seller=False), warn=True)
    log.info("Environment check passed. Observation shape: (7,)")

    # ── Callbacks ─────────────────────────────────────────────────────────────
    eval_cb = EvalCallback(
        env_eval,
        best_model_save_path=save_dir,
        log_path=log_dir,
        eval_freq=10_000,
        n_eval_episodes=50,
        deterministic=True,
        verbose=1,
    )
    checkpoint_cb = CheckpointCallback(
        save_freq=50_000,
        save_path=save_dir,
        name_prefix="negotiation_ppo",
    )
    entropy_cb = EntropyAnnealCallback(
        start=0.05, end=0.005, total_timesteps=total_timesteps
    )

    # ── Model definition ──────────────────────────────────────────────────────
    model = PPO(
        policy="MlpPolicy",
        env=env_train,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=320,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.05,       # initial value; annealed by EntropyAnnealCallback
        vf_coef=0.5,
        max_grad_norm=0.5,
        verbose=1,
        # tensorboard_log=log_dir,  # uncomment to enable TensorBoard logging
    )

    log.info(
        "Training PPO — %s timesteps | env=NegotiationEnv(10 turns, buyer-side) "
        "| arch=MlpPolicy [64×64] | ent_coef 0.05→0.005 (annealed)",
        f"{total_timesteps:,}",
    )
    model.learn(
        total_timesteps=total_timesteps,
        callback=[eval_cb, checkpoint_cb, entropy_cb],
        progress_bar=True,
    )

    # ── Persist final checkpoint and metadata ─────────────────────────────────
    final_path = os.path.join(save_dir, "negotiation_agent_final")
    model.save(final_path)
    log.info("Final model saved: %s.zip", final_path)

    metadata = {
        "algorithm":    "PPO",
        "architecture": "MlpPolicy [64×64 ReLU, shared actor-critic]",
        "total_timesteps": total_timesteps,
        "agent_role":   "buyer",
        "observation_schema": [
            "own_offer_norm",
            "opponent_offer_norm",
            "turn_norm",
            "own_concession_rate",
            "opponent_concession_rate",
            "gap_norm",
            "turns_since_last_concession_norm",
        ],
        "action_meanings": {
            "0": "Hold Firm",
            "1": "Concede Small (5% toward opponent)",
            "2": "Concede Large (15% toward opponent)",
            "3": "Bluff (move 5% away from opponent)",
            "4": "Walk Away (terminate, take BATNA)",
        },
        "hyperparameters": {
            "learning_rate": 3e-4,
            "n_steps":       2048,
            "batch_size":    64,
            "n_epochs":      10,
            "gamma":         0.99,
            "gae_lambda":    0.95,
            "clip_range":    0.2,
            "ent_coef_start": 0.05,
            "ent_coef_end":   0.005,
            "vf_coef":       0.5,
            "max_grad_norm": 0.5,
        },
    }
    metadata_path = os.path.join(save_dir, "model_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Training metadata saved: %s", metadata_path)

    return model


# ── Inference helpers (used by parley_ai/rl/policy.py at runtime) ─────────────

def load_agent(model_path: str = "models/best_model") -> PPO:
    """Load a trained PPO agent from a Stable-Baselines3 ``.zip`` checkpoint."""
    return PPO.load(model_path, device="cpu")


def get_strategy_action(
    model: PPO,
    own_offer: float,
    opponent_offer: float,
    turn: int,
    max_turns: int,
    own_concession_rate: float,
    opponent_concession_rate: float,
    turns_since_last_concession: int,
) -> dict:
    """
    Convenience wrapper: build an observation vector and run one forward pass.

    All inputs should be in the same normalised [0, 100] space as the
    training environment.

    Returns:
        Dict with ``action_id`` (int), ``action_name`` (str), ``description`` (str).
    """
    obs = np.array(
        [
            own_offer / 100.0,
            opponent_offer / 100.0,
            turn / max_turns,
            own_concession_rate,
            opponent_concession_rate,
            abs(own_offer - opponent_offer) / 100.0,
            min(turns_since_last_concession, max_turns) / max_turns,
        ],
        dtype=np.float32,
    )

    action, _ = model.predict(obs, deterministic=True)
    action = int(action)

    action_map = {
        0: ("Hold Firm",      "Opponent maintains their position."),
        1: ("Concede Small",  "Opponent moves slightly toward your offer."),
        2: ("Concede Large",  "Opponent makes a significant concession."),
        3: ("Bluff",          "Opponent moves away from your offer — testing your resolve."),
        4: ("Walk Away",      "Opponent walks away from the negotiation."),
    }
    name, desc = action_map[action]
    return {"action_id": action, "action_name": name, "description": desc}


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="ParleyLab — PPO Negotiation Agent Training")
    parser.add_argument(
        "--timesteps",
        type=int,
        default=300_000,
        help="Total training timesteps (default: 300000)",
    )
    parser.add_argument(
        "--save_dir",
        type=str,
        default="models",
        help="Directory to save model checkpoints (default: models)",
    )
    args = parser.parse_args()

    trained_model = train(total_timesteps=args.timesteps, save_dir=args.save_dir)
    log.info(
        "Training complete. Evaluate with: python -m training.eval --model_path %s/best_model",
        args.save_dir,
    )