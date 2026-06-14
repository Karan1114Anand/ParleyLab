'use client';

import { listScenarios, ScenarioSummary } from '@/lib/api';
import { getCountryByCode } from '@/lib/countries';
import { ScenarioCard } from '@/components/ScenarioCard';
import { useNegotiationStore } from '@/store/useNegotiationStore';
import { useUserSettingsStore } from '@/store/useUserSettingsStore';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

export function LandingScreen() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const selectScenario = useNegotiationStore((s) => s.selectScenario);
  const { userName, countryCode, isConfigured } = useUserSettingsStore();
  const country = getCountryByCode(countryCode);

  useEffect(() => {
    listScenarios()
      .then(setScenarios)
      .catch((e) => setError(e.message ?? 'Cannot reach backend — is it running?'))
      .finally(() => setLoading(false));
  }, []);

  const scrollToGrid = () => {
    gridRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // keep router/scrollToGrid in scope so the logic section is unchanged
  void router;
  void scrollToGrid;

  return (
    <div style={{ minHeight: 'calc(100vh - 48px)', display: 'flex', flexDirection: 'column' }}>

      {/* ── Hero band ────────────────────────────────────────────────────── */}
      <section className="hero-band">
        <h1 className="hero-title">AI NEGOTIATION SIMULATOR.</h1>
        <p className="hero-subtitle">
          Practice before the stakes are real — train against RL-powered opponents with live coaching
        </p>

        {/* User badge */}
        {isConfigured && userName && (
          <div
            style={{
              marginTop: '16px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 12px',
              border: '1px solid rgba(255,255,255,0.3)',
              borderRadius: '2px',
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.8)',
            }}
          >
            <span>{userName}</span>
            {country && <span>{country.flag}</span>}
            {country && (
              <span style={{ color: 'rgba(255,255,255,0.5)' }}>{country.currency}</span>
            )}
          </div>
        )}

        {/* Stats row */}
        <div className="hero-stats">
          {[
            { value: '300K', label: 'Training episodes' },
            { value: '86%', label: 'Deal close rate' },
            { value: '4', label: 'Scenarios' },
            { value: '<1ms', label: 'RL latency' },
          ].map((stat) => (
            <div key={stat.label} style={{ textAlign: 'center' }}>
              <p className="hero-stat-value">{stat.value}</p>
              <p className="hero-stat-label">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Scenario Grid ─────────────────────────────────────────────────── */}
      <section
        ref={gridRef}
        style={{
          maxWidth: '1100px',
          margin: '0 auto',
          width: '100%',
          padding: '32px 24px 64px',
          flex: 1,
        }}
      >
        {/* Divider + label */}
        <div style={{ marginBottom: '24px' }}>
          <p
            style={{
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: '11px',
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              margin: 0,
            }}
          >
            Select scenario
          </p>
        </div>

        {/* Error */}
        {error && (
          <div
            className="animate-fade-up"
            style={{
              marginBottom: '24px',
              padding: '16px',
              border: '1px solid var(--danger)',
              borderRadius: '4px',
            }}
          >
            <p style={{ fontSize: '14px', color: 'var(--danger)', margin: 0 }}>{error}</p>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', marginBottom: 0 }}>
              Make sure the backend is running on port 8000.
            </p>
          </div>
        )}

        {/* Skeleton or cards */}
        {loading ? (
          <div className="scenario-grid">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="shimmer"
                style={{ height: '200px', animationDelay: `${i * 120}ms` }}
              />
            ))}
          </div>
        ) : (
          <div className="scenario-grid">
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

        {/* Pillars strip */}
        {!loading && !error && (
          <div className="pillars-strip">
            {[
              'Reinforcement learning',
              'Real-time coaching',
              'Dynamic opponents',
              'Post-session analytics',
            ].map((text) => (
              <div key={text} className="pillar-item">
                <div className="pillar-dot" />
                <p className="pillar-text">{text}</p>
              </div>
            ))}
          </div>
        )}

        {/* Bottom note */}
        {!loading && !error && (
          <p
            style={{
              textAlign: 'center',
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: '11px',
              color: 'var(--text-dim)',
              marginTop: '32px',
            }}
          >
            Each negotiation uses a hidden opponent profile. No two sessions play the same.
          </p>
        )}
      </section>
    </div>
  );
}
