'use client';

import { CriticFeedback } from '@/lib/api';
import {
  AlertTriangle,
  CheckCircle,
  Lightbulb,
  Tag,
  TrendingUp,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

// ── Concept taxonomy ───────────────────────────────────────────────────────────

const CONCEPT_META: Record<
  string,
  { label: string; color: string; bg: string; border: string; glow: string }
> = {
  anchoring:           { label: 'Anchoring',          color: '#a5b8fd', bg: 'rgba(100,112,243,0.12)', border: 'rgba(100,112,243,0.30)', glow: 'rgba(100,112,243,0.20)' },
  batna_awareness:     { label: 'BATNA Awareness',    color: '#fcd34d', bg: 'rgba(251,191,36,0.12)',  border: 'rgba(251,191,36,0.30)',  glow: 'rgba(251,191,36,0.15)'  },
  concession_pacing:   { label: 'Concession Pacing',  color: '#5eead4', bg: 'rgba(20,184,166,0.12)', border: 'rgba(20,184,166,0.30)',  glow: 'rgba(20,184,166,0.15)'  },
  reciprocity:         { label: 'Reciprocity',         color: '#c084fc', bg: 'rgba(192,132,252,0.12)',border: 'rgba(192,132,252,0.30)', glow: 'rgba(192,132,252,0.15)' },
  information_control: { label: 'Info Control',        color: '#67e8f9', bg: 'rgba(6,182,212,0.12)',  border: 'rgba(6,182,212,0.30)',   glow: 'rgba(6,182,212,0.15)'   },
  bundling:            { label: 'Bundling',            color: '#86efac', bg: 'rgba(34,197,94,0.12)',  border: 'rgba(34,197,94,0.30)',   glow: 'rgba(34,197,94,0.15)'   },
  silence:             { label: 'Strategic Silence',   color: '#94a3b8', bg: 'rgba(100,116,139,0.12)',border: 'rgba(100,116,139,0.30)', glow: 'rgba(100,116,139,0.15)' },
  deadline_pressure:   { label: 'Deadline Pressure',  color: '#fca5a5', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.30)',   glow: 'rgba(239,68,68,0.15)'   },
};

const FALLBACK = CONCEPT_META['anchoring'];

// ── Feedback row ───────────────────────────────────────────────────────────────

function FeedbackRow({
  icon,
  text,
  color,
  delay = 0,
}: {
  icon: React.ReactNode;
  text: string;
  color: string;
  delay?: number;
}) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  return (
    <div
      className="flex items-start gap-2.5 transition-all duration-300"
      style={{
        opacity: show ? 1 : 0,
        transform: show ? 'translateX(0)' : 'translateX(-8px)',
      }}
    >
      <span className="shrink-0 mt-0.5">{icon}</span>
      <p className="text-xs leading-relaxed" style={{ color }}>
        {text}
      </p>
    </div>
  );
}

// ── CriticPanel ────────────────────────────────────────────────────────────────

interface Props {
  feedback: CriticFeedback;
  turn: number;
}

/**
 * Polished coaching panel with:
 * - Slide-in from right on mount
 * - Concept tag with matched colour theme + glow
 * - Staggered row reveal for strengths / weaknesses / suggestion
 * - Animated score bar showing strengths vs weaknesses ratio
 */
export function CriticPanel({ feedback, turn }: Props) {
  const meta = CONCEPT_META[feedback.concept_tag] ?? FALLBACK;
  const [mounted, setMounted] = useState(false);

  const strengthCount  = feedback.strengths.length;
  const weaknessCount  = feedback.weaknesses.length;
  const total          = strengthCount + weaknessCount || 1;
  const strengthPct    = Math.round((strengthCount / total) * 100);

  useEffect(() => {
    const t = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(t);
  }, []);

  return (
    <div
      className="rounded-xl overflow-hidden transition-all duration-400"
      style={{
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateX(0)' : 'translateX(16px)',
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${meta.border}`,
        boxShadow: `0 0 20px ${meta.glow}`,
        transition: 'all 0.35s cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      {/* Accent top stripe */}
      <div
        className="h-0.5 w-full"
        style={{ background: `linear-gradient(90deg, ${meta.color}, transparent)` }}
      />

      <div className="p-4 space-y-4">

        {/* ── Header ────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="w-1.5 h-1.5 rounded-full animate-pulse"
              style={{ background: meta.color }}
            />
            <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">
              Coach · Turn {turn}
            </span>
          </div>

          {/* Concept chip */}
          <span
            className="inline-flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest
              px-2.5 py-1 rounded-full border"
            style={{
              background: meta.bg,
              borderColor: meta.border,
              color: meta.color,
            }}
          >
            <Tag className="w-2.5 h-2.5" />
            {meta.label}
          </span>
        </div>

        {/* ── Strength vs weakness bar ──────────────────────────────── */}
        <div>
          <div className="flex justify-between text-[9px] text-white/25 mb-1">
            <span>{strengthCount} strength{strengthCount !== 1 ? 's' : ''}</span>
            <span>{weaknessCount} to improve</span>
          </div>
          <div className="h-1 rounded-full bg-white/[0.05] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700 ease-out"
              style={{
                width: mounted ? `${strengthPct}%` : '0%',
                background: `linear-gradient(90deg, #34d399, ${meta.color})`,
              }}
            />
          </div>
        </div>

        {/* ── Strengths ────────────────────────────────────────────── */}
        {feedback.strengths.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <CheckCircle className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] font-semibold text-emerald-400 uppercase tracking-widest">
                Strengths
              </span>
            </div>
            {feedback.strengths.map((s, i) => (
              <FeedbackRow
                key={i}
                icon={<span className="w-1 h-1 rounded-full bg-emerald-400/60 mt-1.5 block" />}
                text={s}
                color="rgba(110,231,183,0.85)"
                delay={80 + i * 60}
              />
            ))}
          </div>
        )}

        {/* ── Weaknesses ───────────────────────────────────────────── */}
        {feedback.weaknesses.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3 text-amber-400" />
              <span className="text-[10px] font-semibold text-amber-400 uppercase tracking-widest">
                To Improve
              </span>
            </div>
            {feedback.weaknesses.map((w, i) => (
              <FeedbackRow
                key={i}
                icon={<span className="w-1 h-1 rounded-full bg-amber-400/60 mt-1.5 block" />}
                text={w}
                color="rgba(252,211,77,0.80)"
                delay={200 + i * 60}
              />
            ))}
          </div>
        )}

        {/* ── Suggestion ───────────────────────────────────────────── */}
        {feedback.suggestion && (
          <div
            className="rounded-lg px-3 py-2.5 mt-1"
            style={{ background: `${meta.bg}`, borderLeft: `2px solid ${meta.color}` }}
          >
            <div className="flex items-start gap-2">
              <Lightbulb className="w-3.5 h-3.5 shrink-0 mt-0.5" style={{ color: meta.color }} />
              <p className="text-xs leading-relaxed text-white/60">
                <span className="font-semibold text-white/80">Next move: </span>
                {feedback.suggestion}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
