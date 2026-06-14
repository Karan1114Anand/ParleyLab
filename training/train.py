"""
Negotiation RL Training Script
================================
Trains a PPO agent to negotiate against a rule-based opponent.
The agent learns WHEN to concede, bluff, hold firm, or walk away.
Language is handled separately by an LLM at runtime.

State space  : [own_offer_norm, opponent_offer_norm, turn_norm,
                own_concession_rate, opponent_concession_rate,
                gap_norm, turns_since_last_concession_norm]
Action space : Discrete(5)
               0 = Hold Firm      (no change to offer)
               1 = Concede Small  (move 5% toward opponent)
               2 = Concede Large  (move 15% toward opponent)
               3 = Bluff          (move away from opponent by 5%)
               4 = Walk Away      (terminate, take BATNA)

Reward       : Shaped at each step + terminal reward on deal close
"""

import os
import json
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor


# ── Negotiation Environment ───────────────────────────────────────────────────

class NegotiationEnv(gym.Env):
    """
    Single-issue negotiation environment (e.g. salary, price).

    Both sides have:
      - A target value  (what they want ideally)
      - A BATNA value   (walk-away point)

    The agent plays the BUYER side (minimise deal value).
    The opponent plays the SELLER side (maximise deal value).
    Roles can be flipped by setting agent_is_seller=True.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(self, max_turns: int = 10, agent_is_seller: bool = False, difficulty: float = 0.5):
        super().__init__()

        self.max_turns = max_turns
        self.agent_is_seller = agent_is_seller
        self.difficulty = max(0.0, min(1.0, difficulty))

        # Action space: 5 discrete strategic moves
        self.action_space = spaces.Discrete(5)

        # Observation space: 7 normalised floats in [0, 1]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(7,), dtype=np.float32
        )

        # Will be set in reset()
        self.agent_batna        = None
        self.agent_target       = None
        self.opponent_batna     = None
        self.opponent_target    = None
        self.agent_offer        = None
        self.opponent_offer     = None
        self.turn               = None
        self.history            = None
        self.done               = False

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _sample_scenario(self):
        """
        Randomly sample a negotiation scenario each episode.
        All values normalised to [0, 100] for simplicity.
        The ZOPA (zone of possible agreement) always exists.
        """
        # Seller wants high, buyer wants low
        seller_batna   = np.random.uniform(40, 60)   # seller walks if below this
        seller_target  = seller_batna + np.random.uniform(20, 40)
        buyer_batna    = seller_batna + np.random.uniform(5, 25)  # ZOPA guaranteed
        buyer_target   = seller_batna - np.random.uniform(5, 15)

        if self.agent_is_seller:
            self.agent_batna    = seller_batna
            self.agent_target   = seller_target
            self.opponent_batna = buyer_batna
            self.opponent_target= buyer_target
        else:
            self.agent_batna    = buyer_batna
            self.agent_target   = buyer_target
            self.opponent_batna = seller_batna
            self.opponent_target= seller_target

        # Opening offers: both sides start anchored near their target
        if self.agent_is_seller:
            self.agent_offer    = np.clip(self.agent_target + np.random.uniform(0, 10), 0, 100)
            self.opponent_offer = np.clip(self.opponent_target - np.random.uniform(0, 10), 0, 100)
        else:
            self.agent_offer    = np.clip(self.agent_target - np.random.uniform(0, 10), 0, 100)
            self.opponent_offer = np.clip(self.opponent_target + np.random.uniform(0, 10), 0, 100)

    def _get_obs(self) -> np.ndarray:
        """Build normalised observation vector."""
        own_offer_norm       = self.agent_offer / 100.0
        opp_offer_norm       = self.opponent_offer / 100.0
        turn_norm            = self.turn / self.max_turns

        # Concession rates (how much each side has moved from their opening)
        own_opening  = self.history["agent_offers"][0]   if self.history["agent_offers"]    else self.agent_offer
        opp_opening  = self.history["opponent_offers"][0] if self.history["opponent_offers"] else self.opponent_offer

        own_concession  = abs(self.agent_offer - own_opening) / 100.0
        opp_concession  = abs(self.opponent_offer - opp_opening) / 100.0

        gap_norm = abs(self.agent_offer - self.opponent_offer) / 100.0

        # Turns since agent last conceded
        if len(self.history["agent_offers"]) >= 2:
            last_move = next(
                (i for i, (a, b) in enumerate(zip(
                    reversed(self.history["agent_offers"]),
                    reversed(self.history["agent_offers"][1:])
                )) if a != b),
                self.turn
            )
            turns_since_concession = min(last_move, self.max_turns) / self.max_turns
        else:
            turns_since_concession = 0.0

        return np.array([
            own_offer_norm,
            opp_offer_norm,
            turn_norm,
            own_concession,
            opp_concession,
            gap_norm,
            turns_since_concession,
        ], dtype=np.float32)

    def _opponent_move(self):
        """
        Rule-based opponent strategy.
        Concedes gradually, becomes more flexible near deadline.
        Occasionally bluffs early in the negotiation.
        """
        turns_left = self.max_turns - self.turn
        gap        = abs(self.agent_offer - self.opponent_offer)

        # Deadline pressure: concede more as turns run out
        deadline_factor = 1 - (turns_left / self.max_turns)

        # Random bluff in first 3 turns (20% chance)
        if self.turn < 3 and np.random.random() < 0.20:
            if self.agent_is_seller:
                self.opponent_offer = np.clip(self.opponent_offer - 3, 0, 100)
            else:
                self.opponent_offer = np.clip(self.opponent_offer + 3, 0, 100)
            return

        # Base concession: scale range by difficulty
        # difficulty=0.0 → uniform(1, 6), difficulty=1.0 → uniform(0.5, 1)
        low  = 1.0 - 0.5 * self.difficulty   # 1.0 → 0.5
        high = 6.0 - 5.0 * self.difficulty   # 6.0 → 1.0
        concession_size = np.random.uniform(low, high) * (1 + deadline_factor)

        if gap < 3:
            # Close enough — split the difference
            self.opponent_offer = (self.opponent_offer + self.agent_offer) / 2
        elif self.agent_is_seller:
            self.opponent_offer = np.clip(
                self.opponent_offer + concession_size, 0, self.opponent_batna
            )
        else:
            self.opponent_offer = np.clip(
                self.opponent_offer - concession_size, self.opponent_batna, 100
            )

    def _apply_agent_action(self, action: int):
        """Translate discrete action into offer movement."""
        if self.agent_is_seller:
            # Seller: higher offer = better for agent
            moves = {
                0: 0,      # Hold Firm
                1: -5,     # Concede Small (lower ask)
                2: -15,    # Concede Large
                3: +5,     # Bluff (raise ask)
                4: None,   # Walk Away
            }
        else:
            # Buyer: lower offer = better for agent
            moves = {
                0: 0,
                1: +5,     # Concede Small (raise bid)
                2: +15,    # Concede Large
                3: -5,     # Bluff (lower bid)
                4: None,   # Walk Away
            }

        if action == 4:
            return False  # signal walk away

        delta = moves[action]
        self.agent_offer = np.clip(self.agent_offer + delta, 0, 100)
        return True

    def _compute_reward(self, deal_value: float = None, walked_away: bool = False,
                        timed_out: bool = False) -> float:
        """
        Reward shaping (rebalanced):
        - Closing a deal yields a large positive reward (surplus * 100 + completion bonus)
        - Walking away is heavily penalized to force the agent to actually negotiate
        - Timeouts are mildly negative (better than walking away with no attempt)
        - Step penalty is tiny to allow exploration of multi-turn strategies
        """
        step_penalty = -0.1

        if walked_away:
            return -15.0   # walking away is bad — agent must try to close

        if timed_out:
            return -3.0    # mild — at least it tried

        if deal_value is not None:
            if self.agent_is_seller:
                surplus = (deal_value - self.agent_batna) / 100.0
            else:
                surplus = (self.agent_batna - deal_value) / 100.0
            # Big reward for closing + scaled surplus
            return 10.0 + surplus * 100

        return step_penalty  # mid-negotiation step

    def _is_deal_possible(self) -> bool:
        """Check if current offers overlap (deal can close)."""
        if self.agent_is_seller:
            return self.agent_offer <= self.opponent_offer
        else:
            return self.agent_offer >= self.opponent_offer

    # ── Gym interface ─────────────────────────────────────────────────────────

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._sample_scenario()
        self.turn  = 0
        self.done  = False
        self.history = {"agent_offers": [], "opponent_offers": [], "actions": []}
        self.history["agent_offers"].append(self.agent_offer)
        self.history["opponent_offers"].append(self.opponent_offer)
        return self._get_obs(), {}

    def step(self, action: int):
        assert not self.done, "Episode is done. Call reset()."

        self.turn += 1
        info = {}

        # Agent acts
        continued = self._apply_agent_action(action)
        self.history["agent_offers"].append(self.agent_offer)
        self.history["actions"].append(action)

        # Walk away
        if not continued:
            reward = self._compute_reward(walked_away=True)
            info = {"outcome": "agent_walked_away", "deal_value": self.agent_batna}
            return self._get_obs(), reward, True, False, info

        # Check if deal closes
        if self._is_deal_possible():
            deal_value = (self.agent_offer + self.opponent_offer) / 2
            reward = self._compute_reward(deal_value=deal_value)
            info = {"outcome": "deal_closed", "deal_value": deal_value}
            return self._get_obs(), reward, True, False, info

        # Opponent acts
        self._opponent_move()
        self.history["opponent_offers"].append(self.opponent_offer)

        # Check again after opponent move
        if self._is_deal_possible():
            deal_value = (self.agent_offer + self.opponent_offer) / 2
            reward = self._compute_reward(deal_value=deal_value)
            info = {"outcome": "deal_closed", "deal_value": deal_value}
            return self._get_obs(), reward, True, False, info

        # Timeout
        if self.turn >= self.max_turns:
            reward = self._compute_reward(timed_out=True)
            info = {"outcome": "timeout", "deal_value": None}
            return self._get_obs(), reward, True, False, info

        # Continue negotiating
        reward = self._compute_reward()
        return self._get_obs(), reward, False, False, info

    def render(self, mode="human"):
        print(
            f"Turn {self.turn:02d} | "
            f"Agent offer: {self.agent_offer:5.1f} | "
            f"Opponent offer: {self.opponent_offer:5.1f} | "
            f"Gap: {abs(self.agent_offer - self.opponent_offer):5.1f}"
        )


# ── Training ─────────────────────────────────────────────────────────────────

def train(
    total_timesteps: int = 300_000,
    save_dir: str = "models",
    log_dir: str = "logs",
):
    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(log_dir,  exist_ok=True)

    from stable_baselines3.common.vec_env import SubprocVecEnv

    difficulty_levels = [0.1, 0.3, 0.5, 0.7, 0.9]

    def make_env(difficulty):
        def _init():
            return Monitor(NegotiationEnv(max_turns=10, agent_is_seller=False, difficulty=difficulty))
        return _init

    env_buyer = SubprocVecEnv([make_env(d) for d in difficulty_levels])
    eval_env  = Monitor(NegotiationEnv(max_turns=10, agent_is_seller=False, difficulty=0.5))

    print("Checking environment validity...")
    check_env(NegotiationEnv(max_turns=10, agent_is_seller=False, difficulty=0.5), warn=True)
    print("Environment check passed.\n")

    # Callbacks
    eval_cb = EvalCallback(
        eval_env,
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

    # Entropy annealing callback: start exploratory (0.05), decay to greedy (0.005)
    # SB3's ent_coef doesn't accept schedules, so we update it manually via callback.
    from stable_baselines3.common.callbacks import BaseCallback

    class EntropyAnnealCallback(BaseCallback):
        def __init__(self, start: float = 0.05, end: float = 0.005, verbose: int = 0):
            super().__init__(verbose)
            self.start = start
            self.end   = end

        def _on_step(self) -> bool:
            progress = self.num_timesteps / total_timesteps
            new_ent  = self.start + (self.end - self.start) * progress
            self.model.ent_coef = new_ent
            return True

    entropy_cb = EntropyAnnealCallback(start=0.05, end=0.005)

    # PPO model
    model = PPO(
        policy="MlpPolicy",
        env=env_buyer,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=320,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.05,       # initial value; callback decays it over training
        vf_coef=0.5,
        max_grad_norm=0.5,
        verbose=1,
        # tensorboard_log=log_dir,  # install tensorboard to enable
    )

    print(f"Training PPO agent for {total_timesteps:,} timesteps...")
    model.learn(
        total_timesteps=total_timesteps,
        callback=[eval_cb, checkpoint_cb, entropy_cb],
        progress_bar=True,
    )

    # Save final model
    final_path = os.path.join(save_dir, "negotiation_agent_final")
    model.save(final_path)
    print(f"\nFinal model saved to: {final_path}.zip")

    # Save metadata alongside the model
    metadata = {
        "action_meanings": {
            "0": "Hold Firm",
            "1": "Concede Small (5%)",
            "2": "Concede Large (15%)",
            "3": "Bluff (move away 5%)",
            "4": "Walk Away",
        },
        "observation_schema": [
            "own_offer_norm",
            "opponent_offer_norm",
            "turn_norm",
            "own_concession_rate",
            "opponent_concession_rate",
            "gap_norm",
            "turns_since_last_concession_norm",
        ],
        "total_timesteps": total_timesteps,
        "agent_role": "buyer",
    }
    with open(os.path.join(save_dir, "model_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print("Metadata saved to: models/model_metadata.json")

    return model


# ── Inference helper (used by the main app at runtime) ───────────────────────

def load_agent(model_path: str = "models/best_model"):
    """Load trained agent for inference in the main negotiation app."""
    return PPO.load(model_path)


def get_strategy_action(
    model,
    own_offer: float,
    opponent_offer: float,
    turn: int,
    max_turns: int,
    own_concession_rate: float,
    opponent_concession_rate: float,
    turns_since_last_concession: int,
) -> dict:
    """
    Given the current negotiation state, return the agent's strategic action.
    Called by the main app every time the opponent needs to decide its next move.

    Returns:
        {
            "action_id": int,
            "action_name": str,
            "description": str,
        }
    """
    obs = np.array([
        own_offer / 100.0,
        opponent_offer / 100.0,
        turn / max_turns,
        own_concession_rate,
        opponent_concession_rate,
        abs(own_offer - opponent_offer) / 100.0,
        min(turns_since_last_concession, max_turns) / max_turns,
    ], dtype=np.float32)

    action, _ = model.predict(obs, deterministic=True)
    action = int(action)

    action_map = {
        0: ("Hold Firm",       "Opponent maintains their position."),
        1: ("Concede Small",   "Opponent moves slightly toward your offer."),
        2: ("Concede Large",   "Opponent makes a significant concession."),
        3: ("Bluff",           "Opponent moves away from your offer — testing your resolve."),
        4: ("Walk Away",       "Opponent walks away from the negotiation."),
    }

    name, desc = action_map[action]
    return {"action_id": action, "action_name": name, "description": desc}


# ── Quick evaluation ──────────────────────────────────────────────────────────

def evaluate(model_path: str = "models/best_model", n_episodes: int = 100):
    """Run evaluation episodes and print summary statistics."""
    model = load_agent(model_path)
    env   = NegotiationEnv(max_turns=10, agent_is_seller=False, difficulty=0.5)

    outcomes      = {"deal_closed": 0, "agent_walked_away": 0, "timeout": 0}
    deal_values   = []
    total_rewards = []

    for ep in range(n_episodes):
        obs, _ = env.reset()
        done   = False
        ep_reward = 0.0

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, _, info = env.step(int(action))
            ep_reward += reward

        total_rewards.append(ep_reward)
        outcome = info.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if info.get("deal_value") is not None:
            deal_values.append(info["deal_value"])

    print(f"\n{'='*45}")
    print(f"  Evaluation over {n_episodes} episodes")
    print(f"{'='*45}")
    print(f"  Deals closed      : {outcomes['deal_closed']:>4d} ({outcomes['deal_closed']/n_episodes*100:.1f}%)")
    print(f"  Agent walked away : {outcomes.get('agent_walked_away',0):>4d} ({outcomes.get('agent_walked_away',0)/n_episodes*100:.1f}%)")
    print(f"  Timed out         : {outcomes['timeout']:>4d} ({outcomes['timeout']/n_episodes*100:.1f}%)")
    if deal_values:
        print(f"  Avg deal value    : {np.mean(deal_values):>7.2f}")
        print(f"  Best deal value   : {np.min(deal_values):>7.2f}  (buyer wants low)")
    print(f"  Avg episode reward: {np.mean(total_rewards):>7.2f}")
    print(f"{'='*45}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Negotiation RL Agent")
    parser.add_argument("--mode",       type=str, default="train",
                        choices=["train", "eval"],
                        help="train: train the agent | eval: evaluate a saved model")
    parser.add_argument("--timesteps",  type=int, default=300_000,
                        help="Total training timesteps (default: 300000)")
    parser.add_argument("--model_path", type=str, default="models/best_model",
                        help="Path to saved model for eval mode")
    parser.add_argument("--episodes",   type=int, default=100,
                        help="Number of eval episodes")
    args = parser.parse_args()

    if args.mode == "train":
        train(total_timesteps=args.timesteps)
        print("\nTraining complete. Run with --mode eval to evaluate.")
    elif args.mode == "eval":
        evaluate(model_path=args.model_path, n_episodes=args.episodes)