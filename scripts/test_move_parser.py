#!/usr/bin/env python3
"""
Integration test for the move parser agent.

Runs 5 example negotiation messages through parse_move and prints the
structured output for each. Ollama must be running.

Run from the repo root:
    python scripts/test_move_parser.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Default to a model that is pulled locally; override via env for production.
os.environ.setdefault("PARLEYLAB_OLLAMA_MODEL_DEFAULT", "phi3:latest")

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

from parley_ai import parse_move

# ---------------------------------------------------------------------------
# Shared prior exchange (used as history for turns 2–5)
# ---------------------------------------------------------------------------

PRIOR = [
    {
        "role":    "opponent",
        "content": "We're thrilled about having you join the team. "
                   "We were thinking around 78K to start.",
    },
    {
        "role":    "user",
        "content": "Thank you — that's a starting point. Let me think about it.",
    },
    {
        "role":    "opponent",
        "content": "Of course, take your time. We're keen to make this work.",
    },
]

# ---------------------------------------------------------------------------
# Test cases  (message, history, description)
# ---------------------------------------------------------------------------

CASES = [
    (
        "I appreciate the offer but I have a competing bid at 85K.",
        PRIOR,
        "competing bid disclosure — no specific counter yet",
    ),
    (
        "I can come down to 92K if you include relocation.",
        PRIOR,
        "conditional counteroffer with bundled demand",
    ),
    (
        "Take it or leave it — that's my final offer at 95K.",
        PRIOR,
        "hard ultimatum / bluff",
    ),
    (
        "I'd really love to make this work, what can you do?",
        PRIOR,
        "collaborative probe, no specific offer",
    ),
    (
        "I'm walking away from this.",
        PRIOR,
        "explicit walk-away",
    ),
]

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

SCHEMA_KEYS = {"primary_move", "offered_value", "signals", "tone"}
VALID_MOVES  = {"opening_anchor", "counteroffer", "concession",
                "bluff", "walk_away", "accept", "signal"}
VALID_TONES  = {"collaborative", "firm", "aggressive", "desperate"}

failures = 0

print()
print("═" * 70)
print("  Move Parser — LLM-powered structured extraction")
print("═" * 70)

for i, (msg, hist, desc) in enumerate(CASES, 1):
    print(f"\n[{i}] {desc}")
    print(f"    input : {msg!r}")

    try:
        result = parse_move(msg, hist)
    except ConnectionError as exc:
        print(f"    \033[31mERROR\033[0m: {exc}")
        failures += 1
        continue
    except Exception as exc:
        print(f"    \033[31mUNEXPECTED ERROR\033[0m ({type(exc).__name__}): {exc}")
        failures += 1
        continue

    print(f"    output: {result}")

    # Structural checks
    ok = True
    if set(result.keys()) != SCHEMA_KEYS:
        print(f"    \033[31m✗\033[0m wrong keys: {set(result.keys())}")
        ok = False
    if result["primary_move"] not in VALID_MOVES:
        print(f"    \033[31m✗\033[0m invalid primary_move: {result['primary_move']!r}")
        ok = False
    if result["offered_value"] is not None and not isinstance(result["offered_value"], (int, float)):
        print(f"    \033[31m✗\033[0m offered_value must be float or None")
        ok = False
    if not isinstance(result["signals"], list):
        print(f"    \033[31m✗\033[0m signals must be a list")
        ok = False
    if result["tone"] not in VALID_TONES:
        print(f"    \033[31m✗\033[0m invalid tone: {result['tone']!r}")
        ok = False

    if ok:
        print(f"    \033[32m✓\033[0m schema valid")
    else:
        failures += 1

print()
print("─" * 70)
if failures == 0:
    print(f"  \033[32mALL PASSED\033[0m — {len(CASES)} cases, schema valid\n")
else:
    print(f"  \033[31m{failures} FAILED\033[0m out of {len(CASES)} cases\n")

sys.exit(0 if failures == 0 else 1)
