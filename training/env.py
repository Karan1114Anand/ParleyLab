"""
training/env.py — Farama-Gymnasium Custom Negotiation Environment
=================================================================

Implements ``NegotiationEnv``, the single-issue negotiation environment
used to train the PPO strategic policy.

Design Contract
---------------
State space  : ``gymnasium.spaces.Box(low=0, high=1, shape=(7,), dtype=float32)``
               ┌──────────────────────────────────────────────────────────────────┐
               │ Index │ Feature                           │ Normalization         │
               ├───────┼───────────────────────────────────┼───────────────────────┤
               │   0   │ own_offer_norm                    │ offer / 100           │
               │   1   │ opponent_offer_norm               │ offer / 100           │
               │   2   │ turn_norm                         │ turn / max_turns      │
               │   3   │ own_concession_rate               │ |Δown| / 100          │
               │   4   │ opponent_concession_rate          │ |Δopp| / 100          │
               │   5   │ gap_norm                          │ |own - opp| / 100     │
               │   6   │ turns_since_last_concession_norm  │ turns_idle / max_turns│
               └──────────────────────────────────────────────────────────────────┘

Action space : ``gymnasium.spaces.Discrete(5)``
               0 = Hold Firm      — no offer change
               1 = Concede Small  — move 5% toward opponent
               2 = Concede Large  — move 15% toward opponent
               3 = Bluff          — move 5% away from opponent
               4 = Walk Away      — terminate, accept BATNA

Reward shaping:
  - Deal closed : +10.0 base  +  (surplus / 100) × 100   (surplus over BATNA)
  - Walk away   : -15.0       (strongly discourages premature exit)
  - Timeout     :  -3.0       (mild; indicates unsuccessful convergence)
  - Step        :  -0.1       (exploration tax per turn)

The ZOPA (Zone Of Possible Agreement) is always guaranteed at episode start
by construction of ``_sample_scenario()`` — the buyer's BATNA always exceeds
the seller's BATNA, ensuring a non-empty settlement range exists.
"""

from __future__ import annotations

import logging

import numpy as np
import gymnasium as gym
from gymnasium import spaces

log = logging.getLogger(__name__)


