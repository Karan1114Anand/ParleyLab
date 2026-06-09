#!/usr/bin/env python3
"""
scripts/test_opponent.py — 5-turn smoke test for the opponent agent.

Each turn uses a different (action, persona) combination to verify that
the LLM produces visibly distinct replies matching the chosen strategic move.

Run: python scripts/test_opponent.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Point the opponent at the locally available model (llama3.1:8b may not be pulled).
os.environ.setdefault("PARLEYLAB_OPPONENT_MODEL", "phi3:latest")

from parley_ai import generate_opponent_response

SCENARIOS = [
    {
        "label": "Hold Firm — Polite but budget-constrained HR",
        "action": {
            "action_id": 0,
            "action_name": "Hold Firm",
            "description": "Maintain position; signal confidence.",
        },
        "hidden_context": {
            "target": 85000,
            "batna": 82000,
            "persona": "Polite but budget-constrained HR manager at a mid-size tech company who genuinely likes the candidate",
            "urgency": "Low",
        },
        "history": [
            {"role": "opponent", "content": "We'd love to have you on board — our offer is $84,000."},
            {"role": "user", "content": "I really appreciate the offer, but I was hoping for closer to $92,000 given my five years of experience in this domain."},
        ],
        "parsed_user_move": {
            "primary_move": "counteroffer",
            "offered_value": 92000,
            "signals": [],
            "tone": "collaborative",
        },
    },
    {
        "label": "Concede Small — Direct, time-pressured freelance client",
        "action": {
            "action_id": 1,
            "action_name": "Concede Small",
            "description": "Move 5% toward the opponent.",
        },
        "hidden_context": {
            "target": 15000,
            "batna": 18000,
            "persona": "Direct, time-pressured freelance client who has a product launch in ten days and can't afford delays",
            "urgency": "High",
        },
        "history": [
            {"role": "opponent", "content": "My budget for this project is $14,000, all in."},
            {"role": "user", "content": "For the scope you're describing, I can't go below $17,000. That's my standard rate."},
        ],
        "parsed_user_move": {
            "primary_move": "counteroffer",
            "offered_value": 17000,
            "signals": [],
            "tone": "firm",
        },
    },
    {
        "label": "Concede Large — Motivated landlord with vacant property",
        "action": {
            "action_id": 2,
            "action_name": "Concede Large",
            "description": "Move 15% toward the opponent.",
        },
        "hidden_context": {
            "target": 2800,
            "batna": 2550,
            "persona": "Motivated landlord who has had the apartment sitting empty for two months and needs cash flow",
            "urgency": "High",
        },
        "history": [
            {"role": "opponent", "content": "The listing price is $2,900 per month."},
            {"role": "user", "content": "I can do $2,600, and I'll sign a 24-month lease right now."},
        ],
        "parsed_user_move": {
            "primary_move": "counteroffer",
            "offered_value": 2600,
            "signals": ["bundled_demand"],
            "tone": "collaborative",
        },
    },
    {
        "label": "Bluff — Confident startup founder who plays hardball",
        "action": {
            "action_id": 3,
            "action_name": "Bluff",
            "description": "Move 5% away from opponent to imply a stronger BATNA.",
        },
        "hidden_context": {
            "target": 4.0,
            "batna": 6.0,
            "persona": "Confident, slightly combative startup founder who hates time-wasters and projects strength",
            "urgency": "Low",
        },
        "history": [
            {"role": "opponent", "content": "We can offer 5% equity for a one-year advisory commitment."},
            {"role": "user", "content": "I have another term sheet at 7%. I'd need at least 6.5% to make this worthwhile."},
        ],
        "parsed_user_move": {
            "primary_move": "counteroffer",
            "offered_value": 6.5,
            "signals": ["competing_bid_disclosure"],
            "tone": "firm",
        },
    },
    {
        "label": "Walk Away — Tired hiring manager after three stalled rounds",
        "action": {
            "action_id": 4,
            "action_name": "Walk Away",
            "description": "End negotiation and take BATNA.",
        },
        "hidden_context": {
            "target": 90000,
            "batna": 87000,
            "persona": "Weary hiring manager who has spent three rounds going in circles and has other candidates waiting",
            "urgency": "Moderate",
        },
        "history": [
            {"role": "opponent", "content": "Our absolute ceiling is $88,000."},
            {"role": "user", "content": "I appreciate that, but I won't accept anything under $95,000. That's my final answer."},
            {"role": "opponent", "content": "I understand where you're coming from, but we genuinely cannot go above $88,000."},
            {"role": "user", "content": "$95,000. I'm not moving on this."},
        ],
        "parsed_user_move": {
            "primary_move": "bluff",
            "offered_value": 95000,
            "signals": [],
            "tone": "aggressive",
        },
    },
]


def main() -> None:
    print("=" * 60)
    print("Opponent Agent — 5-Turn Smoke Test")
    print("=" * 60)

    passed = 0
    for i, scenario in enumerate(SCENARIOS, 1):
        label = scenario["label"]
        print(f"\nTurn {i}: {label}")
        print("-" * 50)
        try:
            reply = generate_opponent_response(
                action=scenario["action"],
                hidden_context=scenario["hidden_context"],
                history=scenario["history"],
                parsed_user_move=scenario["parsed_user_move"],
            )
            print(f'Opponent: "{reply}"')

            assert isinstance(reply, str) and reply.strip(), "Reply must be a non-empty string"
            assert len(reply) < 1000, "Reply is too long (> 1000 chars)"

            # Soft check: hidden numbers should not appear verbatim
            for key in ("target", "batna"):
                hidden_val = str(scenario["hidden_context"][key])
                if hidden_val in reply:
                    print(f"  WARNING: reply may contain hidden {key} value ({hidden_val})")

            print("  [PASS]")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {type(exc).__name__}: {exc}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{len(SCENARIOS)} passed")
    if passed < len(SCENARIOS):
        sys.exit(1)


if __name__ == "__main__":
    main()
