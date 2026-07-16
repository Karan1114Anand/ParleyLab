"""
training/eval.py — PPO Policy Evaluation Script
================================================

Runs deterministic rollout episodes against the ``NegotiationEnv`` heuristic
opponent and reports aggregate performance metrics.

Usage (standalone)::

    python -m training.eval --model_path models/best_model --episodes 200

Metrics reported:
  - ZOPA Agreement Rate   : fraction of episodes that closed a deal
  - Mean Utility Capture  : average normalised surplus over BATNA on closed deals
  - Impasse Rate          : fraction of episodes that timed out
  - Walk-Away Rate        : fraction of episodes where agent chose action 4
  - Mean Episode Reward   : raw reward signal averaged across all episodes
  - Mean Decision Latency : wall-clock inference time per PPO forward pass
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from training.env import NegotiationEnv

log = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate(
    model_path: str | Path = "models/best_model",
    n_episodes: int = 100,
    max_turns: int = 10,
    agent_is_seller: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Run ``n_episodes`` deterministic rollouts and collect performance metrics.

    The PPO policy is loaded in ``deterministic=True`` mode, meaning the
    greedy action (argmax over the policy head) is taken at every step —
    no sampling noise is introduced during evaluation.

    Args:
        model_path: Path to the Stable-Baselines3 ``.zip`` checkpoint.
            Omit the ``.zip`` extension; SB3 appends it automatically.
        n_episodes: Number of evaluation episodes.
        max_turns: Maximum turns per episode (must match training config).
        agent_is_seller: Set True to evaluate on the seller-side perspective.
        verbose: When True, print a formatted summary table to stdout.

    Returns:
        A dict containing:

        - ``deal_rate``      (float): Fraction of episodes with a closed deal.
        - ``impasse_rate``   (float): Fraction that timed out.
        - ``walkaway_rate``  (float): Fraction where agent walked away.
        - ``mean_utility``   (float): Mean normalised utility on closed deals.
        - ``mean_reward``    (float): Mean total episode reward.
        - ``mean_latency_ms`` (float): Mean PPO inference latency in ms.
        - ``n_episodes``     (int):  Number of rollout episodes.

    Raises:
        ImportError: If ``stable-baselines3`` is not installed.
        FileNotFoundError: If the model checkpoint does not exist.
    """
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise ImportError(
            "stable-baselines3 is required. Install: pip install stable-baselines3"
        ) from exc

    model_path = Path(model_path)
    log.info("Loading model from '%s' for evaluation (%d episodes).", model_path, n_episodes)

    model = PPO.load(str(model_path), device="cpu")
    env   = NegotiationEnv(max_turns=max_turns, agent_is_seller=agent_is_seller)

    outcomes:      dict[str, int]  = {"deal_closed": 0, "agent_walked_away": 0, "timeout": 0}
    utilities:     list[float]     = []
    total_rewards: list[float]     = []
    latencies_ms:  list[float]     = []

    for ep in range(n_episodes):
        obs, _  = env.reset()
        done    = False
        ep_reward = 0.0

        while not done:
            t0 = time.perf_counter()
            action, _ = model.predict(obs, deterministic=True)
            latencies_ms.append((time.perf_counter() - t0) * 1000)

            obs, reward, done, _, info = env.step(int(action))
            ep_reward += reward

        total_rewards.append(ep_reward)
        outcome = info.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

        if info.get("deal_value") is not None and outcome == "deal_closed":
            deal   = float(info["deal_value"])
            batna  = env.agent_batna
            # Normalised utility: 0 = at BATNA, 1 = at ideal target
            utility = (
                (batna - deal) / 100.0 if not agent_is_seller
                else (deal - batna) / 100.0
            )
            utilities.append(max(0.0, utility))

    n = n_episodes
    results = {
        "deal_rate":       outcomes["deal_closed"] / n,
        "impasse_rate":    outcomes.get("timeout", 0) / n,
        "walkaway_rate":   outcomes.get("agent_walked_away", 0) / n,
        "mean_utility":    float(np.mean(utilities)) if utilities else 0.0,
        "mean_reward":     float(np.mean(total_rewards)),
        "mean_latency_ms": float(np.mean(latencies_ms)) if latencies_ms else 0.0,
        "n_episodes":      n,
    }

    if verbose:
        _print_report(results, outcomes, n)

    return results


# ── Formatting ─────────────────────────────────────────────────────────────────

