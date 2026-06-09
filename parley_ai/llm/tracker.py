"""Thread-safe in-process LLM usage tracker.

A module-level singleton records every Gemini and Ollama call made during
the process lifetime. The backend status endpoint reads it; the router
writes to it on every chat() call.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class LlmEvent:
    ts: str
    provider: str
    event: str     # "success" | "error" | "rate_limit" | "fallback"
    detail: str = ""


class _LlmTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current_provider: str = "gemini"
        self.is_using_fallback: bool = False
        self.fallback_count: int = 0
        # Gemini counters
        self.gemini_requests: int = 0
        self.gemini_successes: int = 0
        self.gemini_rate_limits: int = 0
        self.gemini_errors: int = 0
        # Ollama counters
        self.ollama_requests: int = 0
        self.ollama_successes: int = 0
        self.ollama_errors: int = 0
        self._events: List[LlmEvent] = []

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S")

    def _push(self, provider: str, event: str, detail: str = "") -> None:
        self._events.append(LlmEvent(ts=self._now(), provider=provider, event=event, detail=detail))
        if len(self._events) > 50:
            self._events = self._events[-50:]

    # ── Gemini ────────────────────────────────────────────────────────────────────

    def gemini_started(self) -> None:
        with self._lock:
            self.gemini_requests += 1

    def gemini_ok(self) -> None:
        with self._lock:
            self.gemini_successes += 1
            self._push("gemini", "success")

    def gemini_rate_limited(self, detail: str = "") -> None:
        with self._lock:
            self.gemini_rate_limits += 1
            self.gemini_errors += 1
            self._push("gemini", "rate_limit", detail[:120])

    def gemini_failed(self, detail: str = "") -> None:
        with self._lock:
            self.gemini_errors += 1
            self._push("gemini", "error", detail[:120])

    def switched_to_ollama(self, reason: str = "") -> None:
        with self._lock:
            self.fallback_count += 1
            self.is_using_fallback = True
            self.current_provider = "ollama"
            self._push("system", "fallback", f"→ ollama: {reason[:80]}")

    # ── Ollama ────────────────────────────────────────────────────────────────────

    def ollama_started(self) -> None:
        with self._lock:
            self.ollama_requests += 1

    def ollama_ok(self) -> None:
        with self._lock:
            self.ollama_successes += 1
            self._push("ollama", "success")

    def ollama_failed(self, detail: str = "") -> None:
        with self._lock:
            self.ollama_errors += 1
            self._push("ollama", "error", detail[:120])

    # ── Snapshot ──────────────────────────────────────────────────────────────────

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_provider": self.current_provider,
                "is_using_fallback": self.is_using_fallback,
                "fallback_count": self.fallback_count,
                "gemini": {
                    "requests": self.gemini_requests,
                    "successes": self.gemini_successes,
                    "rate_limits": self.gemini_rate_limits,
                    "errors": self.gemini_errors,
                },
                "ollama": {
                    "requests": self.ollama_requests,
                    "successes": self.ollama_successes,
                    "errors": self.ollama_errors,
                },
                "recent_events": [
                    {"ts": e.ts, "provider": e.provider, "event": e.event, "detail": e.detail}
                    for e in self._events[-20:]
                ],
            }


_tracker = _LlmTracker()


def get_tracker() -> _LlmTracker:
    return _tracker
