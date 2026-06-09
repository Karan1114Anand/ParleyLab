'use client';

import { ScenarioSummary } from '@/lib/api';
import { getAccent } from '@/store/useNegotiationStore';
import { ArrowRight, Clock, Zap } from 'lucide-react';
import { useRef, useState } from 'react';

interface Props {
  scenario: ScenarioSummary;
  onSelect: (s: ScenarioSummary) => void;
  index: number;
}

/**
 * Premium ScenarioCard with:
 * - Per-scenario accent colour theming
 * - Mouse-tracking 3D tilt effect
 * - Glowing border on hover
 * - Staggered fade-up entry animation
 */
export function ScenarioCard({ scenario, onSelect, index }: Props) {
  const accent = getAccent(scenario.id);
  const cardRef = useRef<HTMLButtonElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 12;
    const y = -((e.clientY - rect.top) / rect.height - 0.5) * 12;
    setTilt({ x, y });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
    setHovered(false);
  };

  return (
    <button
      ref={cardRef}
      id={`scenario-card-${scenario.id}`}
      onClick={() => onSelect(scenario)}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        transform: hovered
          ? `perspective(800px) rotateX(${tilt.y}deg) rotateY(${tilt.x}deg) scale(1.02)`
          : 'perspective(800px) rotateX(0) rotateY(0) scale(1)',
        transition: hovered ? 'transform 0.1s ease-out' : 'transform 0.4s ease-out',
        animationDelay: `${index * 100}ms`,
        boxShadow: hovered ? `0 20px 60px ${accent.glow}` : '0 4px 24px rgba(0,0,0,0.3)',
      }}
      className="
        group relative w-full text-left rounded-2xl
        bg-white/[0.04] border border-white/[0.08]
        backdrop-filter backdrop-blur-xl
        cursor-pointer animate-fade-up
        focus:outline-none focus-visible:ring-2 focus-visible:ring-white/30
        overflow-hidden
      "
    >
      {/* Accent glow overlay on hover */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
        style={{ background: `radial-gradient(ellipse at 30% 30%, ${accent.glow} 0%, transparent 70%)` }}
      />

      {/* Accent border on hover */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
        style={{ boxShadow: `inset 0 0 0 1px ${accent.primary}60` }}
      />

      <div className="relative p-6">
        {/* Top row — icon + arrow */}
        <div className="flex items-start justify-between mb-5">
          {/* Icon circle */}
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl shrink-0"
            style={{
              background: `${accent.primary}18`,
              border: `1px solid ${accent.primary}30`,
              boxShadow: hovered ? `0 0 20px ${accent.glow}` : 'none',
              transition: 'box-shadow 0.3s ease',
            }}
          >
            {scenario.icon}
          </div>

          <div
            className="w-8 h-8 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-2 group-hover:translate-x-0"
            style={{ background: `${accent.primary}20`, border: `1px solid ${accent.primary}40` }}
          >
            <ArrowRight className="w-4 h-4" style={{ color: accent.primary }} />
          </div>
        </div>

        {/* Title + roles */}
        <h3 className="font-bold text-white text-xl mb-1 leading-tight">
          {scenario.display_name}
        </h3>
        <p className="text-xs mb-3" style={{ color: accent.primary }}>
          {scenario.user_role} <span className="text-white/30 mx-1">vs</span> {scenario.opponent_role}
        </p>

        {/* Description */}
        <p className="text-sm text-white/50 leading-relaxed mb-5 line-clamp-2">
          {scenario.description}
        </p>

        {/* Footer */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 text-xs text-white/35">
            <span className="flex items-center gap-1.5">
              <Clock className="w-3 h-3" />
              {scenario.max_turns} turns
            </span>
            <span className="w-0.5 h-0.5 rounded-full bg-white/20" />
            <span className="font-mono">{scenario.value_unit}</span>
          </div>

          <span
            className="text-[10px] font-semibold uppercase tracking-widest px-2.5 py-1 rounded-full border"
            style={{
              background: `${accent.primary}15`,
              borderColor: `${accent.primary}35`,
              color: accent.primary,
            }}
          >
            Play
          </span>
        </div>

        {/* Bottom accent line */}
        <div
          className="absolute bottom-0 left-0 right-0 h-[1px] opacity-0 group-hover:opacity-100 transition-opacity duration-500"
          style={{ background: `linear-gradient(90deg, transparent, ${accent.primary}, transparent)` }}
        />
      </div>
    </button>
  );
}
