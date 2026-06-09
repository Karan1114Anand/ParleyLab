'use client';

import { PerformanceScore } from '@/components/PerformanceScore';
import { revealSession, RevealResponse, StartSessionResponse } from '@/lib/api';
import { getAccent } from '@/store/useNegotiationStore';
import {
  ArrowLeft,
  Home,
  Loader2,
  RefreshCw,
  Share2,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';

// ── Loading skeleton ───────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-40 rounded-2xl bg-white/[0.04] shimmer" />
      <div className="grid grid-cols-2 gap-4">
        <div className="h-56 rounded-2xl bg-white/[0.04] shimmer" />
        <div className="h-56 rounded-2xl bg-white/[0.04] shimmer" />
      </div>
      <div className="h-32 rounded-2xl bg-white/[0.04] shimmer" />
      <div className="h-48 rounded-2xl bg-white/[0.04] shimmer" />
    </div>
  );
}

// ── Error card ─────────────────────────────────────────────────────────────────

function ErrorCard({ message, sessionId }: { message: string; sessionId: string }) {
  const isIncomplete = message.toLowerCase().includes('not_complete') ||
    message.toLowerCase().includes('still active');

  return (
    <div className="rounded-2xl p-8 text-center border border-red-500/20 bg-red-500/[0.05] animate-fade-up">
      <div className="text-4xl mb-4">
        {isIncomplete ? '⏳' : '❌'}
      </div>
      <h2 className="text-lg font-bold text-red-300 mb-2">
        {isIncomplete ? 'Negotiation Still In Progress' : 'Could Not Load Results'}
      </h2>
      <p className="text-sm text-white/40 mb-6 leading-relaxed max-w-sm mx-auto">
        {isIncomplete
          ? 'The negotiation hasn\'t ended yet. Complete the negotiation first, then view your results.'
          : message}
      </p>
      {isIncomplete ? (
        <Link
          href={`/negotiation/${sessionId}`}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold
            bg-white/[0.06] border border-white/[0.10] text-white hover:bg-white/[0.10] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Negotiation
        </Link>
      ) : (
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold
            bg-white/[0.06] border border-white/[0.10] text-white hover:bg-white/[0.10] transition-colors"
        >
          <Home className="w-4 h-4" />
          New Negotiation
        </Link>
      )}
    </div>
  );
}

// ── Confetti burst (pure CSS, no lib) ─────────────────────────────────────────

const CONFETTI_COLORS = ['#6470f3', '#c084fc', '#34d399', '#fbbf24', '#f87171', '#67e8f9'];

// Pre-generate stable piece data at module level so it never changes between renders
const CONFETTI_PIECES = Array.from({ length: 24 }, (_, i) => ({
  id: i,
  color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
  left: `${(i / 24) * 100}%`,
  delay: `${(i * 0.05).toFixed(2)}s`,
  size: `${5 + (i % 3) * 3}px`, // deterministic sizes: 5, 8, or 11px
  rotation: `${i * 15}deg`,
}));

function ConfettiBurst({ trigger }: { trigger: boolean }) {
  if (!trigger) return null;
  return (
    <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
      {CONFETTI_PIECES.map((p) => (
        <div
          key={p.id}
          className="absolute top-0 rounded-sm"
          style={{
            left: p.left,
            width: p.size,
            height: p.size,
            background: p.color,
            animation: `confettiFall 2s ease-in ${p.delay} forwards`,
            transform: `rotate(${p.rotation})`,
          }}
        />
      ))}
    </div>
  );
}


// ── Share button ───────────────────────────────────────────────────────────────

