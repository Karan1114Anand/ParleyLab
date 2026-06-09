'use client';

import { Performance, OpponentHidden, TranscriptMessage } from '@/lib/api';
import {
  Award, Bot, CheckCircle, Eye, MessageSquare,
  ThumbsDown, ThumbsUp, User, XCircle, Zap,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

// ── Types ──────────────────────────────────────────────────────────────────────

interface Props {
  outcome: string;
  finalDealValue: number | null;
  opponentHidden: OpponentHidden;
  performance: Performance;
  transcript: TranscriptMessage[];
  valueUnit: string;
  userRole?: string;
  opponentRole?: string;
  openingOffer?: number;
  userTarget?: number;
  userBatna?: number;
}

// ── Outcome config ─────────────────────────────────────────────────────────────

const OUTCOME_CFG = {
  deal_closed: {
    emoji: '🤝', label: 'Deal Closed!',
    color: '#34d399', bg: 'rgba(52,211,153,0.08)', border: 'rgba(52,211,153,0.25)',
    sub: 'A deal was reached. Review your negotiation below.',
  },
  walked_away: {
    emoji: '🚶', label: 'Opponent Walked Away',
    color: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.25)',
    sub: 'No agreement was reached. See what you could improve.',
  },
  timeout: {
    emoji: '⏱️', label: 'Time Expired',
    color: '#fbbf24', bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.25)',
    sub: 'The negotiation ran out of turns.',
  },
};

const RATING_CFG: Record<string, { color: string; label: string }> = {
  Excellent: { color: '#34d399', label: 'Master Negotiator' },
  Good:      { color: '#6470f3', label: 'Skilled Negotiator' },
  Average:   { color: '#fbbf24', label: 'Developing Negotiator' },
  'Needs Work': { color: '#f87171', label: 'Negotiation Apprentice' },
};

// ── Animated counter ───────────────────────────────────────────────────────────

function AnimatedNumber({ target, duration = 1200 }: { target: number; duration?: number }) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let start: number | null = null;
    const step = (ts: number) => {
      if (!start) start = ts;
      const pct = Math.min((ts - start) / duration, 1);
      // easeOutCubic
      const ease = 1 - Math.pow(1 - pct, 3);
      setValue(Math.round(ease * target));
      if (pct < 1) requestAnimationFrame(step);
    };
    const id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [target, duration]);
  return <>{value}</>;
}

// ── Score ring ─────────────────────────────────────────────────────────────────

function ScoreRing({ score, rating }: { score: number; rating: string }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const [offset, setOffset] = useState(circ);
  const rcfg = RATING_CFG[rating] ?? RATING_CFG['Average'];

  useEffect(() => {
    const t = setTimeout(() => setOffset(circ - (score / 100) * circ), 300);
    return () => clearTimeout(t);
  }, [score, circ]);

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative w-40 h-40">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" />
          <circle
            cx="60" cy="60" r={r} fill="none"
            stroke="url(#scoreGrad)"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1.4s cubic-bezier(0.4,0,0.2,1)' }}
          />
          <defs>
            <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6470f3" />
              <stop offset="100%" stopColor="#c084fc" />
            </linearGradient>
          </defs>
        </svg>
        {/* Glow behind ring */}
        <div
          className="absolute inset-0 rounded-full blur-xl opacity-30 pointer-events-none"
          style={{ background: `radial-gradient(circle, ${rcfg.color}, transparent 70%)` }}
        />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-black text-white font-mono tabular-nums">
            <AnimatedNumber target={score} />
          </span>
          <span className="text-xs text-white/30 mt-0.5">/ 100</span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-lg font-bold" style={{ color: rcfg.color }}>{rating}</p>
        <p className="text-xs text-white/35 mt-0.5">{rcfg.label}</p>
      </div>
    </div>
  );
}

// ── Animated bar ───────────────────────────────────────────────────────────────

function AnimatedBar({
  label, value, max, color, delay = 0,
}: { label: string; value: number; max: number; color: string; delay?: number }) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setWidth((value / Math.max(max, 1)) * 100), delay);
    return () => clearTimeout(t);
  }, [value, max, delay]);

  return (
    <div>
      <div className="flex justify-between items-baseline mb-1.5">
        <span className="text-xs text-white/50">{label}</span>
        <span className="text-xs font-mono font-semibold text-white/80">
          {value.toLocaleString()}
        </span>
      </div>
      <div className="h-2 bg-white/[0.05] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${width}%`, background: color }}
        />
      </div>
    </div>
  );
}

// ── Section header ─────────────────────────────────────────────────────────────

