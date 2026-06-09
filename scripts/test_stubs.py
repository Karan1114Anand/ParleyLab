#!/usr/bin/env python3
"""
Smoke test for parley_ai stub functions.

Run from the repo root:
    python scripts/test_stubs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parley_ai import (
    get_critic_feedback,
    get_strategic_action,
    generate_opponent_response,
    parse_move,
    score_session,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

HISTORY = [
    {"role": "opponent", "content": "We're excited to have you. We were thinking around 78K to start."},
    {"role": "user",     "content": "I appreciate the offer. I have a competing bid at 85K and I'd come down to 92K if you include a relocation stipend."},
    {"role": "opponent", "content": "I hear you. Let me see what I can do — I think I can stretch to 88K with a relocation stipend."},
]

USER_MSG = "I have a competing bid at 85K. I'd come down to 92,000 if you include relocation."

STATE_VECTOR = [0.78, 0.92, 0.30, 0.05, 0.12, 0.14, 0.20]

HIDDEN_CONTEXT = {
    "target":  82_000,
    "batna":   90_000,
    "persona": "Polite but budget-constrained",
    "urgency": "Moderate — role open for 6 weeks",
}

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

_passed = _failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        print(f"  \033[32m✓\033[0m  {label}")
        _passed += 1
    else:
        print(f"  \033[31m✗\033[0m  {label}" + (f"  [{detail}]" if detail else ""))
        _failed += 1


def section(title: str) -> None:
    print(f"\n{'─' * 64}")
    print(f"  {title}")
    print(f"{'─' * 64}")


# ---------------------------------------------------------------------------
# 1. parse_move
# ---------------------------------------------------------------------------

section("1 · parse_move")

result = parse_move(USER_MSG, HISTORY)
print(f"\n  input : {USER_MSG!r}")
print(f"  output: {result}\n")

check("returns dict",                     isinstance(result, dict))
check("primary_move is non-empty str",    isinstance(result["primary_move"], str) and result["primary_move"])
check("offered_value is float or None",   result["offered_value"] is None or isinstance(result["offered_value"], (int, float)))
check("signals is non-empty list",        isinstance(result["signals"], list) and len(result["signals"]) > 0)
check("tone is str",                      isinstance(result["tone"], str) and result["tone"])
check("detects offered_value 92000",      result["offered_value"] == 92000.0)
check("detects competing_bid signal",     "competing_bid_disclosure" in result["signals"])

try:
    parse_move("", [])
    check("raises ValueError on empty message", False, "no exception raised")
except ValueError:
    check("raises ValueError on empty message", True)

try:
    parse_move("hello", "not-a-list")
    check("raises TypeError on bad history",    False, "no exception raised")
except TypeError:
    check("raises TypeError on bad history",    True)

# ---------------------------------------------------------------------------
# 2. get_strategic_action
# ---------------------------------------------------------------------------

section("2 · get_strategic_action")

result  = get_strategic_action(STATE_VECTOR)
result2 = get_strategic_action(STATE_VECTOR)
print(f"\n  state_vector : {STATE_VECTOR}")
print(f"  result       : {result}\n")

check("returns dict",                     isinstance(result, dict))
check("action_id is int in 0–4",          isinstance(result["action_id"], int) and result["action_id"] in range(5))
check("action_name is non-empty str",     isinstance(result["action_name"], str) and result["action_name"])
check("description is non-empty str",     isinstance(result["description"], str) and result["description"])
check("deterministic — same input same output", result["action_id"] == result2["action_id"])

try:
    get_strategic_action([0.5] * 6)
    check("raises ValueError on wrong length",    False, "no exception raised")
except ValueError:
    check("raises ValueError on wrong length",    True)

try:
    get_strategic_action([1.5] * 7)
    check("raises ValueError on out-of-range",    False, "no exception raised")
except ValueError:
    check("raises ValueError on out-of-range",    True)

try:
    get_strategic_action((0.5,) * 7)
    check("raises TypeError on non-list",         False, "no exception raised")
except TypeError:
    check("raises TypeError on non-list",         True)

# ---------------------------------------------------------------------------
# 3. generate_opponent_response
# ---------------------------------------------------------------------------

section("3 · generate_opponent_response")

parsed_move = parse_move(USER_MSG, HISTORY)
action      = get_strategic_action(STATE_VECTOR)
response    = generate_opponent_response(action, HIDDEN_CONTEXT, HISTORY, parsed_move)

print(f"\n  action   : {action['action_name']!r}")
print(f"  response : {response!r}\n")

check("returns non-empty str",            isinstance(response, str) and response)

try:
    generate_opponent_response({"no_name": True}, HIDDEN_CONTEXT, HISTORY, parsed_move)
    check("raises KeyError on missing action_name", False, "no exception raised")
except KeyError:
    check("raises KeyError on missing action_name", True)

try:
    generate_opponent_response("bad", HIDDEN_CONTEXT, HISTORY, parsed_move)
    check("raises TypeError on non-dict action",    False, "no exception raised")
except TypeError:
    check("raises TypeError on non-dict action",    True)

# ---------------------------------------------------------------------------
# 4. get_critic_feedback
# ---------------------------------------------------------------------------

section("4 · get_critic_feedback")

feedback = get_critic_feedback(parsed_move, HISTORY)
print(f"\n  parsed_move : {parsed_move}")
print(f"  feedback    : {feedback}\n")

check("returns dict",                     isinstance(feedback, dict))
check("strengths is list",                isinstance(feedback["strengths"], list))
check("weaknesses is list",               isinstance(feedback["weaknesses"], list))
check("suggestion is non-empty str",      isinstance(feedback["suggestion"], str) and feedback["suggestion"])
check("concept_tag is non-empty str",     isinstance(feedback["concept_tag"], str) and feedback["concept_tag"])

try:
    get_critic_feedback("not-a-dict", HISTORY)
    check("raises TypeError on bad parsed_move",  False, "no exception raised")
except TypeError:
    check("raises TypeError on bad parsed_move",  True)

# ---------------------------------------------------------------------------
# 5. score_session
# ---------------------------------------------------------------------------

section("5 · score_session")

score = score_session(HISTORY)
print(f"\n  history ({len(HISTORY)} messages) → {score}\n")

VALID_RATINGS = {"Excellent", "Good", "Fair", "Needs Work"}

check("returns dict",                     isinstance(score, dict))
check("score is int in 0–100",            isinstance(score["score"], int) and 0 <= score["score"] <= 100)
check("rating is valid str",              score["rating"] in VALID_RATINGS)
check("best_move is dict",                isinstance(score["best_move"], dict))
check("best_move has turn + summary",     "turn" in score["best_move"] and "summary" in score["best_move"])
check("worst_move is dict",               isinstance(score["worst_move"], dict))
check("worst_move has turn + summary",    "turn" in score["worst_move"] and "summary" in score["worst_move"])

try:
    score_session([])
    check("raises ValueError on empty history",   False, "no exception raised")
except ValueError:
    check("raises ValueError on empty history",   True)

try:
    score_session("not-a-list")
    check("raises TypeError on non-list history", False, "no exception raised")
except TypeError:
    check("raises TypeError on non-list history", True)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'═' * 64}")
status = "\033[32mALL PASSED\033[0m" if _failed == 0 else f"\033[31m{_failed} FAILED\033[0m"
print(f"  {status}   {_passed} passed  /  {_passed + _failed} total")
print(f"{'═' * 64}\n")

sys.exit(0 if _failed == 0 else 1)
