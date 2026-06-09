'use client';

import { startSession } from '@/lib/api';
import { useNegotiationStore, getAccent } from '@/store/useNegotiationStore';
import { useTypewriter } from '@/hooks/useTypewriter';
import {
  ArrowLeft, ArrowRight, Bot, Shield, Swords,
  Target, User, Zap, Clock, AlertTriangle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';

/**
 * RoleBriefScreen — full-screen "mission briefing" shown after scenario selection.
 *
 * Shows:
 *  - Scenario name, icon, and accent theming
 *  - User role card  vs  Opponent role card
 *  - Target + BATNA stats
 *  - Typewriter context paragraph
 *  - "Enter Negotiation" CTA (calls POST /session/start)
 */
export function RoleBriefScreen() {
  const router = useRouter();
  const { selectedScenario, setSession, goToLanding, phase } = useNegotiationStore();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If somehow selectedScenario is missing, render a fallback
  if (!selectedScenario) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 relative overflow-hidden text-white/50">
        <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin mb-4" />
        Loading scenario data...
      </div>
    );
  }

  const accent = getAccent(selectedScenario.id);

  // Typewriter on the scenario description
  const { visible: typedDescription } = useTypewriter(
    selectedScenario.description,
    14,
    600,
  );

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const info = await startSession(selectedScenario.id);
      // Store in sessionStorage for the negotiation page
      sessionStorage.setItem(`session_${info.session_id}`, JSON.stringify(info));
      sessionStorage.setItem(`scenario_id_${info.session_id}`, selectedScenario.id);
      setSession(info);
      router.push(`/negotiation/${info.session_id}`);
    } catch (e: any) {
      setError(e.message ?? 'Failed to start. Is the backend running?');
      setStarting(false);
    }
  };

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-12 relative overflow-hidden"
      style={{ animation: 'slideUpIn 0.5s cubic-bezier(0.4, 0, 0.2, 1) both' }}
    >
      {/* Ambient glow from scenario accent */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: `radial-gradient(ellipse 70% 50% at 50% 10%, ${accent.glow} 0%, transparent 65%)`,
        }}
      />

      {/* Grid lines */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />

      <div className="relative z-10 w-full max-w-4xl animate-fade-up">

        {/* Back button */}
        <button
          onClick={goToLanding}
          className="flex items-center gap-2 text-sm text-white/40 hover:text-white/80 transition-colors mb-10 group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to scenarios
        </button>

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="text-center mb-12">
          {/* Mission badge */}
          <div
            className="inline-flex items-center gap-2 mb-6 px-4 py-2 rounded-full border text-xs font-semibold uppercase tracking-widest"
            style={{
              background: `${accent.primary}12`,
              borderColor: `${accent.primary}35`,
              color: accent.primary,
            }}
          >
            <Zap className="w-3 h-3" />
            Mission Briefing
          </div>

          {/* Scenario icon + title */}
          <div className="flex items-center justify-center gap-4 mb-4">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl"
              style={{
                background: `${accent.primary}18`,
                border: `1px solid ${accent.primary}35`,
                boxShadow: `0 0 30px ${accent.glow}`,
              }}
            >
              {selectedScenario.icon}
            </div>
            <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight">
              {selectedScenario.display_name}
            </h1>
          </div>

          {/* Typewriter description */}
          <p className="text-white/50 text-lg max-w-xl mx-auto min-h-[3.5rem] leading-relaxed">
            {typedDescription}
            <span className="inline-block w-[2px] h-[1em] ml-[1px] bg-white/60 align-middle animate-pulse" />
          </p>
        </div>

        {/* ── Role vs Role cards ─────────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-8">
          {/* YOU */}
          <div
            className="relative rounded-2xl p-6 overflow-hidden"
            style={{
              background: `linear-gradient(135deg, ${accent.primary}12, ${accent.primary}06)`,
              border: `1px solid ${accent.primary}30`,
            }}
          >
            <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-10"
              style={{ background: accent.primary, transform: 'translate(30%, -30%)' }}
            />
            <div className="relative">
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: `${accent.primary}25`, border: `1px solid ${accent.primary}40` }}
                >
                  <User className="w-5 h-5" style={{ color: accent.primary }} />
                </div>
                <div>
                  <p className="text-xs text-white/30 uppercase tracking-widest">You play as</p>
                  <p className="font-bold text-white text-lg">{selectedScenario.user_role}</p>
                </div>
              </div>

              {/* Stats */}
              <div className="space-y-3">
                <StatRow
                  icon={<Target className="w-3.5 h-3.5" style={{ color: accent.primary }} />}
                  label="Your Target"
                  value={`${selectedScenario.value_unit}`}
                  accent={accent.primary}
                  note="What you're aiming for"
                />
                <StatRow
                  icon={<Shield className="w-3.5 h-3.5 text-amber-400" />}
                  label="Your BATNA"
                  value={selectedScenario.value_unit}
                  accent="#fbbf24"
                  note="Walk-away point — protect this"
                />
              </div>

              {/* Tag */}
              <div className="mt-4 pt-4 border-t border-white/[0.06]">
                <p className="text-xs text-white/30 leading-relaxed">
                  Your specific target and BATNA will be revealed once the negotiation starts.
                </p>
              </div>
            </div>
          </div>

          {/* OPPONENT */}
          <div className="relative rounded-2xl p-6 overflow-hidden bg-white/[0.04] border border-white/[0.08]">
            <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-5"
              style={{ background: '#c084fc', transform: 'translate(30%, -30%)' }}
            />
            <div className="relative">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-purple-500/20 border border-purple-500/30">
                  <Bot className="w-5 h-5 text-purple-300" />
                </div>
                <div>
                  <p className="text-xs text-white/30 uppercase tracking-widest">Opponent (AI)</p>
                  <p className="font-bold text-white text-lg">{selectedScenario.opponent_role}</p>
                </div>
              </div>

              {/* Hidden state teaser */}
              <div className="space-y-3">
                <HiddenStatRow label="Their Target" />
                <HiddenStatRow label="Their BATNA" />
              </div>

              <div className="mt-4 pt-4 border-t border-white/[0.06]">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-white/30 leading-relaxed">
                    The opponent's target and walk-away are hidden. You'll only see them in the post-game reveal.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Rules strip ────────────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { icon: <Clock className="w-4 h-4 text-white/40" />, label: 'Max Turns', value: `${selectedScenario.max_turns}` },
            { icon: <Swords className="w-4 h-4 text-white/40" />, label: 'Format', value: 'Text + Voice' },
            { icon: <Zap className="w-4 h-4 text-white/40" />, label: 'Coach', value: 'Live AI Feedback' },
          ].map(({ icon, label, value }) => (
            <div key={label} className="rounded-xl p-4 bg-white/[0.03] border border-white/[0.06] text-center">
              <div className="flex justify-center mb-2">{icon}</div>
              <p className="text-white/30 text-[10px] uppercase tracking-widest mb-1">{label}</p>
              <p className="text-white text-sm font-semibold">{value}</p>
            </div>
          ))}
        </div>

        {/* ── Error ──────────────────────────────────────────────────────── */}
        {error && (
          <div className="mb-5 px-4 py-3 rounded-xl bg-red-500/5 border border-red-500/20 animate-fade-up">
            <p className="text-sm text-red-300 text-center">{error}</p>
          </div>
        )}

        {/* ── CTA ────────────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
          <button
            id="start-negotiation-btn"
            onClick={handleStart}
            disabled={starting}
            className="relative w-full sm:w-auto px-10 py-4 rounded-2xl font-bold text-white text-lg
              flex items-center justify-center gap-3 overflow-hidden
              disabled:opacity-60 disabled:cursor-not-allowed
              transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
            style={{
              background: `linear-gradient(135deg, ${accent.primary}, #8b5cf6)`,
              boxShadow: starting ? 'none' : `0 8px 32px ${accent.glow}`,
            }}
          >
            {/* Shimmer sweep on hover */}
            <div className="absolute inset-0 opacity-0 hover:opacity-100 transition-opacity duration-300"
              style={{ background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.15) 50%, transparent 60%)' }}
            />
            {starting ? (
              <>
                <div className="w-5 h-5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                <span>Preparing briefing room…</span>
              </>
            ) : (
              <>
                <Swords className="w-5 h-5" />
                <span>Enter Negotiation</span>
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </div>

        {/* Fine print */}
        <p className="text-center text-xs text-white/20 mt-6">
          The AI opponent will make a written opening offer. You respond. Coach feedback appears after every move.
        </p>
      </div>

      {/* CSS for slide-up entry */}
      <style jsx>{`
        @keyframes slideUpIn {
          from { opacity: 0; transform: translateY(32px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatRow({
  icon, label, value, accent, note,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent: string;
  note: string;
}) {
  return (
    <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-white/[0.03] border border-white/[0.05]">
      <div className="flex items-center gap-2">
        {icon}
        <div>
          <p className="text-xs text-white/40">{label}</p>
          <p className="text-xs text-white/25 mt-0.5">{note}</p>
        </div>
      </div>
      <span
        className="text-xs font-semibold px-2 py-1 rounded-md"
        style={{ background: `${accent}18`, color: accent }}
      >
        {value}
      </span>
    </div>
  );
}

function HiddenStatRow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-white/[0.03] border border-white/[0.05]">
      <p className="text-xs text-white/40">{label}</p>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="w-1.5 h-1.5 rounded-full bg-white/15" />
        ))}
        <span className="text-[10px] text-white/25 ml-1">hidden</span>
      </div>
    </div>
  );
}
