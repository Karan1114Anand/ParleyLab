'use client';

import { LandingScreen } from '@/components/LandingScreen';
import { RoleBriefScreen } from '@/components/RoleBriefScreen';
import { useNegotiationStore } from '@/store/useNegotiationStore';
import { useEffect, useState } from 'react';

/**
 * Root page — phase router driven by Zustand.
 *
 * Phases:
 *   'landing'     → <LandingScreen />   (scenario picker)
 *   'brief'       → <RoleBriefScreen /> (mission briefing)
 *   'negotiating' → router.push() navigates away; this never renders
 *
 * The slide transition between phases uses CSS animations.
 */
export default function HomePage() {
  const phase = useNegotiationStore((s) => s.phase);

  // Track previous phase so we can animate the transition direction
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Avoid SSR mismatch
  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <main className="relative overflow-x-hidden">
      {/* Phase: landing */}
      <div
        key="landing"
        style={{
          display: phase === 'landing' ? 'block' : 'none',
          animation: phase === 'landing' ? 'fadeIn 0.4s ease-out' : 'none',
        }}
      >
        <LandingScreen />
      </div>

      {/* Phase: brief */}
      {phase === 'brief' && (
        <div
          key="brief"
          style={{
            animation: 'slideUpIn 0.45s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          <RoleBriefScreen />
        </div>
      )}

      <style jsx global>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes slideUpIn {
          from { opacity: 0; transform: translateY(28px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </main>
  );
}
