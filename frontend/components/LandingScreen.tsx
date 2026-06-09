'use client';

import { listScenarios, ScenarioSummary } from '@/lib/api';
import { ScenarioCard } from '@/components/ScenarioCard';
import { useNegotiationStore } from '@/store/useNegotiationStore';
import { Swords, Zap, ChevronDown } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

/**
 * LandingScreen — hero section + animated scenario grid.
 *
 * Handles scenario loading and passes selection up to the Zustand store.
 */
export function LandingScreen() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const selectScenario = useNegotiationStore((s) => s.selectScenario);

  useEffect(() => {
    listScenarios()
      .then(setScenarios)
      .catch((e) => setError(e.message ?? 'Cannot reach backend — is it running?'))
      .finally(() => setLoading(false));
  }, []);

  const scrollToGrid = () => {
    gridRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <section className="relative flex flex-col items-center justify-center min-h-[92vh] px-4 text-center overflow-hidden">

        {/* Animated gradient orbs */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div
            className="absolute w-[600px] h-[600px] rounded-full blur-3xl opacity-20 animate-pulse-slow"
            style={{
              background: 'radial-gradient(circle, #6470f3 0%, transparent 70%)',
              top: '-10%', left: '-5%',
            }}
          />
          <div
            className="absolute w-[500px] h-[500px] rounded-full blur-3xl opacity-15"
            style={{
              background: 'radial-gradient(circle, #c084fc 0%, transparent 70%)',
              bottom: '-5%', right: '-5%',
              animation: 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) 1s infinite',
            }}
          />
          {/* Grid lines */}
          <div
            className="absolute inset-0 opacity-[0.025]"
            style={{
              backgroundImage: `
                linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)
              `,
              backgroundSize: '60px 60px',
            }}
          />
        </div>

        {/* Content */}
        <div className="relative z-10 max-w-3xl mx-auto animate-fade-up">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 mb-8 px-4 py-2 rounded-full bg-white/[0.06] border border-white/[0.1] backdrop-blur-sm">
            <Zap className="w-3.5 h-3.5 text-brand-400" />
            <span className="text-xs font-semibold text-brand-300 tracking-wide uppercase">
              RL + Gemini Negotiation Coach
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          </div>

          {/* Headline */}
          <h1 className="text-6xl sm:text-7xl font-extrabold leading-[1.08] tracking-tight mb-6">
            <span className="text-white">Master the</span>
            <br />
            <span className="gradient-text">art of the deal.</span>
          </h1>

          <p className="text-lg sm:text-xl text-white/50 leading-relaxed max-w-xl mx-auto mb-10">
            Go head-to-head with an AI opponent powered by reinforcement learning.
            Get brutally honest coaching on every move — before the stakes are real.
          </p>

          {/* Stats */}
          <div className="flex flex-wrap justify-center gap-8 mb-12">
            {[
              { value: '4', label: 'Real Scenarios' },
              { value: 'PPO + LLM', label: 'AI Stack' },
              { value: 'Real-time', label: 'Coaching' },
              { value: '∞', label: 'Practice Rounds' },
            ].map(({ value, label }) => (
              <div key={label} className="text-center">
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="text-xs text-white/40 mt-0.5">{label}</p>
              </div>
            ))}
          </div>

          {/* CTA */}
          <button
            onClick={scrollToGrid}
            className="btn-accent inline-flex items-center gap-2 px-8 py-4 rounded-2xl text-base font-semibold"
          >
            <Swords className="w-5 h-5" />
            Choose Your Scenario
          </button>
        </div>

        {/* Scroll hint */}
        <button
          onClick={scrollToGrid}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 text-white/20 hover:text-white/50 transition-colors animate-bounce"
        >
          <ChevronDown className="w-6 h-6" />
        </button>
      </section>

      {/* ── Scenario Grid ─────────────────────────────────────────────────── */}
      <section ref={gridRef} className="px-4 pb-24 max-w-5xl mx-auto w-full">
        {/* Section header */}
        <div className="flex items-center gap-4 mb-10">
          <div className="flex-1 h-px bg-white/[0.06]" />
          <div className="flex items-center gap-2.5 px-5 py-2 rounded-full bg-white/[0.04] border border-white/[0.08]">
            <Swords className="w-4 h-4 text-brand-400" />
            <span className="text-sm font-semibold text-white">Select Your Negotiation</span>
          </div>
          <div className="flex-1 h-px bg-white/[0.06]" />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 rounded-2xl bg-red-500/5 border border-red-500/20 animate-fade-up">
            <p className="text-sm text-red-300 text-center">{error}</p>
            <p className="text-xs text-white/30 text-center mt-1">
              Make sure the backend is running on port 8000.
            </p>
          </div>
        )}

        {/* Skeleton or cards */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-56 rounded-2xl shimmer"
                style={{ animationDelay: `${i * 120}ms` }}
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {scenarios.map((s, i) => (
              <ScenarioCard
                key={s.id}
                scenario={s}
                onSelect={selectScenario}
                index={i}
              />
            ))}
          </div>
        )}

        {/* Bottom note */}
        {!loading && !error && (
          <p className="text-center text-xs text-white/20 mt-8">
            Each negotiation uses a hidden opponent profile. No two sessions play the same.
          </p>
        )}
      </section>
    </div>
  );
}