class NegotiationEnv(gym.Env):
    """
    Single-issue negotiation environment (salary, price, equity, etc.).

    Both sides carry:
      - A **target** value (aspiration — ideal outcome).
      - A **BATNA** value (Best Alternative To Negotiated Agreement —
        the walk-away point below/above which the party refuses to deal).

    The agent plays the **buyer** side (minimise deal value) by default.
    Set ``agent_is_seller=True`` to flip roles and maximise deal value.

    A ZOPA is guaranteed at every episode reset, so a deal is always
    theoretically achievable — the agent must learn to close it efficiently.

    Attributes:
        max_turns: Maximum number of alternating offer rounds per episode.
        agent_is_seller: When True, agent perspective is the high-offer side.
        action_space: ``Discrete(5)`` — five strategic moves.
        observation_space: ``Box(0, 1, shape=(7,))`` — normalised state vector.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(self, max_turns: int = 10, agent_is_seller: bool = False) -> None:
        super().__init__()

        self.max_turns = max_turns
        self.agent_is_seller = agent_is_seller

        # Action space: 5 discrete strategic moves
        self.action_space = spaces.Discrete(5)

        # Observation space: 7 normalised floats in [0, 1]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(7,), dtype=np.float32
        )

        # Episode-level state — initialised in reset()
        self.agent_batna: float | None     = None
        self.agent_target: float | None    = None
        self.opponent_batna: float | None  = None
        self.opponent_target: float | None = None
        self.agent_offer: float | None     = None
        self.opponent_offer: float | None  = None
        self.turn: int | None              = None
        self.history: dict | None          = None
        self.done: bool                    = False

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _sample_scenario(self) -> None:
        """
        Randomly sample a negotiation scenario at episode start.

        All values are normalised to [0, 100] to keep the observation
        space bounded. The ZOPA is guaranteed by setting buyer_batna strictly
        above seller_batna, ensuring at least one settlement point exists.

        Distribution:
          - seller_batna  ~ Uniform(40, 60)   — seller walks below this
          - seller_target = seller_batna + Uniform(20, 40)
          - buyer_batna   = seller_batna + Uniform(5, 25)   ← guarantees ZOPA
          - buyer_target  = seller_batna - Uniform(5, 15)   ← buyer wants low
        """
        seller_batna   = np.random.uniform(40, 60)
        seller_target  = seller_batna + np.random.uniform(20, 40)
        buyer_batna    = seller_batna + np.random.uniform(5, 25)   # ZOPA guaranteed
        buyer_target   = seller_batna - np.random.uniform(5, 15)

        if self.agent_is_seller:
            self.agent_batna     = seller_batna
            self.agent_target    = seller_target
            self.opponent_batna  = buyer_batna
            self.opponent_target = buyer_target
        else:
            self.agent_batna     = buyer_batna
            self.agent_target    = buyer_target
            self.opponent_batna  = seller_batna
            self.opponent_target = seller_target

        # Opening offers: both sides anchor near their aspiration target
        if self.agent_is_seller:
            self.agent_offer    = np.clip(self.agent_target + np.random.uniform(0, 10), 0, 100)
            self.opponent_offer = np.clip(self.opponent_target - np.random.uniform(0, 10), 0, 100)
        else:
            self.agent_offer    = np.clip(self.agent_target - np.random.uniform(0, 10), 0, 100)
            self.opponent_offer = np.clip(self.opponent_target + np.random.uniform(0, 10), 0, 100)

    def _get_obs(self) -> np.ndarray:
        """
        Build the 7-dimensional normalised state vector.

        All features are clipped to [0.0, 1.0] to ensure the observation
        stays within the registered Box bounds regardless of edge cases.

        Returns:
            A ``float32`` ndarray of shape ``(7,)``.
        """
        own_offer_norm      = self.agent_offer / 100.0
        opp_offer_norm      = self.opponent_offer / 100.0
        turn_norm           = self.turn / self.max_turns

        # Concession rates: cumulative movement from opening position
        own_opening = (
            self.history["agent_offers"][0]
            if self.history["agent_offers"] else self.agent_offer
        )
        opp_opening = (
            self.history["opponent_offers"][0]
            if self.history["opponent_offers"] else self.opponent_offer
        )
        own_concession = abs(self.agent_offer - own_opening) / 100.0
        opp_concession = abs(self.opponent_offer - opp_opening) / 100.0

        gap_norm = abs(self.agent_offer - self.opponent_offer) / 100.0

        # Turns since agent last moved its offer (stalling signal)
        if len(self.history["agent_offers"]) >= 2:
            last_move = next(
                (
                    i for i, (a, b) in enumerate(
                        zip(
                            reversed(self.history["agent_offers"]),
                            reversed(self.history["agent_offers"][1:]),
                        )
                    )
                    if a != b
                ),
                self.turn,
            )
            turns_since_concession = min(last_move, self.max_turns) / self.max_turns
        else:
            turns_since_concession = 0.0

        obs = np.array(
            [
                own_offer_norm,
                opp_offer_norm,
                turn_norm,
                own_concession,
                opp_concession,
                gap_norm,
                turns_since_concession,
            ],
            dtype=np.float32,
        )
        return np.clip(obs, 0.0, 1.0)

    def _opponent_move(self) -> None:
        """
        Rule-based heuristic opponent.

        Strategy:
          - Concedes gradually toward agent's offer.
          - Deadline pressure amplifies concession size as ``turn → max_turns``.
          - Early-game bluffs (turn < 3, 20% chance) to test agent resolve.
          - Refuses to concede beyond its own BATNA.
        """
        turns_left      = self.max_turns - self.turn
        gap             = abs(self.agent_offer - self.opponent_offer)
        deadline_factor = 1 - (turns_left / self.max_turns)

        # Probabilistic early-game bluff
        if self.turn < 3 and np.random.random() < 0.20:
            if self.agent_is_seller:
                self.opponent_offer = np.clip(self.opponent_offer - 3, 0, 100)
            else:
                self.opponent_offer = np.clip(self.opponent_offer + 3, 0, 100)
            return

        # Deadline-weighted concession step
        concession_size = np.random.uniform(1, 3) * (1 + deadline_factor)

        if gap < 3:
            # Offers within 3 units → split the difference to close
            self.opponent_offer = (self.opponent_offer + self.agent_offer) / 2
        elif self.agent_is_seller:
            self.opponent_offer = np.clip(
                self.opponent_offer + concession_size, 0, self.opponent_batna
            )
        else:
            self.opponent_offer = np.clip(
                self.opponent_offer - concession_size, self.opponent_batna, 100
            )

    def _apply_agent_action(self, action: int) -> bool:
        """
        Translate a discrete action integer into an offer movement.

        Args:
            action: Integer in {0, 1, 2, 3, 4}.

        Returns:
            True if negotiation continues; False signals walk-away (action 4).
        """
        if self.agent_is_seller:
            # Seller perspective: higher offer = better for agent
            moves = {0: 0, 1: -5, 2: -15, 3: +5, 4: None}
        else:
            # Buyer perspective: lower offer = better for agent
            moves = {0: 0, 1: +5, 2: +15, 3: -5, 4: None}

        if action == 4:
            return False  # signal walk-away to caller

        delta = moves[action]
        self.agent_offer = np.clip(self.agent_offer + delta, 0, 100)
        return True

    def _compute_reward(
        self,
        deal_value: float | None = None,
        walked_away: bool = False,
        timed_out: bool = False,
    ) -> float:
        """
        Multi-objective reward function.

        The reward is intentionally asymmetric to force the agent to close
        deals rather than defaulting to walk-away:

          R(deal)  = +10.0  +  surplus × 100
                              ──────────────────────────────────────────
                              surplus = (deal_value − batna) / 100    [buyer]
                              surplus = (deal_value − batna) / 100    [seller, negated]

          R(walk)  = −15.0  ← Concession Penalty for abandoning ZOPA

          R(timeout) = −3.0 ← Impasse Risk penalty (weaker than walk-away)

          R(step)  = −0.1   ← per-turn exploration tax

        Args:
            deal_value: Agreed settlement value when a deal closes.
            walked_away: True when the agent chose action 4.
            timed_out: True when ``turn >= max_turns`` with no deal.

        Returns:
            A scalar reward signal.
        """
        if walked_away:
            return -15.0   # Concession Penalty: agent abandoned viable ZOPA

        if timed_out:
            return -3.0    # Impasse Risk: failed to converge within deadline

        if deal_value is not None:
            # Agreement Bonus: reward scales with how much surplus the agent captured
            if self.agent_is_seller:
                surplus = (deal_value - self.agent_batna) / 100.0
            else:
                surplus = (self.agent_batna - deal_value) / 100.0
            return 10.0 + surplus * 100.0

        return -0.1  # per-step exploration tax

    def _is_deal_possible(self) -> bool:
        """True when current offers overlap — deal can close this turn."""
        if self.agent_is_seller:
            return self.agent_offer <= self.opponent_offer
        else:
            return self.agent_offer >= self.opponent_offer

    # ── Farama-Gymnasium interface ─────────────────────────────────────────────

    def reset(self, seed: int | None = None, options: dict | None = None):
        """
        Reset the environment and sample a new negotiation scenario.

        Args:
            seed: Optional RNG seed for reproducibility.
            options: Unused; retained for Gymnasium API compliance.

        Returns:
            Tuple of ``(observation, info)`` matching the Gymnasium v26+ API.
        """
        super().reset(seed=seed)
        self._sample_scenario()
        self.turn = 0
        self.done = False
        self.history = {
            "agent_offers":    [self.agent_offer],
            "opponent_offers": [self.opponent_offer],
            "actions":         [],
        }
        log.debug(
            "NegotiationEnv reset | agent_batna=%.1f opponent_batna=%.1f "
            "agent_offer=%.1f opponent_offer=%.1f",
            self.agent_batna, self.opponent_batna,
            self.agent_offer, self.opponent_offer,
        )
        return self._get_obs(), {}

    def step(self, action: int):
        """
        Advance the environment by one agent turn.

        The execution order is:
          1. Agent applies ``action`` (offer update or walk-away).
          2. Check for immediate deal closure.
          3. Heuristic opponent responds.
          4. Check for deal closure after opponent move.
          5. Check for timeout.

        Args:
            action: Integer in ``{0, 1, 2, 3, 4}``.

        Returns:
            ``(obs, reward, terminated, truncated, info)`` — Gymnasium v26+ format.
        """
        assert not self.done, "Episode is done. Call reset() before stepping."

        self.turn += 1
        info: dict = {}

        # Stage 1: Agent acts
        continued = self._apply_agent_action(action)
        self.history["agent_offers"].append(self.agent_offer)
        self.history["actions"].append(action)

        # Stage 2: Walk-away short-circuit
        if not continued:
            reward = self._compute_reward(walked_away=True)
            info   = {"outcome": "agent_walked_away", "deal_value": self.agent_batna}
            self.done = True
            return self._get_obs(), reward, True, False, info

        # Stage 3: Check deal after agent move
        if self._is_deal_possible():
            deal_value = (self.agent_offer + self.opponent_offer) / 2
            reward     = self._compute_reward(deal_value=deal_value)
            info       = {"outcome": "deal_closed", "deal_value": deal_value}
            self.done  = True
            return self._get_obs(), reward, True, False, info

        # Stage 4: Opponent responds
        self._opponent_move()
        self.history["opponent_offers"].append(self.opponent_offer)

        # Stage 5: Check deal after opponent move
        if self._is_deal_possible():
            deal_value = (self.agent_offer + self.opponent_offer) / 2
            reward     = self._compute_reward(deal_value=deal_value)
            info       = {"outcome": "deal_closed", "deal_value": deal_value}
            self.done  = True
            return self._get_obs(), reward, True, False, info

        # Stage 6: Timeout check
        if self.turn >= self.max_turns:
            reward    = self._compute_reward(timed_out=True)
            info      = {"outcome": "timeout", "deal_value": None}
            self.done = True
            return self._get_obs(), reward, True, False, info

        # Continue negotiating
        reward = self._compute_reward()
        return self._get_obs(), reward, False, False, info

    def render(self, mode: str = "human") -> None:
        """Print a single-line summary of the current negotiation state."""
        log.info(
            "Turn %02d | Agent offer: %5.1f | Opponent offer: %5.1f | Gap: %5.1f",
            self.turn,
            self.agent_offer,
            self.opponent_offer,
            abs(self.agent_offer - self.opponent_offer),
        )
