'use client';

import { getLlmStatus, LlmEvent, LlmStatus } from '@/lib/api';
import { useEffect, useRef, useState } from 'react';

// ── Colour helpers ─────────────────────────────────────────────────────────────

const EVENT_COLORS: Record<string, string> = {
  success:    '#34d399',   // green
  rate_limit: '#f87171',   // red
  error:      '#f87171',
  fallback:   '#fbbf24',   // amber
};

const PROVIDER_COLORS: Record<string, string> = {
  gemini: '#a5b8fd',
  ollama: '#34d399',
  system: '#fbbf24',
};

function eventColor(event: string)    { return EVENT_COLORS[event]    ?? '#8888aa'; }
function providerColor(p: string)     { return PROVIDER_COLORS[p]     ?? '#8888aa'; }

// ── Stat cell ──────────────────────────────────────────────────────────────────

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <span className="text-[11px]" style={{ color: '#5a5a7a' }}>{label}</span>
      <span className="text-[11px] font-mono font-semibold" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

// ── Event log row ──────────────────────────────────────────────────────────────

function EventRow({ ev }: { ev: LlmEvent }) {
  return (
    <div className="flex items-start gap-2 py-[3px]">
      <span className="text-[10px] font-mono shrink-0" style={{ color: '#3a3a5a' }}>
        {ev.ts}
      </span>
      <span
        className="text-[10px] font-mono font-semibold shrink-0 w-12"
        style={{ color: providerColor(ev.provider) }}
      >
        [{ev.provider.slice(0, 6)}]
      </span>
      <span
        className="text-[10px] font-mono shrink-0 w-16"
        style={{ color: eventColor(ev.event) }}
      >
        {ev.event}
      </span>
      {ev.detail && (
        <span className="text-[10px] font-mono truncate" style={{ color: '#44446a' }}>
          {ev.detail}
        </span>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function LlmTerminal() {
  const [open, setOpen]         = useState(false);
  const [stats, setStats]       = useState<LlmStatus | null>(null);
  const [error, setError]       = useState(false);
  const [blink, setBlink]       = useState(false);
  const logRef                  = useRef<HTMLDivElement>(null);
  const prevEventCount          = useRef(0);
  const intervalRef             = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch on open + poll every 3 s while open
  useEffect(() => {
    const fetch = () => {
      getLlmStatus()
        .then((s) => {
          setStats(s);
          setError(false);
          // Blink indicator when new events arrive
          if (s.recent_events.length > prevEventCount.current) {
            prevEventCount.current = s.recent_events.length;
            setBlink(true);
            setTimeout(() => setBlink(false), 600);
          }
        })
        .catch(() => setError(true));
    };

    fetch();
    intervalRef.current = setInterval(fetch, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Auto-scroll log to bottom when new events arrive
  useEffect(() => {
    if (open && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [stats?.recent_events.length, open]);

  const isFallback = stats?.is_using_fallback ?? false;
  const hasRateLimit = (stats?.gemini.rate_limits ?? 0) > 0;

  // Dot colour for the toggle button
  const dotColor = error
    ? '#f87171'
    : isFallback
    ? '#fbbf24'
    : hasRateLimit
    ? '#fbbf24'
    : '#34d399';

  const providerLabel = stats
    ? (stats.current_provider === 'gemini' ? 'Gemini' : 'Ollama (fallback)')
    : '…';

  return (
    <>
      {/* ── Toggle button ────────────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen((v) => !v)}
        title="LLM usage stats"
        className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-3 py-2 rounded-xl
          border border-white/[0.10] bg-black/70 backdrop-blur-md
          text-[11px] font-mono font-semibold text-white/60
          hover:text-white/90 hover:border-white/20 transition-all"
        style={{ boxShadow: open ? `0 0 16px ${dotColor}30` : undefined }}
      >
        {/* Animated dot */}
        <span
          className="w-2 h-2 rounded-full shrink-0 transition-colors duration-300"
          style={{
            background: dotColor,
            boxShadow: `0 0 6px ${dotColor}`,
            animation: blink ? 'pulse 0.3s ease-in-out' : undefined,
          }}
        />
        <span className="font-mono text-[10px] tracking-widest">
          &gt;_ LLM
        </span>
        <span
          className="text-[10px] px-1.5 py-0.5 rounded-md font-semibold"
          style={{
            background: isFallback ? 'rgba(251,191,36,0.15)' : 'rgba(52,211,153,0.12)',
            color: isFallback ? '#fbbf24' : '#34d399',
            border: `1px solid ${isFallback ? 'rgba(251,191,36,0.3)' : 'rgba(52,211,153,0.25)'}`,
          }}
        >
          {stats?.current_provider?.toUpperCase() ?? '…'}
        </span>
      </button>

      {/* ── Terminal panel ───────────────────────────────────────────────────── */}
      <div
        className="fixed bottom-16 right-4 z-50 w-[420px] max-w-[calc(100vw-2rem)]
          rounded-2xl border border-white/[0.08] overflow-hidden
          transition-all duration-300 ease-in-out"
        style={{
          background: 'rgba(6,6,16,0.96)',
          backdropFilter: 'blur(24px)',
          boxShadow: '0 24px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)',
          opacity: open ? 1 : 0,
          transform: open ? 'translateY(0) scale(1)' : 'translateY(12px) scale(0.97)',
          pointerEvents: open ? 'auto' : 'none',
        }}
      >
        {/* Title bar */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06]">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-[#f87171]/70" />
            <div className="w-3 h-3 rounded-full bg-[#fbbf24]/70" />
            <div className="w-3 h-3 rounded-full bg-[#34d399]/70" />
          </div>
          <span className="flex-1 text-center text-[11px] font-mono text-white/30 tracking-wider">
            parleylab — llm usage monitor
          </span>
          <button
            onClick={() => setOpen(false)}
            className="text-white/20 hover:text-white/60 text-xs leading-none"
          >
            ✕
          </button>
        </div>

        {error ? (
          <div className="px-4 py-6 text-center">
            <p className="text-[11px] font-mono text-[#f87171]">
              ✗ backend unreachable
            </p>
            <p className="text-[10px] text-white/20 mt-1">
              Is the server running on port 8000?
            </p>
          </div>
        ) : !stats ? (
          <div className="px-4 py-6 text-center">
            <p className="text-[11px] font-mono" style={{ color: '#34d399' }}>
              $ fetching stats…
            </p>
          </div>
        ) : (
          <div className="px-4 pt-3 pb-4 space-y-3">

            {/* Fallback banner */}
            {isFallback && (
              <div className="px-3 py-2 rounded-xl border border-[#fbbf24]/30 bg-[#fbbf24]/05">
                <p className="text-[11px] font-mono text-[#fbbf24]">
                  ⚠ Gemini rate-limited — running on Ollama (phi3:latest)
                </p>
              </div>
            )}

            {/* Active provider row */}
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-widest text-white/25">
                active provider
              </span>
              <span
                className="text-[11px] font-mono font-bold"
                style={{ color: isFallback ? '#fbbf24' : '#34d399' }}
              >
                {providerLabel}
                {stats.fallback_count > 0 && (
                  <span className="text-[10px] text-white/25 ml-2">
                    ({stats.fallback_count}× fallback)
                  </span>
                )}
              </span>
            </div>

            {/* Counters grid */}
            <div className="grid grid-cols-2 gap-3">
              {/* Gemini column */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <p
                  className="text-[10px] font-mono font-bold uppercase tracking-widest mb-2"
                  style={{ color: '#a5b8fd' }}
                >
                  Gemini
                </p>
                <Stat label="requests"    value={stats.gemini.requests}    color="#a5b8fd" />
                <Stat label="successes"   value={stats.gemini.successes}   color="#34d399" />
                <Stat label="rate limits" value={stats.gemini.rate_limits} color="#f87171" />
                <Stat label="errors"      value={stats.gemini.errors}      color="#f87171" />
              </div>

              {/* Ollama column */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <p
                  className="text-[10px] font-mono font-bold uppercase tracking-widest mb-2"
                  style={{ color: '#34d399' }}
                >
                  Ollama
                </p>
                <Stat label="requests"  value={stats.ollama.requests}  color="#34d399" />
                <Stat label="successes" value={stats.ollama.successes} color="#34d399" />
                <Stat label="errors"    value={stats.ollama.errors}    color="#f87171" />
              </div>
            </div>

            {/* Event log */}
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-white/20 mb-1.5">
                event log
              </p>
              <div
                ref={logRef}
                className="rounded-xl border border-white/[0.05] bg-black/40 px-3 py-2 h-40 overflow-y-auto"
                style={{ scrollbarWidth: 'thin' }}
              >
                {stats.recent_events.length === 0 ? (
                  <p className="text-[10px] font-mono text-white/20 py-2 text-center">
                    no events yet — waiting for LLM calls…
                  </p>
                ) : (
                  [...stats.recent_events].reverse().map((ev, i) => (
                    <EventRow key={i} ev={ev} />
                  ))
                )}
              </div>
            </div>

            {/* Footer */}
            <p className="text-[9px] font-mono text-white/15 text-right">
              auto-refresh every 3s · {new Date().toLocaleTimeString()}
            </p>
          </div>
        )}
      </div>
    </>
  );
}
