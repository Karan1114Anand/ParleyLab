# parley_ai — Public Interface Reference

**For Taanush** — everything you need to wire the backend to the AI layer.

---

## Setup

Copy `.env.example` to `.env` and fill in your key:

```
GEMINI_API_KEY=your-key-here          # required for production
PARLEYLAB_LLM_PROVIDER=gemini         # or "ollama" for local dev
PARLEYLAB_MODEL=gemini-2.0-flash      # optional model override
```

For local development without a Gemini key, set `PARLEYLAB_LLM_PROVIDER=ollama`
and ensure `ollama serve` is running with `phi3:latest` pulled.

---

## Import

```python
from parley_ai import (
    parse_move,
    get_strategic_action,
    generate_opponent_response,
    get_critic_feedback,
    score_session,
)
```

Only these five names are part of the public API. Everything else
(`LLMRouter`, `StrategyPolicy`, agent internals) is private.

---

## Functions

### `parse_move(user_message, history) → dict`

Classifies the user's negotiation message into structured primitives.
Used at the start of every turn before calling `get_strategic_action`.

**Input**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `user_message` | `str` | ✓ | Raw user text, non-empty |
| `history` | `list[dict]` | ✓ | Prior messages; each `{"role": "user"|"opponent", "content": str}` |

**Output**

```python
{
    "primary_move":  "opening_anchor",          # str — see move types below
    "offered_value": 92000.0,                   # float | None
    "signals":       ["competing_bid_disclosure", "bundled_demand"],  # list[str]
    "tone":          "collaborative",            # str
}
```

**Move types:** `opening_anchor` · `counteroffer` · `concession` ·
`bluff` · `walk_away` · `accept` · `signal`

**Signal types:** `competing_bid_disclosure` · `bundled_demand` ·
`time_pressure` · `reciprocity_request`

**Tone values:** `collaborative` · `firm` · `aggressive` · `desperate`

**Errors & fallbacks**

| Condition | Behaviour |
|-----------|-----------|
| Empty `user_message` | Raises `ValueError` |
| `history` not a list | Raises `TypeError` |
| LLM unreachable / timeout | Falls back to keyword heuristic — always returns valid schema |
| LLM returns malformed JSON | Returns safe default `{"primary_move": "signal", "offered_value": null, ...}` |

---

### `get_strategic_action(state_vector) → dict`

Queries the trained PPO policy to decide the opponent's next move.

**Input**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `state_vector` | `list[float]` | ✓ | Exactly 7 floats, each in `[0.0, 1.0]` |

**State vector layout**

```
[0] own_offer_norm                     normalised to [min_value, max_value]
[1] opponent_offer_norm
[2] turn_norm                          current_turn / max_turns
[3] own_concession_rate                avg % conceded per user turn
[4] opponent_concession_rate
[5] gap_norm                           |own_offer - opp_offer| / value_range
[6] turns_since_last_concession_norm
```

**Output**

```python
{"action_id": 1, "action_name": "Concede Small", "description": "Move 5% toward the opponent's position."}
```

**Action map**

| ID | Name | Meaning |
|----|------|---------|
| 0 | Hold Firm | Maintain position; signal confidence |
| 1 | Concede Small | Move ~5% toward opponent |
| 2 | Concede Large | Move ~15% toward opponent |
| 3 | Bluff | Move ~5% away; imply stronger BATNA |
| 4 | Walk Away | End negotiation; take BATNA |

**Errors & fallbacks**

| Condition | Behaviour |
|-----------|-----------|
| `state_vector` not a list | Raises `TypeError` |
| Length ≠ 7 | Raises `ValueError` |
| Value outside `[0, 1]` | Raises `ValueError` |
| Policy load fails | Returns action 0 (Hold Firm) with error logged |

---

### `generate_opponent_response(action, hidden_context, history, parsed_user_move, llm=None) → str`

Generates the opponent's natural-language reply for the turn.

**Input**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `action` | `dict` | ✓ | Output of `get_strategic_action()`; must have `"action_name"` |
| `hidden_context` | `dict` | ✓ | Opponent's private data (see below) |
| `history` | `list[dict]` | ✓ | Full conversation including current user turn as last entry |
| `parsed_user_move` | `dict` | ✓ | Output of `parse_move()` for current turn |
| `llm` | `LLMRouter \| None` | — | Pass `None` to auto-construct from env |

**`hidden_context` structure**

```python
{
    "target":        85000.0,      # opponent's ideal outcome value
    "batna":         78000.0,      # opponent's walk-away threshold
    "persona":       "Polite but budget-constrained HR manager",
    "urgency":       "Moderate — role open 6 weeks",
    "current_offer": 82000.0,      # optional: specific number to state this turn
    "value_unit":    "USD per year",  # optional: appended to current_offer
}
```

