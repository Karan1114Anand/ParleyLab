'use client';

import { UserBrief } from '@/lib/api';
import { Shield, Target } from 'lucide-react';

interface Props {
  userRole: string;
  opponentRole: string;
  userBrief: UserBrief;
  valueUnit: string;
  turn: number;
  maxTurns: number;
}

export function RoleBrief({
  userRole,
  opponentRole,
  userBrief,
  valueUnit,
  turn,
  maxTurns,
}: Props) {
  const turnsLeft = maxTurns - turn;
  const progress = turn / maxTurns;
  const progressColor =
    progress > 0.75 ? 'bg-red-500' : progress > 0.5 ? 'bg-amber-500' : 'bg-brand-500';

  return (
    <div className="glass rounded-xl p-4 mb-4">
      <div className="flex flex-wrap items-start gap-4 justify-between">
        {/* Role */}
        <div>
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-1">
            Your Role
          </p>
          <p className="font-semibold text-white">
            {userRole}{' '}
            <span className="text-[var(--text-muted)] font-normal">vs</span>{' '}
            {opponentRole}
          </p>
        </div>

        {/* Target */}
        <div className="flex items-center gap-1.5">
          <Target className="w-4 h-4 text-brand-400" />
          <div>
            <p className="text-xs text-[var(--text-muted)]">Target</p>
            <p className="font-semibold text-brand-300">
              {userBrief.target.toLocaleString()} {valueUnit}
            </p>
          </div>
        </div>

        {/* BATNA */}
        <div className="flex items-center gap-1.5">
          <Shield className="w-4 h-4 text-amber-400" />
          <div>
            <p className="text-xs text-[var(--text-muted)]">BATNA (Walk-away)</p>
            <p className="font-semibold text-amber-300">
              {userBrief.batna.toLocaleString()} {valueUnit}
            </p>
          </div>
        </div>

        {/* Turn counter */}
        <div className="text-right">
          <p className="text-xs text-[var(--text-muted)]">Turns left</p>
          <p
            className={`font-bold text-lg ${
              turnsLeft <= 2 ? 'text-red-400' : 'text-white'
            }`}
          >
            {turnsLeft}
          </p>
        </div>
      </div>

      {/* Context */}
      <p className="text-xs text-[var(--text-muted)] mt-3 border-t border-white/5 pt-3 leading-relaxed">
        📋 {userBrief.context}
      </p>

      {/* Progress bar */}
      <div className="mt-3 h-1 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
          style={{ width: `${progress * 100}%` }}
        />
      </div>
    </div>
  );
}
