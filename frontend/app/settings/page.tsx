'use client';

import { COUNTRIES, CountryInfo } from '@/lib/countries';
import { useUserSettingsStore } from '@/store/useUserSettingsStore';
import { ArrowLeft, Check, Globe, Search, User } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

/**
 * User Settings page — choose profile name and country.
 *
 * The country determines the currency used in negotiation scenarios,
 * and the user name is included in the AI negotiation dialogue so
 * the opponent addresses the user by name.
 */
export default function SettingsPage() {
  const router = useRouter();
  const {
    userName,
    countryCode,
    setUserName,
    setCountryCode,
    markConfigured,
  } = useUserSettingsStore();

  const [localName, setLocalName] = useState(userName);
  const [localCountry, setLocalCountry] = useState(countryCode);
  const [search, setSearch] = useState('');
  const [saved, setSaved] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [llmProvider, setLlmProvider] = useState<'ollama' | 'gemini'>('ollama');
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');

  useEffect(() => {
    setMounted(true);
  }, []);

  // Sync store → local state on mount (for hydration)
  useEffect(() => {
    if (mounted) {
      setLocalName(userName);
      setLocalCountry(countryCode);
    }
  }, [mounted, userName, countryCode]);

  const filtered = useMemo(() => {
    if (!search.trim()) return COUNTRIES;
    const q = search.toLowerCase();
    return COUNTRIES.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q) ||
        c.currency.toLowerCase().includes(q),
    );
  }, [search]);

  const selectedCountry: CountryInfo | undefined = COUNTRIES.find(
    (c) => c.code === localCountry,
  );

  const handleSave = () => {
    setUserName(localName.trim());
    setCountryCode(localCountry);
    markConfigured();
    setSaved(true);
    setTimeout(() => {
      router.push('/');
    }, 800);
  };

  const canSave = localName.trim().length >= 1 && localCountry;

  const getInitials = (name: string) => {
    const parts = name.trim().split(/\s+/);
    if (parts.length === 0 || !parts[0]) return '?';
    if (parts.length === 1) return parts[0][0].toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  if (!mounted) {
    return (
      <div
        style={{
          minHeight: 'calc(100vh - 48px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            border: '2px solid var(--accent)',
            borderTopColor: 'transparent',
          }}
          className="animate-spin"
        />
      </div>
    );
  }

  return (
    <div className="settings-container">
      {/* Back button */}
      <button
        onClick={() => router.push('/')}
        className="btn-ghost"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '13px',
          marginBottom: '32px',
        }}
      >
        <ArrowLeft size={14} />
        Back to home
      </button>

      {/* Section title */}
      <h1 className="settings-title">Profile settings</h1>

      {/* Avatar + name row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
        <div className="settings-avatar">
          {getInitials(localName || userName || 'U')}
        </div>
        <div style={{ flex: 1 }}>
          <p
            style={{
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: '14px',
              fontWeight: 500,
              color: 'var(--text)',
              margin: '0 0 2px',
            }}
          >
            {localName || 'Your name'}
          </p>
          {selectedCountry && (
            <p
              style={{
                fontSize: '12px',
                color: 'var(--text-muted)',
                margin: 0,
              }}
            >
              {selectedCountry.flag} {selectedCountry.name} · {selectedCountry.currency}
            </p>
          )}
        </div>
      </div>

      {/* ── Form fields (2-column grid) ──────────────────────────────────── */}
      <div className="form-grid-2col" style={{ marginBottom: '24px' }}>
        <div>
          <label className="settings-field-label" htmlFor="settings-name-input">
            Display name
          </label>
          <input
            id="settings-name-input"
            type="text"
            value={localName}
            onChange={(e) => setLocalName(e.target.value)}
            placeholder="Enter your name…"
            maxLength={50}
            className="settings-input"
          />
        </div>
        <div>
          <label className="settings-field-label">
            Email
          </label>
          <input
            type="email"
            placeholder="you@example.com"
            className="settings-input"
            disabled
            style={{ opacity: 0.5, cursor: 'not-allowed' }}
          />
        </div>
      </div>

      <div className="form-grid-2col" style={{ marginBottom: '24px' }}>
        <div>
          <label className="settings-field-label">
            Default scenario
          </label>
          <input
            type="text"
            value="Salary negotiation"
            className="settings-input"
            disabled
            style={{ opacity: 0.5, cursor: 'not-allowed' }}
          />
        </div>
        <div>
          <label className="settings-field-label">
            Difficulty
          </label>
          <input
            type="text"
            value="Adaptive"
            className="settings-input"
            disabled
            style={{ opacity: 0.5, cursor: 'not-allowed' }}
          />
        </div>
      </div>

      {/* ── Country selector ──────────────────────────────────────────────── */}
      <div style={{ marginBottom: '24px' }}>
        <label className="settings-field-label">
          <Globe
            style={{
              display: 'inline',
              width: '12px',
              height: '12px',
              marginRight: '4px',
              verticalAlign: 'middle',
            }}
          />
          Your country
        </label>

        {/* Selected country display */}
        {selectedCountry && (
          <div
            style={{
              marginBottom: '12px',
              padding: '12px 16px',
              border: '1px solid var(--accent)',
              borderRadius: '2px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              background: 'rgba(232, 83, 10, 0.06)',
            }}
          >
            <span style={{ fontSize: '24px' }}>{selectedCountry.flag}</span>
            <div>
              <p
                style={{
                  fontSize: '14px',
                  fontWeight: 500,
                  color: 'var(--text)',
                  margin: 0,
                }}
              >
                {selectedCountry.name}
              </p>
              <p
                style={{
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                  margin: 0,
                }}
              >
                {selectedCountry.currencySymbol} ({selectedCountry.currency}) — {selectedCountry.currencyName}
              </p>
            </div>
            <Check
              style={{
                marginLeft: 'auto',
                width: '16px',
                height: '16px',
                color: 'var(--accent)',
              }}
            />
          </div>
        )}

        {/* Search */}
        <div style={{ position: 'relative', marginBottom: '8px' }}>
          <Search
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '14px',
              height: '14px',
              color: 'var(--text-dim)',
            }}
          />
          <input
            id="settings-country-search"
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search countries…"
            className="settings-input"
            style={{ paddingLeft: '36px' }}
          />
        </div>

        {/* Country grid */}
        <div
          className="form-grid-2col"
          style={{
            maxHeight: '280px',
            overflowY: 'auto',
            gap: '4px',
          }}
        >
          {filtered.map((c) => {
            const isSelected = c.code === localCountry;
            return (
              <button
                key={c.code}
                id={`country-${c.code}`}
                onClick={() => setLocalCountry(c.code)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 12px',
                  border: `1px solid ${isSelected ? '#E8530A' : 'var(--border)'}`,
                  borderRadius: '2px',
                  background: isSelected ? 'rgba(232, 83, 10, 0.06)' : 'transparent',
                  color: isSelected ? 'var(--text)' : 'var(--text-muted)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'border-color 150ms ease',
                  width: '100%',
                  fontFamily: 'inherit',
                  fontSize: '13px',
                }}
              >
                <span>{c.flag}</span>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <p
                    style={{
                      fontSize: '13px',
                      fontWeight: isSelected ? 500 : 400,
                      color: isSelected ? 'var(--text)' : 'var(--text-muted)',
                      margin: 0,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {c.name}
                  </p>
                  <p
                    style={{
                      fontSize: '10px',
                      color: 'var(--text-dim)',
                      margin: 0,
                    }}
                  >
                    {c.currencySymbol} {c.currency}
                  </p>
                </div>
                {isSelected && (
                  <Check
                    style={{
                      width: '14px',
                      height: '14px',
                      color: '#E8530A',
                      flexShrink: 0,
                    }}
                  />
                )}
              </button>
            );
          })}
          {filtered.length === 0 && (
            <p
              style={{
                gridColumn: '1 / -1',
                textAlign: 'center',
                fontSize: '12px',
                color: 'var(--text-dim)',
                padding: '24px 0',
              }}
            >
              No countries match &quot;{search}&quot;
            </p>
          )}
        </div>
      </div>

      {/* ── Divider ──────────────────────────────────────────────────────── */}
      <hr className="settings-divider" />

      {/* ── LLM Provider ─────────────────────────────────────────────────── */}
      <div style={{ marginBottom: '24px' }}>
        <label className="settings-field-label">LLM provider</label>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <button
            className={`settings-chip ${llmProvider === 'ollama' ? 'settings-chip-active' : ''}`}
            onClick={() => setLlmProvider('ollama')}
          >
            Ollama
          </button>
          <button
            className={`settings-chip ${llmProvider === 'gemini' ? 'settings-chip-active' : ''}`}
            onClick={() => setLlmProvider('gemini')}
          >
            Gemini
          </button>
        </div>

        {llmProvider === 'ollama' && (
          <div>
            <label className="settings-field-label">Ollama base URL</label>
            <input
              type="text"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              className="settings-input"
            />
          </div>
        )}
      </div>

      {/* ── Save button ──────────────────────────────────────────────────── */}
      <button
        id="save-settings-btn"
        onClick={handleSave}
        disabled={!canSave || saved}
        className="settings-save-btn"
      >
        {saved ? (
          <>
            <Check
              style={{
                display: 'inline',
                width: '14px',
                height: '14px',
                verticalAlign: 'middle',
                marginRight: '6px',
              }}
            />
            Saved!
          </>
        ) : (
          'Save changes →'
        )}
      </button>

      <p
        style={{
          fontSize: '11px',
          color: 'var(--text-dim)',
          marginTop: '16px',
          fontFamily: 'var(--font-mono, monospace)',
        }}
      >
        Settings are saved locally and persist across sessions.
      </p>
    </div>
  );
}