> **CRITICAL:** Never pass `target` or `batna` anywhere the user can see.
> The opponent prompt is instructed never to state those numbers, but do not
> surface `hidden_context` to the frontend under any circumstances.

**Output**

A single plain string. Example:

```
"I hear you — let me stretch this one more time.
I can go to 82,000 USD per year, but that's genuinely the ceiling."
```

**Errors & fallbacks**

| Condition | Behaviour |
|-----------|-----------|
| `action` not a dict | Raises `TypeError` |
| `hidden_context` not a dict | Raises `TypeError` |
| `action` missing `"action_name"` | Raises `ValueError` |
| LLM unavailable | Falls back to hardcoded template; if `current_offer` is set, template includes the number |

---

### `get_critic_feedback(parsed_user_move, history) → dict`

Evaluates the user's move against negotiation theory and returns coaching feedback.

**Input**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `parsed_user_move` | `dict` | ✓ | Output of `parse_move()` |
| `history` | `list[dict]` | ✓ | Full conversation including current user turn |

**Output**

```python
{
    "strengths":   ["Anchored high at $95K before first concession"],
    "weaknesses":  ["Revealed competing-bid value ($85K) — caps leverage"],
    "suggestion":  "On the next turn, withhold the exact competing number and only confirm an offer exists.",
    "concept_tag": "information_disclosure",
}
```

**`concept_tag` values:** `anchoring` · `concession_pacing` · `batna_signaling` ·
`reciprocity` · `information_disclosure` · `framing` · `walk_away_credibility`

**Errors & fallbacks**

| Condition | Behaviour |
|-----------|-----------|
| `parsed_user_move` not a dict | Raises `TypeError` |
| `history` not a list | Raises `TypeError` |
| LLM unavailable | Returns a random entry from a curated fallback pool; always valid schema |
| LLM returns malformed JSON | Returns safe default with `concept_tag: "anchoring"` |

---

### `score_session(history, hidden_context=None, outcome="deal_closed", final_deal_value=None, user_brief=None, llm=None) → dict`

Computes the user's end-of-session performance score.

**Input**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `history` | `list[dict]` | ✓ | Complete conversation; user turns may have `"critic_feedback"` key |
| `hidden_context` | `dict \| None` | — | Reserved; pass `None` |
| `outcome` | `str` | — | `"deal_closed"` · `"walked_away"` · `"timeout"` |
| `final_deal_value` | `float \| None` | — | Agreed value if deal closed |
| `user_brief` | `dict \| None` | — | `{"target": float, "batna": float}` |
| `llm` | `LLMRouter \| None` | — | For best/worst move identification |

**Output**

```python
{
    "score":      72,
    "rating":     "Good",
    "best_move":  {"turn": 2, "summary": "Bundled relocation demand", "reason": "Expanded the negotiation to a multi-issue deal, creating room for mutual gain."},
    "worst_move": {"turn": 4, "summary": "Accepted without final push", "reason": "Accepted the first bundled offer without testing whether one more ask was possible."},
}
```

**Rating thresholds:** `Poor` (0–39) · `Fair` (40–59) · `Good` (60–79) · `Excellent` (80–100)

**Scoring formula**

- **Outcome quality (50 pts):** Did the deal close? Was the value above BATNA?
  Close to target? Requires `outcome`, `final_deal_value`, and `user_brief`.
- **Move quality (50 pts):** Average of per-turn `critic_feedback` strength/weakness
  ratios from `history`. Falls back to text heuristics if no feedback is embedded.

When `user_brief` / `final_deal_value` are absent, only move quality is scored
and the result is scaled to `[0, 100]`.

**Errors & fallbacks**

| Condition | Behaviour |
|-----------|-----------|
| `history` not a list | Raises `TypeError` |
| `history` is empty | Raises `ValueError` |
| Any internal error | Returns `{"score": 50, "rating": "Fair", "best_move": {...}, "worst_move": {...}}` with error logged |

---

## Per-turn pipeline order

```
user_message
    │
    ▼
parse_move(user_message, history)
    → parsed_move
    │
    ▼
get_strategic_action(state_vector)
    → action
    │
    ├──► generate_opponent_response(action, hidden_ctx, history, parsed_move)
    │       → opponent_reply  (send to frontend)
    │
    └──► get_critic_feedback(parsed_move, history)
            → feedback  (show in sidebar / store on history entry)
```

At session end:

```
score_session(history, outcome=..., final_deal_value=..., user_brief=...)
    → score_result  (show on results page)
```

---

## Logging

All agents log at `INFO` level. Set your logging config to see LLM latency:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Sample output:

```
INFO  move_parser: provider=gemini model=gemini-2.0-flash latency=0.84s
INFO  opponent: provider=gemini model=gemini-2.0-flash action=Concede Small latency=1.12s
INFO  critic: provider=gemini model=gemini-2.0-flash latency=0.97s
WARNING  parse_move: LLM unavailable (HTTP 429) — heuristic fallback.
```
