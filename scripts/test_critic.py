#!/usr/bin/env python3
"""
Integration test for the critic agent.

Runs 5 user moves through get_critic_feedback and prints structured output.
Uses the same 5 messages as test_move_parser.py for consistency; parsed_move
dicts are pre-computed to avoid a second Ollama call.

Run from the repo root:
    python scripts/test_critic.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("PARLEYLAB_LLM_PROVIDER", "ollama")
os.environ.setdefault("PARLEYLAB_OLLAMA_MODEL_DEFAULT", "phi3:latest")

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

from parley_ai import get_critic_feedback

# ---------------------------------------------------------------------------
# Shared prior exchange (gives critic conversation context)
# ---------------------------------------------------------------------------

PRIOR = [
    {
        "role":    "opponent",
        "content": "We're really excited about having you. We were thinking around 78K to start.",
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
# Test cases — same messages as test_move_parser.py
# Pre-computed parsed_user_move dicts (realistic LLM parser output)
# ---------------------------------------------------------------------------

CASES = [
    (
        "I appreciate the offer but I have a competing bid at 85K.",
        {
            "primary_move":  "signal",
            "offered_value": None,
            "signals":       ["competing_bid_disclosure"],
            "tone":          "collaborative",
        },
        PRIOR,
        "competing bid disclosure — should trigger information_disclosure critique",
    ),
    (
        "I can come down to 92K if you include relocation.",
        {
            "primary_move":  "counteroffer",
            "offered_value": 92000.0,
            "signals":       ["bundled_demand"],
            "tone":          "collaborative",
        },
        PRIOR + [
            {"role": "opponent", "content": "We appreciate that. Relocation is possible — could you come down a bit more?"},
        ],
        "conditional counteroffer — bundled demand, concession pacing",
    ),
    (
        "Take it or leave it — that's my final offer at 95K.",
        {
            "primary_move":  "bluff",
            "offered_value": 95000.0,
            "signals":       [],
            "tone":          "aggressive",
        },
        PRIOR + [
            {"role": "opponent", "content": "We can stretch to 88K but that's really our ceiling."},
        ],
        "hard ultimatum — walk_away_credibility or framing",
    ),
    (
        "I'd really love to make this work, what can you do?",
        {
            "primary_move":  "signal",
            "offered_value": None,
            "signals":       ["reciprocity_request"],
            "tone":          "collaborative",
        },
        PRIOR + [
            {"role": "opponent", "content": "We hear you. Is there flexibility on your end?"},
        ],
        "collaborative probe — reciprocity or framing",
    ),
    (
        "I'm walking away from this.",
        {
            "primary_move":  "walk_away",
            "offered_value": None,
            "signals":       [],
            "tone":          "firm",
        },
        PRIOR + [
            {"role": "opponent", "content": "We truly can't go higher than 82K."},
            {"role": "user",     "content": "That's still too far from my expectations."},
            {"role": "opponent", "content": "I understand. I'm afraid that's our final position."},
        ],
        "walk-away — walk_away_credibility",
    ),
]

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

VALID_TAGS = {
    "anchoring", "concession_pacing", "batna_signaling",
    "reciprocity", "information_disclosure", "framing", "walk_away_credibility",
}

failures = 0

print()
print("═" * 70)
print("  Critic Agent — negotiation theory feedback")
print("═" * 70)

for i, (msg, parsed_move, history, desc) in enumerate(CASES, 1):
    # Append current user message to history for full context
    full_history = history + [{"role": "user", "content": msg}]

    print(f"\n[{i}] {desc}")
    print(f"    move  : {msg!r}")
    print(f"    parsed: {parsed_move}")

    try:
        feedback = get_critic_feedback(parsed_move, full_history)
    except ConnectionError as exc:
        print(f"    \033[31mERROR\033[0m: {exc}")
        failures += 1
        continue
    except Exception as exc:
        print(f"    \033[31mUNEXPECTED\033[0m ({type(exc).__name__}): {exc}")
        failures += 1
        continue

    print(f"    strengths  : {feedback.get('strengths')}")
    print(f"    weaknesses : {feedback.get('weaknesses')}")
    print(f"    suggestion : {feedback.get('suggestion')!r}")
    print(f"    concept_tag: {feedback.get('concept_tag')!r}")

    ok = True
    if set(feedback.keys()) != {"strengths", "weaknesses", "suggestion", "concept_tag"}:
        print(f"    \033[31m✗\033[0m wrong keys: {set(feedback.keys())}")
        ok = False
    if not isinstance(feedback["strengths"], list) or not feedback["strengths"]:
        print("    \033[31m✗\033[0m strengths must be a non-empty list")
        ok = False
    if not isinstance(feedback["weaknesses"], list) or not feedback["weaknesses"]:
        print("    \033[31m✗\033[0m weaknesses must be a non-empty list")
        ok = False
    if not isinstance(feedback["suggestion"], str) or not feedback["suggestion"].strip():
        print("    \033[31m✗\033[0m suggestion must be a non-empty string")
        ok = False
    if feedback["concept_tag"] not in VALID_TAGS:
        print(f"    \033[31m✗\033[0m invalid concept_tag: {feedback['concept_tag']!r}")
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
