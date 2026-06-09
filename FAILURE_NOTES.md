# FAILURE_NOTES — Quality Test Known Issues

Last updated: 2026-06-09
Test suite: `scripts/quality_test.py` (15 cases, target ≥ 14/15)

---

## LLM Provider Notes

### Gemini (production provider)
- **Free-tier rate limit (429)**: The free tier allows ~15 RPM. Running all 15
  quality-test cases in sequence with only 0.6 s between calls exceeds this.
  A 429 causes a `ConnectionError` and the test is skipped, not failed.
  **Mitigation**: Run during off-peak hours, or use
  `PARLEYLAB_LLM_PROVIDER=ollama` locally.

### Ollama (local test provider)
- **Model cold-start**: The first request after Ollama is idle takes 20–40 s
  for model loading. The quality test now runs a warmup call before the
  timed cases to absorb this.
- **qwen3:4b** uses chain-of-thought (thinking tokens) and can exceed the
  60–90 s timeout even on non-trivial prompts. Use phi3 or mistral for
  time-bounded tests.
- **mistral:latest (7.2 B)** generates quality responses but requires 90+ s
  per call on this hardware. Use `PARLEYLAB_OLLAMA_TIMEOUT=120` if preferred.
- **phi3:latest (3.8 B)** is the reliable local test model. All prior
  test suites (35/35 stub tests, opponent/critic/parser scripts) were
  validated against phi3.

---

## Persistent Prompt Limitations (per agent)

### Move Parser

| Case | Status | Notes |
|------|--------|-------|
| Implicit range ("high 80s") | Usually passes | phi3 sometimes returns `offered_value=null` instead of ~88 000 — both are acceptable under the current check |
| Stall signal ("have to think") | Usually passes | May be classified as `walk_away` instead of `signal`; both are accepted |
| Aggressive ultimatum ("100K or I'm out") | Usually passes | phi3 sometimes returns `opening_anchor` instead of `bluff`; both are accepted if `tone=aggressive` and `offered_value=100000` |

**Root cause**: Small models (phi3, 3.8 B) are poor at distinguishing
`bluff` vs `opening_anchor` when both a number and an ultimatum appear in
the same message. The added examples in the system prompt improve this
but do not eliminate the ambiguity at 3.8 B.

### Opponent Agent

| Case | Status | Notes |
|------|--------|-------|
| Concede Small / Concede Large | Fixed | Used to fail because the LLM fallback template didn't include the offer number. Now the `_build_fallback()` helper embeds it. LLM path improved by stronger `REQUIRED: MUST state the number` instruction |
| Walk Away | Reliable | Fallback and LLM path both produce natural ending language |

**Known edge case**: When `current_offer` is `None` (orchestrator didn't
calculate a specific counter-value) and the action is Concede Small/Large,
both LLM and fallback produce vague phrasing like "I can stretch a touch"
without a number. This is correct behaviour — the orchestrator is
responsible for computing and passing a concrete offer when conceding.

### Critic Agent

| Case | Status | Notes |
|------|--------|-------|
| Generic feedback | Partially mitigated | Updated prompt adds BAD/GOOD examples. phi3 still occasionally outputs concept-name strings as strengths (e.g. `"anchoring"`) rather than quoted user behaviour. Gemini does not have this issue |
| BATNA disclosure | Usually passes | phi3 may mention "80,000" in strengths rather than weaknesses; Gemini flags it correctly |

**Root cause**: phi3 (3.8 B) doesn't reliably follow complex multi-part
instructions. The BAD/GOOD counter-examples help but don't guarantee
specific-over-generic output at this model size.

---

## What Taanush Should Expect at Integration Time

1. **Use Gemini in production** — all prompt design targets Gemini Flash.
   phi3 is only for local, offline development.

2. **Opponent Concede moves**: The orchestrator MUST pass
   `hidden_context["current_offer"]` (the specific numeric value for this
   turn) for Concede Small/Large. If it is omitted, the opponent reply
   will not state a number.

3. **Critic specificity**: On Gemini, the critic references exact numbers
   and quoted user phrases. On phi3, expect occasional concept-name
   strings in the `strengths`/`weaknesses` lists. The schema is always
   valid; only the phrasing quality degrades.

4. **Walk-away credibility**: The critic's `walk_away_credibility` tag
   fires when the user issues a threat without backing it up. This
   requires the critic to see prior context (history). Passing a
   single-turn history (no prior context) will cause the critic to
   evaluate the move in isolation and may under-penalise unsubstantiated
   threats.
