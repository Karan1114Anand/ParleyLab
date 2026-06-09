#!/usr/bin/env python3
"""
parley_ai smoke test — runs all 5 public functions once with realistic data.

Run from the repo root:
    python scripts/smoke_test.py

Expected: all 5 functions produce valid output in under 60 s.
LLM calls use the configured provider (PARLEYLAB_LLM_PROVIDER env var).
If the LLM is unavailable, the test passes using built-in fallbacks.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

from parley_ai import (
    parse_move,
    get_strategic_action,
    generate_opponent_response,
    get_critic_feedback,
    score_session,
)

# ── Shared test data ─────────────────────────────────────────────────────────

HISTORY = [
    {"role": "opponent", "content": "We can offer $80,000 to start."},
    {"role": "user",     "content": "I appreciate that — I was thinking more like $92,000."},
    {"role": "opponent", "content": "That's a stretch, but let me check internally."},
]

USER_MESSAGE = "I have a competing offer at $88K — if you can do $90K with relocation, I'm in."

HIDDEN_CTX = {
    "target":        82_000,
    "batna":         78_000,
    "persona":       "Polite but budget-constrained HR manager",
    "urgency":       "Moderate — role open 6 weeks",
    "current_offer": 84_000,
    "value_unit":    "USD per year",
}

STATE_VECTOR = [0.72, 0.55, 0.30, 0.15, 0.10, 0.17, 0.40]

# ── Validators ───────────────────────────────────────────────────────────────

VALID_MOVES    = {"opening_anchor","counteroffer","concession","bluff","walk_away","accept","signal"}
VALID_TONES    = {"collaborative","firm","aggressive","desperate"}
VALID_SIGNALS  = {"competing_bid_disclosure","bundled_demand","time_pressure","reciprocity_request"}
VALID_TAGS     = {"anchoring","concession_pacing","batna_signaling","reciprocity",
                  "information_disclosure","framing","walk_away_credibility"}
VALID_RATINGS  = {"Poor","Fair","Good","Excellent"}
VALID_ACTIONS  = {0,1,2,3,4}


def check(label: str, errors: list[str]) -> None:
    if errors:
        for e in errors:
            print(f"   ✗  {e}")
        print(f"  FAIL  [{label}]")
        sys.exit(1)
    print(f"  PASS  [{label}]")


# ── 1. parse_move ─────────────────────────────────────────────────────────────
print("\n── 1. parse_move")
t0 = time.perf_counter()
pm = parse_move(USER_MESSAGE, HISTORY)
elapsed = time.perf_counter() - t0
print(f"     {pm}  ({elapsed:.2f}s)")
errs = []
if pm.get("primary_move") not in VALID_MOVES:
    errs.append(f"primary_move {pm.get('primary_move')!r} not valid")
if pm.get("tone") not in VALID_TONES:
    errs.append(f"tone {pm.get('tone')!r} not valid")
if not isinstance(pm.get("signals"), list):
    errs.append("signals must be a list")
bad_sigs = [s for s in pm.get("signals", []) if s not in VALID_SIGNALS]
if bad_sigs:
    errs.append(f"unknown signals: {bad_sigs}")
v = pm.get("offered_value")
if v is not None and not isinstance(v, (int, float)):
    errs.append(f"offered_value must be numeric or null, got {type(v).__name__}")
check("parse_move", errs)


# ── 2. get_strategic_action ───────────────────────────────────────────────────
print("\n── 2. get_strategic_action")
t0 = time.perf_counter()
act = get_strategic_action(STATE_VECTOR)
elapsed = time.perf_counter() - t0
print(f"     {act}  ({elapsed:.2f}s)")
errs = []
if act.get("action_id") not in VALID_ACTIONS:
    errs.append(f"action_id {act.get('action_id')!r} not in {{0..4}}")
if not isinstance(act.get("action_name"), str) or not act["action_name"]:
    errs.append("action_name missing or empty")
if not isinstance(act.get("description"), str):
    errs.append("description must be a string")
check("get_strategic_action", errs)


# ── 3. generate_opponent_response ─────────────────────────────────────────────
print("\n── 3. generate_opponent_response")
full_history = HISTORY + [{"role": "user", "content": USER_MESSAGE}]
t0 = time.perf_counter()
reply = generate_opponent_response(act, HIDDEN_CTX, full_history, pm)
elapsed = time.perf_counter() - t0
print(f"     {reply!r}  ({elapsed:.2f}s)")
errs = []
if not isinstance(reply, str) or not reply.strip():
    errs.append("reply must be a non-empty string")
if len(reply) > 600:
    errs.append(f"reply too long ({len(reply)} chars; expected ≤ 600)")
for leaked in [str(HIDDEN_CTX["target"]), str(HIDDEN_CTX["batna"])]:
    if leaked.replace("000","K") in reply or leaked in reply:
        errs.append(f"hidden value {leaked!r} leaked into reply")
check("generate_opponent_response", errs)


# ── 4. get_critic_feedback ────────────────────────────────────────────────────
print("\n── 4. get_critic_feedback")
t0 = time.perf_counter()
fb = get_critic_feedback(pm, full_history)
elapsed = time.perf_counter() - t0
print(f"     strengths : {fb.get('strengths')}")
print(f"     weaknesses: {fb.get('weaknesses')}")
print(f"     suggestion: {fb.get('suggestion')!r}")
print(f"     tag       : {fb.get('concept_tag')!r}  ({elapsed:.2f}s)")
errs = []
if not isinstance(fb.get("strengths"), list) or not fb["strengths"]:
    errs.append("strengths must be a non-empty list")
if not isinstance(fb.get("weaknesses"), list) or not fb["weaknesses"]:
    errs.append("weaknesses must be a non-empty list")
if not isinstance(fb.get("suggestion"), str) or not fb["suggestion"].strip():
    errs.append("suggestion must be a non-empty string")
if fb.get("concept_tag") not in VALID_TAGS:
    errs.append(f"concept_tag {fb.get('concept_tag')!r} not valid")
check("get_critic_feedback", errs)


# ── 5. score_session ──────────────────────────────────────────────────────────
print("\n── 5. score_session")
scored_history = [
    {"role": "opponent", "content": "We can offer $80,000 to start."},
    {
        "role": "user", "content": "I have a competing offer — I need at least $92K.",
        "critic_feedback": {
            "strengths":   ["Disclosed competing offer without naming the amount"],
            "weaknesses":  ["Jumped straight to 92K — leaves no room for incremental gains"],
            "suggestion":  "Hold at 95K for one more turn.",
            "concept_tag": "anchoring",
        },
    },
    {"role": "opponent", "content": "We can stretch to $86K with relocation."},
    {
        "role": "user", "content": "Alright, $86K plus relocation — deal.",
        "critic_feedback": {
            "strengths":   ["Accepted a bundled offer that exceeded pure salary"],
            "weaknesses":  ["Closed without one final push"],
            "suggestion":  "Try asking for $87K one more time.",
            "concept_tag": "concession_pacing",
        },
    },
]
t0 = time.perf_counter()
score = score_session(
    scored_history,
    outcome="deal_closed",
    final_deal_value=86_000,
    user_brief={"target": 95_000, "batna": 80_000},
)
elapsed = time.perf_counter() - t0
print(f"     score : {score.get('score')}/100  rating: {score.get('rating')}  ({elapsed:.2f}s)")
print(f"     best  : Turn {score['best_move'].get('turn')} — {score['best_move'].get('summary')}")
print(f"     worst : Turn {score['worst_move'].get('turn')} — {score['worst_move'].get('summary')}")
errs = []
s = score.get("score")
if not isinstance(s, int) or not (0 <= s <= 100):
    errs.append(f"score must be int in [0,100], got {s!r}")
if score.get("rating") not in VALID_RATINGS:
    errs.append(f"rating {score.get('rating')!r} not valid")
for key in ("best_move", "worst_move"):
    m = score.get(key, {})
    if not isinstance(m.get("turn"), int):
        errs.append(f"{key}.turn must be int")
    if not isinstance(m.get("summary"), str) or not m["summary"]:
        errs.append(f"{key}.summary missing")
    if not isinstance(m.get("reason"), str) or not m["reason"]:
        errs.append(f"{key}.reason missing")
check("score_session", errs)


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "═"*50)
print("  All 5 smoke tests passed.")
print("═"*50 + "\n")
