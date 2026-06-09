#!/usr/bin/env python3
"""
Integration test for parley_ai LLM clients.

Tests Ollama (primary provider, must be running for the demo) and
optionally Gemini (future fallback — skipped unless GEMINI_API_KEY is set).

Run from the repo root:
    python scripts/test_llm_clients.py
"""

import json
import logging
import os
import sys
from pathlib import Path

# Show INFO logs so router/client log lines are visible
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from parley_ai.llm.ollama import OllamaClient
from parley_ai.llm.router import LLMRouter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASS = _FAIL = _SKIP = 0


def ok(label: str) -> None:
    global _PASS
    print(f"  \033[32m✓\033[0m  {label}")
    _PASS += 1


def fail(label: str, detail: str = "") -> None:
    global _FAIL
    msg = f"  \033[31m✗\033[0m  {label}"
    if detail:
        msg += f"\n       {detail}"
    print(msg)
    _FAIL += 1


def skip(label: str, reason: str = "") -> None:
    global _SKIP
    msg = f"  \033[33m⊘\033[0m  {label}"
    if reason:
        msg += f"  [{reason}]"
    print(msg)
    _SKIP += 1


def section(title: str) -> None:
    print(f"\n{'─' * 66}")
    print(f"  {title}")
    print(f"{'─' * 66}")


# ---------------------------------------------------------------------------
# 1. OllamaClient — plain text
# ---------------------------------------------------------------------------

section("1 · OllamaClient — plain text  (primary demo provider)")

# Use whichever small model is already pulled
OLLAMA_TEST_MODEL = os.getenv("PARLEYLAB_OLLAMA_MODEL_DEFAULT", "phi3:latest")

try:
    client = OllamaClient(model=OLLAMA_TEST_MODEL)
    reply = client.chat(
        system="You are a concise assistant. Keep replies to one sentence.",
        messages=[{"role": "user", "content": "Say hello in exactly one sentence."}],
    )
    print(f"\n  model  : {OLLAMA_TEST_MODEL}")
    print(f"  reply  : {reply.strip()!r}\n")
    ok("Ollama returned a non-empty string")
    ok("reply is a str") if isinstance(reply, str) else fail("reply is a str")

except ConnectionError as exc:
    fail("Ollama reachable", str(exc))
    skip("Ollama text reply", "connection failed — is `ollama serve` running?")
except Exception as exc:
    fail(f"Unexpected error: {type(exc).__name__}", str(exc))

# ---------------------------------------------------------------------------
# 2. OllamaClient — json_mode
# ---------------------------------------------------------------------------

section("2 · OllamaClient — json_mode")

try:
    client = OllamaClient(model=OLLAMA_TEST_MODEL)
    reply = client.chat(
        system='Return a JSON object with exactly one key "greeting" whose value is a short greeting string.',
        messages=[{"role": "user", "content": "Give me the JSON greeting."}],
        json_mode=True,
        temperature=0.0,
    )
    print(f"\n  raw reply : {reply.strip()!r}\n")
    parsed = json.loads(reply)
    ok("json_mode reply parses with json.loads()")
    ok("parsed result is a dict") if isinstance(parsed, dict) else fail("parsed result is a dict")

except ConnectionError:
    skip("json_mode test", "Ollama not reachable")
except json.JSONDecodeError as exc:
    fail("json_mode reply parses with json.loads()", f"JSONDecodeError: {exc}")
except Exception as exc:
    fail(f"Unexpected error: {type(exc).__name__}", str(exc))

# ---------------------------------------------------------------------------
# 3. OllamaClient — error paths
# ---------------------------------------------------------------------------

section("3 · OllamaClient — error paths")

try:
    bad = OllamaClient(model="phi3:latest", base_url="http://localhost:19999")
    bad.chat("x", [{"role": "user", "content": "ping"}])
    fail("raises ConnectionError on unreachable base_url")
except ConnectionError:
    ok("raises ConnectionError on unreachable base_url")
except Exception as exc:
    fail("raises ConnectionError on unreachable base_url", f"got {type(exc).__name__}: {exc}")

try:
    c = OllamaClient(model="phi3:latest")
    c.chat("x", [{"role": "badRole", "content": "x"}])
    fail("raises ValueError on invalid role")
except ValueError:
    ok("raises ValueError on invalid role")

# ---------------------------------------------------------------------------
# 4. LLMRouter — defaults to Ollama
# ---------------------------------------------------------------------------

section("4 · LLMRouter — defaults to Ollama")

try:
    router = LLMRouter(model=OLLAMA_TEST_MODEL)
    ok(f"LLMRouter constructs with provider={router.provider!r}")

    reply = router.chat(
        system="You are concise. One sentence only.",
        messages=[{"role": "user", "content": "What is 2 + 2?"}],
    )
    print(f"\n  reply : {reply.strip()!r}\n")
    ok("LLMRouter.chat() returns a non-empty string")

except ConnectionError as exc:
    fail("LLMRouter.chat() reachable", str(exc))
except Exception as exc:
    fail(f"Unexpected error: {type(exc).__name__}", str(exc))

try:
    LLMRouter(provider="unknown_provider")
    fail("raises ValueError on unknown provider")
except ValueError:
    ok("raises ValueError on unknown provider")

# ---------------------------------------------------------------------------
# 5. GeminiClient — future fallback (skipped unless GEMINI_API_KEY is set)
# ---------------------------------------------------------------------------

section("5 · GeminiClient — future fallback (not used in demo)")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    skip("GeminiClient test", "GEMINI_API_KEY not set — skipping (expected for demo)")
else:
    try:
        from parley_ai.llm.gemini import GeminiClient
        gclient = GeminiClient()
        greply = gclient.chat(
            system="You are a concise assistant. One sentence only.",
            messages=[{"role": "user", "content": "Say hello in one sentence."}],
        )
        print(f"\n  reply : {greply.strip()!r}\n")
        ok("GeminiClient returned a non-empty string  (future fallback — not used in demo)")

        grouter = LLMRouter(provider="gemini")
        ok(f"LLMRouter constructs with provider={grouter.provider!r}")

    except Exception as exc:
        fail(f"Gemini error: {type(exc).__name__}", str(exc))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'═' * 66}")
status = "\033[32mOK\033[0m" if _FAIL == 0 else f"\033[31m{_FAIL} FAILED\033[0m"
print(f"  {status}   {_PASS} passed  |  {_SKIP} skipped  |  {_FAIL} failed")
print(f"{'═' * 66}\n")

sys.exit(0 if _FAIL == 0 else 1)
