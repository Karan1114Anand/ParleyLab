#!/usr/bin/env python3
"""
Integration test for the scoring module.

Runs a fake 5-turn salary negotiation through score_session and prints
the full result. Uses Gemini (the production LLM) for best/worst identification.

Run from the repo root:
    python scripts/test_scoring.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

from parley_ai import score_session

# ---------------------------------------------------------------------------
# Fake 5-turn salary negotiation transcript
# Critic feedbacks are embedded so move-quality scoring is fully exercised.
# ---------------------------------------------------------------------------

HISTORY = [
    {
        "role": "opponent",
        "content": "We're excited about having you join the team. We can offer $78,000 to start.",
    },
    {
        "role": "user",
        "content": "I appreciate the offer. I have a competing bid at $85K. I can see myself here — could you do $95,000?",
        "critic_feedback": {
            "strengths":   ["Disclosed a competing bid to create leverage", "Anchored high at $95K before conceding"],
            "weaknesses":  ["Revealed the exact competing-bid value ($85K) too early — caps the pressure"],
            "suggestion":  "Mention the competing offer exists without naming the number.",
            "concept_tag": "information_disclosure",
        },
    },
    {
        "role": "opponent",
        "content": "That's above our range. We could stretch to $82,000 as a final offer.",
    },
    {
        "role": "user",
        "content": "I appreciate you stretching. I'd need at least $90,000 — and if you can include a relocation stipend, I'd sign today.",
        "critic_feedback": {
            "strengths":   ["Bundled a non-monetary demand effectively", "Used a deadline ('sign today') to create urgency"],
            "weaknesses":  ["Still moving down quickly — only 3 turns in, concession pace is too fast"],
            "suggestion":  "Hold at $92K one more turn before moving to $90K.",
            "concept_tag": "concession_pacing",
        },
    },
    {
        "role": "opponent",
        "content": "We can do $86,000 with a $2,000 relocation stipend. That's genuinely the best we can do.",
    },
    {
        "role": "user",
        "content": "Alright — $86,000 plus the relocation works for me. Deal.",
        "critic_feedback": {
            "strengths":   ["Accepted when a good bundled offer was on the table"],
            "weaknesses":  ["Accepted without testing whether the opponent would move further"],
            "suggestion":  "One more nudge ('can you do $87K?') costs nothing and might land extra value.",
            "concept_tag": "concession_pacing",
        },
    },
    {
        "role": "opponent",
        "content": "Excellent — welcome aboard. We'll get the paperwork started.",
    },
]

USER_BRIEF = {
    "target": 95000,
    "batna":  80000,
    "context": "Candidate with a competing offer, 2 days to decide.",
}

# The deal closed at a midpoint between the two final positions
FINAL_DEAL = 86000.0

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

print()
print("═" * 66)
print("  score_session — 5-turn salary negotiation")
print("═" * 66)
print(f"\n  outcome          : deal_closed")
print(f"  final_deal_value : ${FINAL_DEAL:,.0f}")
print(f"  user target      : ${USER_BRIEF['target']:,.0f}")
print(f"  user BATNA       : ${USER_BRIEF['batna']:,.0f}")
print()

result = score_session(
    history          = HISTORY,
    outcome          = "deal_closed",
    final_deal_value = FINAL_DEAL,
    user_brief       = USER_BRIEF,
)

print(f"  score      : {result['score']}/100")
print(f"  rating     : {result['rating']}")
print()
print(f"  best_move  : Turn {result['best_move']['turn']} — {result['best_move']['summary']}")
print(f"               {result['best_move']['reason']}")
print()
print(f"  worst_move : Turn {result['worst_move']['turn']} — {result['worst_move']['summary']}")
print(f"               {result['worst_move']['reason']}")
print()

# ── Schema checks ─────────────────────────────────────────────────────────────
VALID_RATINGS = {"Excellent", "Good", "Fair", "Poor"}
errors = []

if not isinstance(result["score"], int) or not (0 <= result["score"] <= 100):
    errors.append(f"score out of range: {result['score']}")
if result["rating"] not in VALID_RATINGS:
    errors.append(f"invalid rating: {result['rating']!r}")
for key in ("best_move", "worst_move"):
    m = result[key]
    if not isinstance(m.get("turn"), int):
        errors.append(f"{key}.turn is not int")
    if not isinstance(m.get("summary"), str) or not m["summary"]:
        errors.append(f"{key}.summary is empty")
    if not isinstance(m.get("reason"), str) or not m["reason"]:
        errors.append(f"{key}.reason is empty")

if errors:
    print("  ✗  SCHEMA ERRORS:")
    for e in errors:
        print(f"       {e}")
    sys.exit(1)

print("  ✓  schema valid")
print()

# ── Run without optional fields (graceful degradation) ────────────────────────
print("─" * 66)
print("  Degraded mode (no outcome context)")
print("─" * 66)

degraded = score_session(history=HISTORY)
print(f"\n  score  : {degraded['score']}/100   rating: {degraded['rating']}")
print(f"  best   : Turn {degraded['best_move']['turn']}")
print(f"  worst  : Turn {degraded['worst_move']['turn']}")
print()
print("  ✓  graceful degradation confirmed")
print()
