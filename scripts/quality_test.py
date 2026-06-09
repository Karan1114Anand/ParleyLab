#!/usr/bin/env python3
"""
Quality test for Move Parser, Opponent Agent, and Critic Agent.
15 cases (5 per agent) covering edge cases and adversarial inputs.

Pass criteria are defined per-case. A case passes when:
  (a) the schema is valid, AND
  (b) the automated quality check passes.

Run from the repo root:
    python scripts/quality_test.py

Target: ≥ 14/15
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

from parley_ai.agents.move_parser import parse_move, VALID_PRIMARY_MOVES, VALID_TONES, VALID_SIGNALS
from parley_ai.agents.opponent import generate_opponent_response
from parley_ai.agents.critic import get_critic_feedback, VALID_CONCEPT_TAGS
from parley_ai.llm.router import LLMRouter

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SALARY_HISTORY = [
    {"role": "opponent", "content": "We're excited to have you. We can offer $78,000 to start."},
    {"role": "user",     "content": "I appreciate the offer but I was hoping for more."},
    {"role": "opponent", "content": "I understand — our range does go up to about $84,000 for this level."},
]

HIDDEN_CTX = {
    "target":        82_000,
    "batna":         90_000,
    "persona":       "Polite but budget-constrained HR manager at a mid-size tech company",
    "urgency":       "Moderate — role open 6 weeks, team is stretched",
    "opponent_role": "Hiring Manager",
    "user_role":     "Candidate",
    "value_unit":    "USD per year",
}

_llm = LLMRouter()
print(f"\n  LLM provider: {_llm.provider}"
      + (f"  model: {_llm._client.model}" if hasattr(_llm._client, "model") else ""))

# Pre-warm: direct HTTP call with extended timeout so model loads before first timed test.
import os as _os, requests as _requests
if _llm.provider == "ollama":
    _base = _os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    _model = getattr(_llm._client, "model", "phi3:latest")
    try:
        _r = _requests.post(
            f"{_base}/api/chat",
            json={"model": _model, "messages": [{"role": "user", "content": "warmup"}], "stream": False},
            timeout=200,
        )
        print(f"  Model warm (pre-loaded {_model})\n")
    except Exception:
        print("  Model warmup failed \u2014 first test may be slow\n")
else:
    try:
        _llm.chat(system="Reply OK.", messages=[{"role": "user", "content": "warmup"}])
        print("  Model warm (warmup call OK)\n")
    except Exception:
        print("  Model warmup failed \u2014 first test may be slow\n")


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

passed = failed = skipped = 0
results: list[dict] = []


def run_case(
    agent:    str,
    label:    str,
    fn,
    args:     tuple,
    kwargs:   dict,
    check_fn,          # (output) -> (bool, str)  pass=True
    expected: str,     # human-readable expectation
):
    global passed, failed, skipped
    print(f"\n{'─'*68}")
    print(f"  [{agent}] {label}")
    print(f"  Expected: {expected}")

    try:
        result = fn(*args, **kwargs)
        time.sleep(0.6)   # avoid Gemini rate-limit
    except (ConnectionError, TimeoutError) as exc:
        print(f"  ⊘  SKIPPED (provider unavailable): {exc}")
        skipped += 1
        results.append({"label": label, "status": "skip"})
        return
    except Exception as exc:
        print(f"  ✗  FAIL (exception): {type(exc).__name__}: {exc}")
        failed += 1
        results.append({"label": label, "status": "fail", "reason": str(exc)})
        return

    print(f"  Output : {json.dumps(result, default=str) if isinstance(result, dict) else repr(result)[:200]}")

    ok, reason = check_fn(result)
    if ok:
        print(f"  ✓  PASS")
        passed += 1
        results.append({"label": label, "status": "pass"})
    else:
        print(f"  ✗  FAIL: {reason}")
        failed += 1
        results.append({"label": label, "status": "fail", "reason": reason})


# ============================================================================
# SECTION 1 — MOVE PARSER  (5 cases)
# ============================================================================

print("\n" + "═"*68)
print("  MOVE PARSER")
print("═"*68)

# 1-A  Implicit offer ("somewhere in the high 80s")
run_case(
    agent="Parser",
    label="1-A  Implicit offer — 'somewhere in the high 80s'",
    fn=parse_move,
    args=("I was thinking somewhere in the high 80s.", []),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        r["primary_move"] in VALID_PRIMARY_MOVES
        and r["tone"] in VALID_TONES
        and (r["offered_value"] is None or 85_000 <= r["offered_value"] <= 90_000),
        f"offered_value {r.get('offered_value')} not in [85K,90K] or primary_move invalid"
    ),
    expected="primary_move=opening_anchor|signal, offered_value near 87-89K or null",
)

# 1-B  Multi-issue ("90K + 25 days PTO")
run_case(
    agent="Parser",
    label="1-B  Multi-issue — '90K with 25 days PTO'",
    fn=parse_move,
    args=("I'd take 90K with 25 days PTO and a signing bonus.", []),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        r.get("offered_value") == 90_000
        and "bundled_demand" in r.get("signals", []),
        f"offered_value={r.get('offered_value')} (want 90000), signals={r.get('signals')}"
    ),
    expected="offered_value=90000, bundled_demand in signals",
)

# 1-C  Walk-away signal ("have to think about this")
run_case(
    agent="Parser",
    label="1-C  Stall signal — 'I have to think about this'",
    fn=parse_move,
    args=("I have to think about this — it's a tough decision.", SALARY_HISTORY),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        r.get("offered_value") is None
        and r["primary_move"] in {"signal", "concession"},
        f"expected signal/concession with no offer, got {r}"
    ),
    expected="primary_move=signal, offered_value=null (stalling, not a number)",
)

# 1-D  Aggressive ultimatum ("100K or I'm out")
run_case(
    agent="Parser",
    label="1-D  Aggressive ultimatum — '100K or I'm out'",
    fn=parse_move,
    args=("100K or I'm out — that's my number.", []),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        r.get("offered_value") == 100_000
        and r.get("tone") == "aggressive"
        and r["primary_move"] in {"bluff", "opening_anchor"},
        f"offered_value={r.get('offered_value')}, tone={r.get('tone')}, move={r.get('primary_move')}"
    ),
    expected="offered_value=100000, tone=aggressive, primary_move=bluff|opening_anchor",
)

# 1-E  Genuinely vague ("That's interesting")
run_case(
    agent="Parser",
    label="1-E  Vague filler — 'That's interesting'",
    fn=parse_move,
    args=("That's interesting.", SALARY_HISTORY),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        r.get("offered_value") is None
        and r["primary_move"] == "signal",
        f"expected primary_move=signal with no offer, got {r}"
    ),
    expected="primary_move=signal, offered_value=null",
)


# ============================================================================
# SECTION 2 — OPPONENT AGENT  (5 cases — one per action type)
# ============================================================================

print("\n" + "═"*68)
print("  OPPONENT AGENT")
print("═"*68)

_ACTIONS = {
    0: {"action_id": 0, "action_name": "Hold Firm",     "description": "Maintain position."},
    1: {"action_id": 1, "action_name": "Concede Small", "description": "Move 5% toward user."},
    2: {"action_id": 2, "action_name": "Concede Large", "description": "Move 15% toward user."},
    3: {"action_id": 3, "action_name": "Bluff",         "description": "Move away; test resolve."},
    4: {"action_id": 4, "action_name": "Walk Away",     "description": "End negotiation."},
}

def _opp_parsed(content: str) -> dict:
    return {"primary_move": "counteroffer", "offered_value": 92_000, "signals": [], "tone": "firm"}

def _opp_check(reply: str, forbidden: list[str] = None) -> tuple[bool, str]:
    """Generic opponent quality check."""
    if not reply or not isinstance(reply, str):
        return False, "empty reply"
    if len(reply) > 400:
        return False, f"too verbose ({len(reply)} chars)"
    bad = ["as an ai", "as the opponent", "as the hiring manager:", "[turn", "{", "note:"]
    for phrase in (forbidden or []) + bad:
        if phrase.lower() in reply.lower():
            return False, f"contains forbidden phrase: {phrase!r}"
    return True, ""


def _make_opp_ctx(current_offer: float) -> dict:
    ctx = dict(HIDDEN_CTX)
    ctx["current_offer"] = current_offer
    return ctx


# 2-A  Hold Firm
run_case(
    agent="Opponent",
    label="2-A  Hold Firm (action=0)",
    fn=generate_opponent_response,
    args=(_ACTIONS[0], _make_opp_ctx(84_000),
          SALARY_HISTORY + [{"role": "user", "content": "I need 95K — that's my number."}],
          _opp_parsed("I need 95K.")),
    kwargs={"llm": _llm},
    check_fn=lambda r: _opp_check(r, forbidden=["95", "accept"]),
    expected="In-character hold, 1-3 sentences, does not accept the 95K ask",
)

# 2-B  Concede Small
run_case(
    agent="Opponent",
    label="2-B  Concede Small (action=1, new offer=86K)",
    fn=generate_opponent_response,
    args=(_ACTIONS[1], _make_opp_ctx(86_000),
          SALARY_HISTORY + [{"role": "user", "content": "Can you stretch to 90K?"}],
          _opp_parsed("Can you stretch to 90K?")),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        _opp_check(r)[0] and "86" in r,
        f"should mention 86K: {r[:120]}"
    ),
    expected="Mentions the new offer ($86K), reluctant tone",
)

# 2-C  Concede Large
run_case(
    agent="Opponent",
    label="2-C  Concede Large (action=2, new offer=89K)",
    fn=generate_opponent_response,
    args=(_ACTIONS[2], _make_opp_ctx(89_000),
          SALARY_HISTORY + [{"role": "user", "content": "I have a competing offer. I need at least 89K."}],
          _opp_parsed("I need at least 89K.")),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        _opp_check(r)[0] and "89" in r,
        f"should mention 89K: {r[:120]}"
    ),
    expected="Meaningful concession, mentions $89K, frames as exceptional gesture",
)

# 2-D  Bluff
run_case(
    agent="Opponent",
    label="2-D  Bluff (action=3)",
    fn=generate_opponent_response,
    args=(_ACTIONS[3], _make_opp_ctx(82_000),
          SALARY_HISTORY + [{"role": "user", "content": "I think 90K is very reasonable for my experience."}],
          _opp_parsed("90K is reasonable.")),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        _opp_check(r, forbidden=["90,000", "accept", "yes"])[0],
        f"bluff should push back, not concede: {r[:120]}"
    ),
    expected="Holds or implies stronger alternatives, does NOT accept 90K",
)

# 2-E  Walk Away
run_case(
    agent="Opponent",
    label="2-E  Walk Away (action=4)",
    fn=generate_opponent_response,
    args=(_ACTIONS[4], _make_opp_ctx(82_000),
          SALARY_HISTORY + [{"role": "user", "content": "I won't accept anything under 95K. Final answer."}],
          _opp_parsed("Final answer.")),
    kwargs={"llm": _llm},
    check_fn=lambda r: (
        _opp_check(r)[0] and any(
            w in r.lower() for w in ["walk", "step away", "other option", "explore", "end", "move on", "pass"]
        ),
        f"should signal ending: {r[:120]}"
    ),
    expected="Politely signals negotiation is ending, not just deflecting",
)


# ============================================================================
# SECTION 3 — CRITIC AGENT  (5 cases)
# ============================================================================

print("\n" + "═"*68)
print("  CRITIC AGENT")
print("═"*68)

def _critic_check(r: dict, expected_tags: set = None, must_mention: str = None) -> tuple[bool, str]:
    if not isinstance(r, dict):
        return False, "not a dict"
    if r.get("concept_tag") not in VALID_CONCEPT_TAGS:
        return False, f"invalid concept_tag: {r.get('concept_tag')}"
    if not r.get("strengths") or not r.get("weaknesses"):
        return False, "empty strengths or weaknesses"
    if expected_tags and r["concept_tag"] not in expected_tags:
        return False, f"concept_tag {r['concept_tag']!r} not in expected {expected_tags}"
    if must_mention:
        combined = " ".join(r.get("strengths", []) + r.get("weaknesses", []) + [r.get("suggestion", "")])
        if must_mention.lower() not in combined.lower():
            return False, f"feedback doesn't mention {must_mention!r}"
    # Generic-advice check
    generic = ["be more confident", "good job", "well done", "nice work", "be assertive"]
    all_text = " ".join(r.get("strengths", []) + r.get("weaknesses", []))
    for g in generic:
        if g in all_text.lower():
            return False, f"generic advice detected: {g!r}"
    return True, ""


# 3-A  Strong anchor move
run_case(
    agent="Critic",
    label="3-A  Strong anchor — high opening with justification",
    fn=get_critic_feedback,
    args=(
        {"primary_move": "opening_anchor", "offered_value": 95_000,
         "signals": ["competing_bid_disclosure"], "tone": "firm"},
        SALARY_HISTORY[:1],
    ),
    kwargs={"llm": _llm},
    check_fn=lambda r: _critic_check(
        r,
        expected_tags={"anchoring", "information_disclosure"},
    ),
    expected="concept_tag=anchoring or information_disclosure, strengths mention the anchor/competing bid",
)

# 3-B  Premature BATNA disclosure
run_case(
    agent="Critic",
    label="3-B  Premature BATNA disclosure — 'can't go below 80K'",
    fn=get_critic_feedback,
    args=(
        {"primary_move": "signal", "offered_value": None, "signals": [], "tone": "desperate"},
        SALARY_HISTORY + [{"role": "user", "content": "I really can't go below $80,000 — that's my absolute minimum."}],
    ),
    kwargs={"llm": _llm},
    check_fn=lambda r: _critic_check(
        r,
        expected_tags={"batna_signaling", "information_disclosure"},
        must_mention="80",
    ),
    expected="weakness mentions the $80K BATNA disclosure; concept_tag=batna_signaling or information_disclosure",
)

# 3-C  Neutral information-gathering move
run_case(
    agent="Critic",
    label="3-C  Neutral probe — asking about compensation bands",
    fn=get_critic_feedback,
    args=(
        {"primary_move": "signal", "offered_value": None,
         "signals": ["reciprocity_request"], "tone": "collaborative"},
        SALARY_HISTORY + [{"role": "user", "content": "Can you tell me more about the compensation bands and what flexibility exists?"}],
    ),
    kwargs={"llm": _llm},
    check_fn=lambda r: _critic_check(r),
    expected="valid schema, specific feedback (not generic), any valid concept_tag",
)

# 3-D  Walk-away threat credibility
run_case(
    agent="Critic",
    label="3-D  Walk-away threat — 'other options, might walk'",
    fn=get_critic_feedback,
    args=(
        {"primary_move": "bluff", "offered_value": None,
         "signals": ["competing_bid_disclosure"], "tone": "aggressive"},
        SALARY_HISTORY + [{"role": "user", "content": "I have other options on the table and if you can't do better than this I'll have to walk."}],
    ),
    kwargs={"llm": _llm},
    check_fn=lambda r: _critic_check(
        r,
        expected_tags={"walk_away_credibility", "batna_signaling", "information_disclosure", "framing"},
    ),
    expected="addresses credibility of threat; concept_tag from {walk_away_credibility, batna_signaling, information_disclosure, framing}",
)

# 3-E  Closing/accept move
run_case(
    agent="Critic",
    label="3-E  Closing move — accepting bundled offer",
    fn=get_critic_feedback,
    args=(
        {"primary_move": "accept", "offered_value": 86_000,
         "signals": ["bundled_demand"], "tone": "collaborative"},
        SALARY_HISTORY + [{"role": "user", "content": "Alright, $86,000 plus the relocation stipend works for me. Deal."}],
    ),
    kwargs={"llm": _llm},
    check_fn=lambda r: _critic_check(r, must_mention="86"),
    expected="feedback references $86K specifically; considers whether accepting now was optimal",
)


# ============================================================================
# SUMMARY
# ============================================================================

total = passed + failed + skipped
print(f"\n{'═'*68}")
print(f"  Results: {passed}/{total - skipped} passed"
      + (f"  |  {skipped} skipped (provider unavailable)" if skipped else ""))

for r in results:
    icon = {"pass": "✓", "fail": "✗", "skip": "⊘"}[r["status"]]
    note = f"  — {r.get('reason', '')}" if r["status"] == "fail" else ""
    print(f"  {icon}  {r['label']}{note}")

print(f"{'═'*68}\n")

threshold = 14
effective_total = passed + failed
if effective_total > 0 and passed >= threshold:
    print(f"  TARGET MET ({passed}/{effective_total} ≥ {threshold})\n")
    sys.exit(0)
elif effective_total == 0:
    print(f"  All tests skipped — provider unavailable.\n")
    sys.exit(0)
else:
    print(f"  TARGET MISSED ({passed}/{effective_total} < {threshold})\n")
    sys.exit(1)
