'use client';

import { startSession } from '@/lib/api';
import { getCountryByCode } from '@/lib/countries';
import { useNegotiationStore, getAccent } from '@/store/useNegotiationStore';
import { useUserSettingsStore } from '@/store/useUserSettingsStore';
import { useTypewriter } from '@/hooks/useTypewriter';
import { AlertTriangle, ArrowLeft, ArrowRight, Clock, Swords } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

export function RoleBriefScreen() {
  const router = useRouter();
  const { selectedScenario, setSession, goToLanding } = useNegotiationStore();
  const { userName, countryCode } = useUserSettingsStore();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!selectedScenario) {
    return (
      <div
        style={{
          minHeight: 'calc(100vh - 48px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '14px',
        }}
      >
        Loading scenario data…
      </div>
    );
  }

  // keep accent in scope (computed from scenario, not used in new JSX)
  void getAccent(selectedScenario.id);

  const country = getCountryByCode(countryCode);
  const currency = country?.currency ?? 'USD';

  const { visible: typedDescription } = useTypewriter(selectedScenario.description, 14, 600);

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const info = await startSession(
        selectedScenario.id,
        userName || undefined,
        currency,
      );
      sessionStorage.setItem(`session_${info.session_id}`, JSON.stringify(info));
      sessionStorage.setItem(`scenario_id_${info.session_id}`, selectedScenario.id);
      setSession(info);
      router.push(`/negotiation/${info.session_id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to start. Is the backend running?';
      setError(msg);
      setStarting(false);
    }
  };

  return (
    <div style={{ minHeight: 'calc(100vh - 48px)', display: 'flex', flexDirection: 'column' }}>

      {/* ── Orange header band ──────────────────────────────────────────── */}
      <div className="rb-header-band">
        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          <p className="rb-header-label">Active scenario</p>
          <h1 className="rb-header-title">{selectedScenario.display_name}</h1>
        </div>
      </div>

      {/* ── Back ────────────────────────────────────────────────────────── */}
      <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%', padding: '24px 24px 0' }}>
        <button
          onClick={goToLanding}
          className="btn-ghost"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '13px',
            marginBottom: '24px',
          }}
        >
          <ArrowLeft size={14} />
          Back to scenarios
        </button>
      </div>

      {/* ── Description (typewriter) ────────────────────────────────────── */}
      <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%', padding: '0 24px 24px' }}>
        <p
          style={{
            color: 'var(--text-muted)',
            fontSize: '14px',
            lineHeight: 1.6,
            margin: 0,
            minHeight: '32px',
          }}
        >
          {typedDescription}
          <span
            style={{
              display: 'inline-block',
              width: '2px',
              height: '1em',
              marginLeft: '2px',
              background: 'var(--text-muted)',
              verticalAlign: 'middle',
            }}
          />
        </p>
      </div>

      {/* ── Divider ─────────────────────────────────────────────────────── */}
      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '0' }} />

      {/* ── Split layout: YOUR BRIEF | OPPONENT PROFILE ─────────────────── */}
      <div className="rb-grid">

        {/* YOUR BRIEF */}
        <div>
          <p className="rb-section-label">Your brief</p>

          <DataRow label="Role" value={selectedScenario.user_role} />
          <DataRow
            label="Target"
            value={selectedScenario.value_unit}
            note="Exact value revealed at session start"
            isOrange
          />
          <DataRow
            label="BATNA"
            value={selectedScenario.value_unit}
            note="Your walk-away — protect this"
            isOrange
          />

          {/* Strategy hint */}
          <div className="rb-hint-box">
            <p className="rb-hint-text">
              Aim high, concede slowly, and never reveal your BATNA.
              The AI opponent is trained to exploit weak anchors.
            </p>
          </div>
        </div>

        {/* OPPONENT PROFILE */}
        <div>
          <p className="rb-section-label">Opponent profile</p>

          <DataRow label="Role" value={selectedScenario.opponent_role} />

          {/* Hidden / masked values */}
          <div style={{ marginBottom: '16px' }}>
            <p className="rb-data-label">Target</p>
            <span className="rb-masked">██████</span>
          </div>
          <div style={{ marginBottom: '16px' }}>
            <p className="rb-data-label">BATNA</p>
            <span className="rb-masked">██████</span>
          </div>

          {/* Urgency badge */}
          <div style={{ marginBottom: '16px' }}>
            <p className="rb-data-label">Urgency</p>
            <span className="rb-urgency-badge">Unknown</span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
              marginTop: '12px',
              padding: '10px 12px',
              border: '1px solid var(--border)',
              borderRadius: '2px',
            }}
          >
            <AlertTriangle
              size={12}
              style={{ color: 'var(--warning)', flexShrink: 0, marginTop: '1px' }}
            />
            <p
              style={{
                fontSize: '11px',
                color: 'var(--text-dim)',
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              Target and BATNA are hidden until the post-session reveal.
            </p>
          </div>
        </div>
      </div>

      {/* ── Rules strip ─────────────────────────────────────────────────── */}
      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '0' }} />
      <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px 24px', display: 'flex', gap: '32px', flexWrap: 'wrap' }}>
        {[
          { icon: <Clock size={12} />, label: 'Max turns', value: `${selectedScenario.max_turns}` },
          { icon: <Swords size={12} />, label: 'Format', value: 'Text + voice' },
          { icon: <ArrowRight size={12} />, label: 'Coaching', value: 'Live AI feedback' },
        ].map(({ icon, label, value }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--text-dim)' }}>{icon}</span>
            <div>
              <p
                style={{
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '10px',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  margin: '0 0 1px',
                }}
              >
                {label}
              </p>
              <p style={{ fontSize: '13px', color: 'var(--text)', margin: 0 }}>{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* ── Error ───────────────────────────────────────────────────────── */}
      {error && (
        <div
          className="animate-fade-up"
          style={{
            maxWidth: '800px',
            margin: '0 auto',
            padding: '0 24px',
          }}
        >
          <div
            style={{
              marginBottom: '20px',
              padding: '12px 16px',
              border: '1px solid var(--danger)',
              borderRadius: '2px',
            }}
          >
            <p style={{ fontSize: '14px', color: 'var(--danger)', margin: 0 }}>{error}</p>
          </div>
        </div>
      )}

      {/* ── CTA ─────────────────────────────────────────────────────────── */}
      <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%', padding: '0 24px 32px' }}>
        <button
          id="start-negotiation-btn"
          onClick={handleStart}
          disabled={starting}
          className="rb-cta"
        >
          {starting ? (
            <>
              <span
                style={{
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  border: '2px solid rgba(255,255,255,0.3)',
                  borderTopColor: 'white',
                  display: 'inline-block',
                }}
                className="animate-spin"
              />
              Preparing session…
            </>
          ) : (
            <>Begin negotiation →</>
          )}
        </button>

        {/* Fine print */}
        <p
          style={{
            textAlign: 'center',
            fontFamily: 'var(--font-mono, monospace)',
            fontSize: '11px',
            color: 'var(--text-dim)',
            marginTop: '16px',
          }}
        >
          The AI will make an opening offer. You respond. Coaching appears after every move.
        </p>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function DataRow({
  label,
  value,
  note,
  isOrange,
}: {
  label: string;
  value: string;
  note?: string;
  isOrange?: boolean;
}) {
  return (
    <div style={{ marginBottom: '16px' }}>
      <p className="rb-data-label">{label}</p>
      <p className={isOrange ? 'rb-data-value-orange' : 'rb-data-value'}>{value}</p>
      {note && (
        <p style={{ fontSize: '11px', color: 'var(--text-dim)', margin: '2px 0 0' }}>{note}</p>
      )}
    </div>
  );
}