function ShareButton({ score, outcome }: { score: number; outcome: string }) {
  const [copied, setCopied] = useState(false);
  const handle = async () => {
    const text = `I scored ${score}/100 in a negotiation on ParleyLab! Outcome: ${outcome.replace('_', ' ')} 🤝`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  };
  return (
    <button
      onClick={handle}
      className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold
        bg-white/[0.05] border border-white/[0.08] text-white/60
        hover:text-white hover:bg-white/[0.08] transition-all"
    >
      <Share2 className="w-3.5 h-3.5" />
      {copied ? 'Copied!' : 'Share result'}
    </button>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function ResultsPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const sessionId = params.id;

  const [data, setData]       = useState<RevealResponse | null>(null);
  const [session, setSession] = useState<StartSessionResponse | null>(null);
  const [scenarioId, setScenarioId] = useState('salary_v1');
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [confetti, setConfetti] = useState(false);
  const headerRef = useRef<HTMLDivElement>(null);

  // Recover session bootstrap from sessionStorage for richer UI
  useEffect(() => {
    const stored = sessionStorage.getItem(`session_${sessionId}`);
    if (stored) {
      try { setSession(JSON.parse(stored)); } catch { /* ignore */ }
    }
    const sid = sessionStorage.getItem(`scenario_id_${sessionId}`);
    if (sid) setScenarioId(sid);
  }, [sessionId]);

  // Fetch reveal data
  useEffect(() => {
    revealSession(sessionId)
      .then((d) => {
        setData(d);
        setLoading(false);
        // Trigger confetti only for deal_closed
        if (d.outcome === 'deal_closed') {
          setTimeout(() => setConfetti(true), 600);
          setTimeout(() => setConfetti(false), 3500);
        }
      })
      .catch((e) => {
        setError(e.message ?? 'Failed to load results.');
        setLoading(false);
      });
  }, [sessionId]);

  const accent = getAccent(scenarioId);

  return (
    <>
      <ConfettiBurst trigger={confetti} />

      <main className="min-h-screen pb-20">

        {/* ── Ambient glow header ───────────────────────────────────────── */}
        <div
          ref={headerRef}
          className="relative px-4 pt-10 pb-12 mb-2 overflow-hidden"
        >
          {/* Background orb */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: `radial-gradient(ellipse 70% 60% at 50% 0%, ${accent.glow}, transparent 70%)`,
            }}
          />
          {/* Grid overlay */}
          <div
            className="absolute inset-0 pointer-events-none opacity-[0.025]"
            style={{
              backgroundImage: `linear-gradient(rgba(255,255,255,1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)`,
              backgroundSize: '40px 40px',
            }}
          />

          <div className="relative max-w-3xl mx-auto">
            {/* Nav row */}
            <div className="flex items-center justify-between mb-10">
              <Link
                href="/"
                className="flex items-center gap-2 text-sm text-white/40 hover:text-white/80 transition-colors group"
              >
                <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
                New negotiation
              </Link>
              <div className="flex items-center gap-2">
                {data && (
                  <ShareButton score={data.performance.score} outcome={data.outcome} />
                )}
                <button
                  onClick={() => router.push('/')}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold
                    bg-white/[0.05] border border-white/[0.08] text-white/60
                    hover:text-white hover:bg-white/[0.08] transition-all"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Practice again
                </button>
              </div>
            </div>

            {/* Headline */}
            <div className="text-center">
              <div
                className="inline-flex items-center gap-2 mb-5 px-4 py-1.5 rounded-full border text-xs font-bold uppercase tracking-widest"
                style={{
                  background: `${accent.primary}10`,
                  borderColor: `${accent.primary}30`,
                  color: accent.primary,
                }}
              >
                <Sparkles className="w-3 h-3" />
                Session Complete
              </div>
              <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight mb-3">
                Negotiation{' '}
                <span
                  style={{
                    backgroundImage: `linear-gradient(135deg, ${accent.primary}, #c084fc)`,
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  Debrief
                </span>
              </h1>
              {session && (
                <p className="text-white/35 text-base">
                  {session.scenario_display_name} ·{' '}
                  <span className="font-mono text-white/20 text-sm">{sessionId}</span>
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ── Content area ─────────────────────────────────────────────── */}
        <div className="max-w-3xl mx-auto px-4">
          {loading && <LoadingSkeleton />}
          {error   && <ErrorCard message={error} sessionId={sessionId} />}
          {data    && (
            <PerformanceScore
              outcome={data.outcome}
              finalDealValue={data.final_deal_value}
              opponentHidden={data.opponent_hidden}
              performance={data.performance}
              transcript={data.full_transcript}
              valueUnit={data.value_unit}
              userRole={session?.user_role}
              opponentRole={session?.opponent_role}
              openingOffer={session?.opening_offer}
              userTarget={session?.user_brief?.target}
              userBatna={session?.user_brief?.batna}
            />
          )}
        </div>

      </main>
    </>
  );
}
