'use client';

import { ScenarioSummary } from '@/lib/api';

interface Props {
  scenario: ScenarioSummary;
  onSelect: (s: ScenarioSummary) => void;
  index: number;
}

export function ScenarioCard({ scenario, onSelect, index }: Props) {
  const num = String(index + 1).padStart(2, '0');

  return (
    <button
      id={`scenario-card-${scenario.id}`}
      onClick={() => onSelect(scenario)}
      className="scenario-card"
      style={{
        animationDelay: `${index * 80}ms`,
      }}
    >
      {/* Scenario number */}
      <p className="scenario-number">
        {num} —
      </p>

      {/* Name */}
      <h3 className="scenario-name">
        {scenario.display_name}
      </h3>

      {/* Description */}
      <p className="scenario-desc line-clamp-2">
        {scenario.description}
      </p>

      {/* Footer */}
      <div className="scenario-footer">
        <span className="scenario-range">
          {scenario.max_turns} turns · {scenario.value_unit}
        </span>
        <span className="scenario-cta">
          Start →
        </span>
      </div>
    </button>
  );
}
