'use client';

import { create } from 'zustand';
import type { ScenarioSummary, StartSessionResponse } from '@/lib/api';

// ── App phases ─────────────────────────────────────────────────────────────────
export type AppPhase = 'landing' | 'brief' | 'negotiating';

// ── Scenario accent colors keyed by scenario ID ────────────────────────────────
export const SCENARIO_ACCENTS: Record<string, {
  primary: string;
  glow: string;
  badge: string;
  border: string;
  text: string;
}> = {
  salary_v1:   { primary: '#6470f3', glow: 'rgba(100,112,243,0.35)', badge: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',   border: 'border-indigo-500/50',  text: 'text-indigo-300' },
  freelance_v1:{ primary: '#34d399', glow: 'rgba(52,211,153,0.35)',  badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30', border: 'border-emerald-500/50', text: 'text-emerald-300' },
  rent_v1:     { primary: '#fbbf24', glow: 'rgba(251,191,36,0.35)',  badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',       border: 'border-amber-500/50',  text: 'text-amber-300' },
  equity_v1:   { primary: '#c084fc', glow: 'rgba(192,132,252,0.35)', badge: 'bg-purple-500/20 text-purple-300 border-purple-500/30',    border: 'border-purple-500/50', text: 'text-purple-300' },
};

export const getAccent = (id: string) =>
  SCENARIO_ACCENTS[id] ?? SCENARIO_ACCENTS['salary_v1'];

// ── Store ──────────────────────────────────────────────────────────────────────
interface NegotiationStore {
  phase: AppPhase;
  selectedScenario: ScenarioSummary | null;
  sessionInfo: StartSessionResponse | null;

  selectScenario: (scenario: ScenarioSummary) => void;
  setSession: (info: StartSessionResponse) => void;
  goToLanding: () => void;
  reset: () => void;
}

export const useNegotiationStore = create<NegotiationStore>()((set) => ({
  phase: 'landing',
  selectedScenario: null,
  sessionInfo: null,

  selectScenario: (scenario) =>
    set({ selectedScenario: scenario, phase: 'brief' }),

  setSession: (info) =>
    set({ sessionInfo: info, phase: 'negotiating' }),

  goToLanding: () =>
    set({ phase: 'landing', selectedScenario: null, sessionInfo: null }),

  reset: () =>
    set({ phase: 'landing', selectedScenario: null, sessionInfo: null }),
}));
