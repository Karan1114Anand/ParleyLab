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

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-8 relative overflow-hidden">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute w-[600px] h-[600px] rounded-full blur-3xl opacity-15"
          style={{
            background: 'radial-gradient(circle, #6470f3 0%, transparent 70%)',
            top: '-15%',
            right: '-10%',
          }}
        />
        <div
          className="absolute w-[400px] h-[400px] rounded-full blur-3xl opacity-10"
          style={{
            background: 'radial-gradient(circle, #c084fc 0%, transparent 70%)',
            bottom: '-10%',
            left: '-5%',
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      <div className="relative z-10 w-full max-w-2xl">
        {/* Back button */}
        <button
          onClick={() => router.push('/')}
          className="flex items-center gap-2 text-sm text-white/40 hover:text-white/80 transition-colors mb-8 group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to home
        </button>

        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 mb-5 px-4 py-2 rounded-full bg-white/[0.06] border border-white/[0.1] backdrop-blur-sm">
            <User className="w-3.5 h-3.5 text-brand-400" />
            <span className="text-xs font-semibold text-brand-300 tracking-wide uppercase">
              Profile Settings
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight mb-3">
            Your Profile
          </h1>
          <p className="text-white/40 text-lg max-w-md mx-auto">
            Set your name and country so the AI can personalize your negotiation experience.
          </p>
        </div>

        {/* ── Name field ────────────────────────────────────────────────────── */}
        <div className="mb-8">
          <label className="block text-xs text-white/40 uppercase tracking-widest font-semibold mb-3">
            Your Name
          </label>
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/25" />
            <input
              id="settings-name-input"
              type="text"
              value={localName}
              onChange={(e) => setLocalName(e.target.value)}
              placeholder="Enter your name…"
              maxLength={50}
              className="w-full pl-12 pr-4 py-4 rounded-2xl
                bg-white/[0.04] border border-white/[0.08]
                text-white text-lg placeholder:text-white/20
                focus:outline-none focus:border-brand-500/50 focus:bg-white/[0.06]
                transition-all duration-200"
            />
          </div>
          <p className="text-xs text-white/25 mt-2 ml-1">
            The AI opponent will address you by this name during negotiations.
          </p>
        </div>

        {/* ── Country selector ──────────────────────────────────────────────── */}
        <div className="mb-8">
          <label className="block text-xs text-white/40 uppercase tracking-widest font-semibold mb-3">
            <Globe className="inline w-3.5 h-3.5 mr-1.5 -mt-0.5" />
            Your Country
          </label>

          {/* Selected country display */}
          {selectedCountry && (
            <div
              className="mb-4 px-5 py-4 rounded-2xl border flex items-center gap-4"
              style={{
                background: 'rgba(100,112,243,0.08)',
                borderColor: 'rgba(100,112,243,0.25)',
              }}
            >
              <span className="text-3xl">{selectedCountry.flag}</span>
              <div>
                <p className="text-white font-semibold text-lg">{selectedCountry.name}</p>
                <p className="text-white/40 text-sm">
                  Currency: {selectedCountry.currencySymbol} ({selectedCountry.currency}) — {selectedCountry.currencyName}
                </p>
              </div>
              <Check className="ml-auto w-5 h-5 text-brand-400" />
            </div>
          )}

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
            <input
              id="settings-country-search"
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search countries…"
              className="w-full pl-11 pr-4 py-3 rounded-xl
                bg-white/[0.03] border border-white/[0.06]
                text-white text-sm placeholder:text-white/20
                focus:outline-none focus:border-white/20
                transition-all duration-200"
            />
          </div>

          {/* Country grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[360px] overflow-y-auto pr-1 rounded-xl"
            style={{ scrollbarWidth: 'thin' }}
          >
            {filtered.map((country) => {
              const isSelected = country.code === localCountry;
              return (
                <button
                  key={country.code}
                  id={`country-${country.code}`}
                  onClick={() => setLocalCountry(country.code)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-all duration-200 ${
                    isSelected
                      ? 'bg-brand-500/10 border-brand-500/40'
                      : 'bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.05] hover:border-white/[0.12]'
                  }`}
                >
                  <span className="text-xl">{country.flag}</span>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-medium truncate ${isSelected ? 'text-white' : 'text-white/70'}`}>
                      {country.name}
                    </p>
                    <p className="text-[11px] text-white/30">
                      {country.currencySymbol} {country.currency}
                    </p>
                  </div>
                  {isSelected && (
                    <Check className="w-4 h-4 text-brand-400 shrink-0" />
                  )}
                </button>
              );
            })}
            {filtered.length === 0 && (
              <p className="col-span-2 text-center text-sm text-white/20 py-6">
                No countries match "{search}"
              </p>
            )}
          </div>
        </div>

        {/* ── Save button ──────────────────────────────────────────────────── */}
        <div className="flex justify-center">
          <button
            id="save-settings-btn"
            onClick={handleSave}
            disabled={!canSave || saved}
            className="relative px-10 py-4 rounded-2xl font-bold text-white text-lg
              flex items-center justify-center gap-3 overflow-hidden
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
            style={{
              background: saved
                ? 'linear-gradient(135deg, #34d399, #059669)'
                : 'linear-gradient(135deg, #6470f3, #8b5cf6)',
              boxShadow: saved
                ? '0 8px 32px rgba(52,211,153,0.35)'
                : canSave
                ? '0 8px 32px rgba(100,112,243,0.35)'
                : 'none',
            }}
          >
            {saved ? (
              <>
                <Check className="w-5 h-5" />
                <span>Saved!</span>
              </>
            ) : (
              <>
                <Check className="w-5 h-5" />
                <span>Save Settings</span>
              </>
            )}
          </button>
        </div>

        <p className="text-center text-xs text-white/20 mt-6">
          Settings are saved locally and persist across sessions.
        </p>
      </div>
    </div>
  );
}