def _print_report(results: dict, outcomes: dict, n: int) -> None:
    """Print a formatted evaluation summary."""
    sep = "=" * 55
    log.info(sep)
    log.info("  PPO Policy Evaluation  —  %d episodes", n)
    log.info(sep)
    log.info("  ZOPA Agreement Rate  : %5.1f%%", results["deal_rate"] * 100)
    log.info("  Impasse Rate         : %5.1f%%", results["impasse_rate"] * 100)
    log.info("  Walk-Away Rate       : %5.1f%%", results["walkaway_rate"] * 100)
    log.info("  Mean Utility Capture : %5.1f%%", results["mean_utility"] * 100)
    log.info("  Mean Episode Reward  : %7.2f",   results["mean_reward"])
    log.info("  Mean Decision Latency: %7.2f ms", results["mean_latency_ms"])
    log.info("  Deals / Impasses / Walkaway: %d / %d / %d",
             outcomes["deal_closed"],
             outcomes.get("timeout", 0),
             outcomes.get("agent_walked_away", 0))
    log.info(sep)


# ── Greedy baseline (for benchmark comparison) ─────────────────────────────────

def evaluate_greedy_baseline(
    n_episodes: int = 100,
    max_turns: int = 10,
    agent_is_seller: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Evaluate a greedy heuristic agent (always Concede Small) as a baseline.

    The greedy policy always takes action 1 (Concede Small — move 5% toward
    opponent). This represents a naive monotone concession strategy with no
    strategic awareness.

    Args:
        n_episodes: Number of rollout episodes.
        max_turns: Maximum turns per episode.
        agent_is_seller: Perspective flag, same as ``evaluate()``.
        verbose: When True, print a formatted summary.

    Returns:
        Same dict schema as ``evaluate()``.
    """
    env = NegotiationEnv(max_turns=max_turns, agent_is_seller=agent_is_seller)

    outcomes:      dict[str, int]  = {"deal_closed": 0, "agent_walked_away": 0, "timeout": 0}
    utilities:     list[float]     = []
    total_rewards: list[float]     = []

    for _ in range(n_episodes):
        obs, _    = env.reset()
        done      = False
        ep_reward = 0.0

        while not done:
            # Greedy policy: always concede small (action = 1)
            obs, reward, done, _, info = env.step(1)
            ep_reward += reward

        total_rewards.append(ep_reward)
        outcome = info.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

        if info.get("deal_value") is not None and outcome == "deal_closed":
            deal    = float(info["deal_value"])
            batna   = env.agent_batna
            utility = (
                (batna - deal) / 100.0 if not agent_is_seller
                else (deal - batna) / 100.0
            )
            utilities.append(max(0.0, utility))

    n = n_episodes
    results = {
        "deal_rate":       outcomes["deal_closed"] / n,
        "impasse_rate":    outcomes.get("timeout", 0) / n,
        "walkaway_rate":   outcomes.get("agent_walked_away", 0) / n,
        "mean_utility":    float(np.mean(utilities)) if utilities else 0.0,
        "mean_reward":     float(np.mean(total_rewards)),
        "mean_latency_ms": 0.0,   # no model inference
        "n_episodes":      n,
    }

    if verbose:
        log.info("--- Greedy Baseline Results ---")
        _print_report(results, outcomes, n)

    return results


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Evaluate a trained PPO negotiation agent."
    )
    parser.add_argument(
        "--model_path",
        type=str,
        default="models/best_model",
        help="Path to SB3 .zip model (omit extension). Default: models/best_model",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=100,
        help="Number of evaluation episodes. Default: 100",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Also run greedy baseline and show comparison.",
    )
    args = parser.parse_args()

    ppo_results = evaluate(model_path=args.model_path, n_episodes=args.episodes)

    if args.baseline:
        log.info("")
        baseline_results = evaluate_greedy_baseline(n_episodes=args.episodes)
        log.info("")
        log.info("=== Comparison: PPO vs Greedy Baseline ===")
        log.info(
            "Agreement Rate  : PPO %.1f%%  vs  Baseline %.1f%%",
            ppo_results["deal_rate"] * 100, baseline_results["deal_rate"] * 100,
        )
        log.info(
            "Mean Utility    : PPO %.1f%%  vs  Baseline %.1f%%",
            ppo_results["mean_utility"] * 100, baseline_results["mean_utility"] * 100,
        )
        log.info(
            "Impasse Rate    : PPO %.1f%%  vs  Baseline %.1f%%",
            ppo_results["impasse_rate"] * 100, baseline_results["impasse_rate"] * 100,
        )