function SectionHeader({ icon, label, sub }: { icon: React.ReactNode; label: string; sub?: string }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="w-8 h-8 rounded-lg bg-white/[0.05] border border-white/[0.07] flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-white">{label}</p>
        {sub && <p className="text-xs text-white/30 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function PerformanceScore({
  outcome,
  finalDealValue,
  opponentHidden,
  performance,
  transcript,
  valueUnit,
  userRole,
  opponentRole,
  openingOffer,
  userTarget,
  userBatna,
}: Props) {
  const cfg = OUTCOME_CFG[outcome as keyof typeof OUTCOME_CFG] ?? OUTCOME_CFG.timeout;
  const score = performance.score ?? 0;
  const [showTranscript, setShowTranscript] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  // Offer range analytics
  const maxOffer = Math.max(
    openingOffer ?? 0,
    opponentHidden.target,
    opponentHidden.batna,
    userTarget ?? 0,
    userBatna ?? 0,
    finalDealValue ?? 0,
  );

  return (
    <div className="space-y-6 animate-fade-up">

      {/* ── 1. Outcome banner ─────────────────────────────────────────────────── */}
      <div
        className="rounded-2xl p-6 text-center relative overflow-hidden"
        style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
      >
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: `radial-gradient(ellipse 80% 60% at 50% 0%, ${cfg.color}15, transparent)` }}
        />
        <div className="relative">
          <div className="text-5xl mb-3">{cfg.emoji}</div>
          <h2 className="text-2xl font-extrabold" style={{ color: cfg.color }}>{cfg.label}</h2>
          <p className="text-sm text-white/40 mt-1">{cfg.sub}</p>
          {finalDealValue !== null && (
            <div
              className="inline-flex items-center gap-2 mt-4 px-5 py-2.5 rounded-xl border font-mono font-bold text-lg"
              style={{ background: `${cfg.color}10`, borderColor: `${cfg.color}30`, color: cfg.color }}
            >
              Final Deal: {finalDealValue.toLocaleString()} {valueUnit}
            </div>
          )}
        </div>
      </div>

      {/* ── 2. Score + offer analytics ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Score ring card */}
        <div className="rounded-2xl p-6 bg-white/[0.03] border border-white/[0.07] flex flex-col items-center gap-4">
          <SectionHeader
            icon={<Award className="w-4 h-4 text-indigo-400" />}
            label="Performance Score"
            sub="Based on deal value, BATNA utilisation & coaching feedback"
          />
          <ScoreRing score={score} rating={performance.rating} />
        </div>

        {/* Offer analytics / bar chart */}
        <div className="rounded-2xl p-6 bg-white/[0.03] border border-white/[0.07]">
          <SectionHeader
            icon={<Zap className="w-4 h-4 text-amber-400" />}
            label="Offer Landscape"
            sub="How the numbers compared at the end"
          />
          <div className="space-y-4 mt-2">
            {openingOffer !== undefined && (
              <AnimatedBar label="Opponent opened at" value={openingOffer} max={maxOffer} color="#f87171" delay={200} />
            )}
            {userBatna !== undefined && (
              <AnimatedBar label="Your BATNA (walk-away)" value={userBatna} max={maxOffer} color="#fbbf24" delay={350} />
            )}
            {userTarget !== undefined && (
              <AnimatedBar label="Your target" value={userTarget} max={maxOffer} color="#6470f3" delay={500} />
            )}
            {finalDealValue !== null && finalDealValue !== undefined && (
              <AnimatedBar label="Final deal ✓" value={finalDealValue} max={maxOffer} color="#34d399" delay={650} />
            )}
            <AnimatedBar label="Opponent's hidden target" value={opponentHidden.target} max={maxOffer} color="#c084fc" delay={800} />
            <AnimatedBar label="Opponent's hidden BATNA" value={opponentHidden.batna} max={maxOffer} color="#94a3b8" delay={950} />
          </div>
        </div>
      </div>

      {/* ── 3. Best & worst moves ──────────────────────────────────────────────── */}
      {(performance.best_move || performance.worst_move) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {performance.best_move && (
            <div className="rounded-2xl p-5 bg-emerald-500/[0.05] border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                  <ThumbsUp className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <div>
                  <p className="text-xs font-bold text-emerald-400 uppercase tracking-widest">Best Move</p>
                  <p className="text-[10px] text-white/30">Turn {performance.best_move.turn}</p>
                </div>
              </div>
              <p className="text-sm text-emerald-300/80 leading-relaxed">
                {performance.best_move.summary}
              </p>
            </div>
          )}
          {performance.worst_move && (
            <div className="rounded-2xl p-5 bg-amber-500/[0.05] border border-amber-500/20">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-amber-500/15 flex items-center justify-center">
                  <ThumbsDown className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <div>
                  <p className="text-xs font-bold text-amber-400 uppercase tracking-widest">Needs Improvement</p>
                  <p className="text-[10px] text-white/30">Turn {performance.worst_move.turn}</p>
                </div>
              </div>
              <p className="text-sm text-amber-300/80 leading-relaxed">
                {performance.worst_move.summary}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── 4. Opponent reveal ─────────────────────────────────────────────────── */}
      <div className="rounded-2xl p-6 bg-white/[0.03] border border-purple-500/20 relative overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 80% 60% at 100% 0%, rgba(192,132,252,0.06), transparent)' }}
        />
        <div className="relative">
          <SectionHeader
            icon={<Eye className="w-4 h-4 text-purple-400" />}
            label="Opponent Unmasked"
            sub="Their hidden state — only revealed now"
          />
          <div className="grid grid-cols-2 gap-4 mb-5">
            {[
              { label: 'Their Target', value: opponentHidden.target, color: '#c084fc' },
              { label: 'Their BATNA', value: opponentHidden.batna, color: '#94a3b8' },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="rounded-xl px-4 py-3 border"
                style={{ background: `${color}08`, borderColor: `${color}25` }}
              >
                <p className="text-[10px] text-white/30 uppercase tracking-widest mb-1">{label}</p>
                <p className="text-xl font-bold font-mono" style={{ color }}>
                  {value.toLocaleString()}
                </p>
                <p className="text-[10px] text-white/25 mt-0.5">{valueUnit}</p>
              </div>
            ))}
          </div>
          <div className="space-y-2 border-t border-white/[0.05] pt-4">
            <div className="flex items-start gap-2">
              <Bot className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
              <div>
                <span className="text-xs font-semibold text-purple-300">Persona: </span>
                <span className="text-xs text-white/50">{opponentHidden.persona}</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="text-xs font-semibold text-amber-300">Urgency: </span>
                <span className="text-xs text-white/50">{opponentHidden.urgency}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 5. Full transcript ─────────────────────────────────────────────────── */}
      {transcript.length > 0 && (
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
          {/* Toggle header */}
          <button
            id="transcript-toggle"
            onClick={() => setShowTranscript(!showTranscript)}
            className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/[0.02] transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-white/[0.05] border border-white/[0.07] flex items-center justify-center">
                <MessageSquare className="w-3.5 h-3.5 text-white/40" />
              </div>
              <div className="text-left">
                <p className="text-sm font-semibold text-white">Full Transcript</p>
                <p className="text-xs text-white/30 mt-0.5">{transcript.length} messages · with opponent context now revealed</p>
              </div>
            </div>
            <span
              className="text-white/30 text-sm transition-transform duration-300"
              style={{ transform: showTranscript ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              ▾
            </span>
          </button>

          {/* Transcript body */}
          <div
            ref={transcriptRef}
            className="overflow-hidden transition-all duration-500 ease-in-out"
            style={{ maxHeight: showTranscript ? '9999px' : '0' }}
          >
            <div className="px-6 pb-6 space-y-3 border-t border-white/[0.05] pt-4">
              {transcript.map((msg, i) => {
                const isUser = msg.role === 'user';
                return (
                  <div
                    key={i}
                    className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
                    style={{ animation: `fadeUp 0.3s ease-out ${i * 30}ms both` }}
                  >
                    {/* Avatar */}
                    <div
                      className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center border text-[10px] font-bold`}
                      style={isUser
                        ? { background: 'rgba(100,112,243,0.15)', borderColor: 'rgba(100,112,243,0.30)' }
                        : { background: 'rgba(192,132,252,0.10)', borderColor: 'rgba(192,132,252,0.20)' }
                      }
                    >
                      {isUser
                        ? <User className="w-3 h-3 text-indigo-400" />
                        : <Bot className="w-3 h-3 text-purple-400" />
                      }
                    </div>

                    {/* Bubble */}
                    <div className={`max-w-[80%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                      <div className="flex items-center gap-2 px-0.5">
                        <span
                          className="text-[10px] font-semibold"
                          style={{ color: isUser ? '#a5b8fd' : '#c084fc' }}
                        >
                          {isUser ? (userRole ?? 'You') : (opponentRole ?? 'Opponent')}
                        </span>
                        <span className="text-[9px] text-white/20 font-mono">· Turn {msg.turn}</span>
                      </div>
                      <div
                        className="text-xs leading-relaxed px-3.5 py-2.5 rounded-xl"
                        style={isUser
                          ? {
                              background: 'rgba(100,112,243,0.12)',
                              border: '1px solid rgba(100,112,243,0.20)',
                              color: 'rgba(255,255,255,0.85)',
                              borderTopRightRadius: '4px',
                            }
                          : {
                              background: 'rgba(255,255,255,0.04)',
                              border: '1px solid rgba(255,255,255,0.07)',
                              color: 'rgba(255,255,255,0.70)',
                              borderTopLeftRadius: '4px',
                            }
                        }
                      >
                        {msg.content}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
