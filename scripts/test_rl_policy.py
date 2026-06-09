#!/usr/bin/env python3
"""
Smoke test for the real PPO policy via get_strategic_action.

Run from the repo root:
    python scripts/test_rl_policy.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parley_ai import get_strategic_action

# ---------------------------------------------------------------------------
# 5 state vectors designed to exercise different regions of the policy
# ---------------------------------------------------------------------------

TEST_CASES = [
    (
        "Early turn — offers close, little movement",
        [0.78, 0.92, 0.10, 0.02, 0.05, 0.14, 0.10],
    ),
    (
        "Mid turn — own side moving, opponent stalled",
        [0.40, 0.90, 0.50, 0.30, 0.05, 0.50, 0.50],
    ),
    (
        "Late turn — large gap, both sides conceding",
        [0.50, 0.85, 0.80, 0.20, 0.30, 0.35, 0.70],
    ),
    (
        "Near deal — gap tiny, high turn count",
        [0.70, 0.72, 0.90, 0.10, 0.40, 0.02, 0.30],
    ),
    (
        "Early, far apart — opponent hasn't moved",
        [0.30, 0.95, 0.20, 0.00, 0.50, 0.65, 0.00],
    ),
]

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

print()
print("═" * 70)
print("  StrategyPolicy — deterministic PPO predictions")
print("═" * 70)

seen_actions: set[int] = set()

for label, vec in TEST_CASES:
    result = get_strategic_action(vec)
    seen_actions.add(result["action_id"])
    print(f"\n  [{label}]")
    print(f"    state   : {vec}")
    print(f"    action  : {result['action_id']} — {result['action_name']}")
    print(f"    meaning : {result['description']}")

print()
print("─" * 70)
print(f"  Unique actions seen: {sorted(seen_actions)}  "
      f"({len(seen_actions)} of 5 possible)")
print("─" * 70)

if len(seen_actions) < 2:
    print("  WARNING: only one action returned across all states — check model.")
    sys.exit(1)

print("  OK — diverse predictions confirmed.\n")
