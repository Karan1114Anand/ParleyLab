'use client';

import { Bot, Check, CheckCheck, User } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

// ── Types ──────────────────────────────────────────────────────────────────────

interface ChatMessageProps {
  role: 'user' | 'opponent';
  content: string;
  turn?: number;
  opponentRole?: string;
  accentColor?: string;   // hex — for scenario-themed user bubble
  isNew?: boolean;        // drives the entry animation
}

// ── Helpers ────────────────────────────────────────────────────────────────────

/** Formats raw text: preserves line-breaks, no other processing. */
function MessageText({ text }: { text: string }) {
  return (
    <>
      {text.split('\n').map((line, i) => (
        <span key={i}>
          {line}
          {i < text.split('\n').length - 1 && <br />}
        </span>
      ))}
    </>
  );
}

/** Timestamp label — shown once after the bubble renders. */
function Timestamp({ isUser }: { isUser: boolean }) {
  const now = new Date();
  const label = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return (
    <span className={`text-[10px] text-white/20 px-1 ${isUser ? 'text-right' : ''}`}>
      {label}
    </span>
  );
}

// ── ChatMessage ────────────────────────────────────────────────────────────────

/**
 * Premium chat bubble component with:
 * - Direction-aware layout (user = right, opponent = left)
 * - Scenario-accent user bubble colour
 * - Smooth slide-in entry animation per side
 * - Animated "delivered" checkmark for user messages
 * - Subtle shimmer glow on new messages
 */
export function ChatMessage({
  role,
  content,
  turn,
  opponentRole,
  accentColor = '#6470f3',
  isNew = true,
}: ChatMessageProps) {
  const isUser = role === 'user';
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Tiny delay so React batches the paint before animating
    const t = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(t);
  }, []);

  return (
    <div
      className={`
        flex gap-3 w-full
        ${isUser ? 'flex-row-reverse' : 'flex-row'}
        ${isNew ? (isUser ? 'animate-slide-right' : 'animate-slide-left') : ''}
      `}
    >
      {/* ── Avatar ─────────────────────────────────────────────────────── */}
      <div className="shrink-0 flex flex-col items-center gap-1 pt-0.5">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300"
          style={isUser
            ? {
                background: `${accentColor}25`,
                boxShadow: `0 0 0 1px ${accentColor}40`,
              }
            : {
                background: 'rgba(192,132,252,0.15)',
                boxShadow: '0 0 0 1px rgba(192,132,252,0.25)',
              }
          }
        >
          {isUser
            ? <User className="w-4 h-4" style={{ color: accentColor }} />
            : <Bot className="w-4 h-4 text-purple-300" />
          }
        </div>
        {/* Role label below avatar */}
        <span className="text-[9px] text-white/25 leading-none text-center w-8 truncate">
          {isUser ? 'You' : (opponentRole?.split(' ')[0] ?? 'AI')}
        </span>
      </div>

      {/* ── Bubble ─────────────────────────────────────────────────────── */}
      <div className={`flex flex-col gap-1 max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>

        {/* Turn badge */}
        {turn !== undefined && turn > 0 && (
          <span className="text-[9px] text-white/20 font-mono px-1">
            Turn {turn}
          </span>
        )}

        {/* Bubble itself */}
        <div
          className={`
            relative px-4 py-3 text-sm leading-relaxed rounded-2xl
            transition-all duration-200 group
            ${isUser
              ? 'rounded-tr-[4px] text-white'
              : 'rounded-tl-[4px] text-white/90 bg-white/[0.05] border border-white/[0.07]'
            }
          `}
          style={isUser ? {
            background: `linear-gradient(135deg, ${accentColor}35, ${accentColor}20)`,
            border: `1px solid ${accentColor}30`,
            boxShadow: isNew ? `0 4px 20px ${accentColor}15` : 'none',
          } : {
            boxShadow: isNew ? '0 4px 20px rgba(0,0,0,0.3)' : 'none',
          }}
        >
          {/* Shimmer sweep on new message */}
          {isNew && (
            <div
              className="absolute inset-0 rounded-2xl pointer-events-none overflow-hidden"
              style={{ opacity: 0.6, animation: 'msgShimmer 0.8s ease-out forwards' }}
            >
              <div
                className="absolute inset-0"
                style={{
                  background: `linear-gradient(105deg, transparent 30%, rgba(255,255,255,0.06) 50%, transparent 70%)`,
                  transform: 'translateX(-100%)',
                  animation: 'shimmerSweep 0.7s ease-out 0.1s forwards',
                }}
              />
            </div>
          )}

          <MessageText text={content} />

          {/* Delivered indicator — user only */}
          {isUser && (
            <span className="absolute -bottom-0.5 -right-0.5 opacity-60">
              <CheckCheck className="w-3 h-3" style={{ color: accentColor }} />
            </span>
          )}
        </div>

        {/* Timestamp */}
        <Timestamp isUser={isUser} />
      </div>
    </div>
  );
}

// ── TypingIndicator ────────────────────────────────────────────────────────────

interface TypingProps {
  opponentRole: string;
  accentColor?: string;
}

/**
 * Premium typing indicator with:
 * - Three animated dots with sequential delays
 * - Animated "thinking" text that cycles through states
 * - Smooth fade-up entry
 */
export function TypingIndicator({ opponentRole, accentColor }: TypingProps) {
  const phases = ['Thinking', 'Calculating', 'Responding'];
  const [phaseIdx, setPhaseIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setPhaseIdx((i) => (i + 1) % phases.length), 1800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex gap-3 animate-fade-up">
      {/* Avatar */}
      <div className="shrink-0 flex flex-col items-center gap-1 pt-0.5">
        <div className="w-8 h-8 rounded-full bg-purple-500/15 border border-purple-500/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-purple-300" />
        </div>
        <span className="text-[9px] text-white/25 leading-none text-center w-8 truncate">
          {opponentRole?.split(' ')[0] ?? 'AI'}
        </span>
      </div>

      {/* Bubble */}
      <div className="flex flex-col gap-1 items-start">
        <div className="px-4 py-3 rounded-2xl rounded-tl-[4px] bg-white/[0.05] border border-white/[0.07]">
          <div className="flex items-center gap-3">
            {/* Dots */}
            <div className="flex items-center gap-1.5">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-white/40"
                  style={{
                    animation: `typingDot 1.4s ease-in-out ${i * 0.16}s infinite`,
                  }}
                />
              ))}
            </div>
            {/* Phase text */}
            <span
              key={phaseIdx}
              className="text-xs text-white/30"
              style={{ animation: 'fadeIn 0.3s ease-out' }}
            >
              {phases[phaseIdx]}…
            </span>
          </div>
        </div>
        <span className="text-[9px] text-white/20 px-1">
          {opponentRole}
        </span>
      </div>

      <style jsx>{`
        @keyframes typingDot {
          0%, 60%, 100% { transform: translateY(0);    opacity: 0.4; }
          30%            { transform: translateY(-5px); opacity: 1;   }
        }
        @keyframes shimmerSweep {
          from { transform: translateX(-100%); }
          to   { transform: translateX(200%);  }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ── DateSeparator ──────────────────────────────────────────────────────────────

export function DateSeparator({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 my-2">
      <div className="flex-1 h-px bg-white/[0.05]" />
      <span className="text-[10px] text-white/20 font-medium uppercase tracking-widest px-2">
        {label}
      </span>
      <div className="flex-1 h-px bg-white/[0.05]" />
    </div>
  );
}
