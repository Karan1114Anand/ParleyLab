'use client';

import { ChatMessage, DateSeparator, TypingIndicator } from '@/components/ChatMessage';
import { CriticPanel } from '@/components/CriticPanel';
import { InputBox } from '@/components/InputBox';
import {
  ApiRequestError,
  CriticFeedback,
  StartSessionResponse,
  evaluateMove,
  submitMove,
} from '@/lib/api';
import { getAccent } from '@/store/useNegotiationStore';
import {
  ArrowLeft,
  Clock,
  Shield,
  Swords,
  Target,
  Trophy,
  Zap,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

// ── Types ──────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: 'user' | 'opponent';
  content: string;
  turn: number;
  isNew?: boolean;
}

interface SessionState {
  info: StartSessionResponse;
  messages: Message[];
  lastCritic: CriticFeedback | null;
  lastCriticTurn: number;
  isComplete: boolean;
  outcome: string | null;
  currentOpponentOffer: number;
  turn: number;
}

// ── Turn progress bar ──────────────────────────────────────────────────────────

function TurnBar({
  turn, maxTurns, accent,
}: { turn: number; maxTurns: number; accent: string }) {
  const pct = Math.min((turn / maxTurns) * 100, 100);
  const remaining = maxTurns - turn;
  const urgency = remaining <= 2 ? 'text-red-400' : remaining <= 4 ? 'text-amber-400' : 'text-white/40';
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${pct}%`,
            background: pct > 80
              ? 'linear-gradient(90deg,#fbbf24,#f87171)'
              : `linear-gradient(90deg, ${accent}, #8b5cf6)`,
          }}
        />
      </div>
      <span className={`text-xs font-mono shrink-0 ${urgency}`}>
        {remaining} left
      </span>
    </div>
  );
}

// ── Header bar ─────────────────────────────────────────────────────────────────

function NegotiationHeader({
  info, turn, accent, isComplete, onViewResults,
}: {
  info: StartSessionResponse;
  turn: number;
  accent: ReturnType<typeof getAccent>;
  isComplete: boolean;
  onViewResults: () => void;
}) {
  return (
    <header className="shrink-0 px-4 pt-4 pb-3 border-b border-white/[0.06]">
      <div className="max-w-5xl mx-auto flex items-center justify-between gap-4">
        {/* Left: back + scenario name */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => (window.location.href = '/')}
            className="shrink-0 w-8 h-8 rounded-lg bg-white/[0.05] border border-white/[0.06]
              flex items-center justify-center text-white/40 hover:text-white/80 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <p className="text-xs text-white/30 uppercase tracking-widest mb-0.5">Negotiation Room</p>
            <h1 className="font-bold text-white text-base leading-tight truncate">
              {info.scenario_display_name}
            </h1>
          </div>
        </div>

        {/* Center: role chips */}
        <div className="hidden sm:flex items-center gap-2 shrink-0">
          <span
            className="text-xs font-medium px-3 py-1 rounded-full border"
            style={{
              background: `${accent.primary}15`,
              borderColor: `${accent.primary}35`,
              color: accent.primary,
            }}
          >
            {info.user_role}
          </span>
          <Swords className="w-3.5 h-3.5 text-white/20" />
          <span className="text-xs font-medium px-3 py-1 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-300">
            {info.opponent_role}
          </span>
        </div>

        {/* Right: results CTA or turn info */}
        {isComplete ? (
          <button
            id="view-results-btn"
            onClick={onViewResults}
            className="shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold
              text-white animate-fade-up"
            style={{
              background: `linear-gradient(135deg, ${accent.primary}, #8b5cf6)`,
              boxShadow: `0 4px 20px ${accent.glow}`,
            }}
          >
            <Trophy className="w-4 h-4" />
            View Results
          </button>
        ) : (
          <div className="flex items-center gap-2 text-xs text-white/30 shrink-0">
            <Clock className="w-3.5 h-3.5" />
            <span>Turn {turn}/{info.max_turns}</span>
          </div>
        )}
      </div>

      {/* Turn progress */}
      <div className="max-w-5xl mx-auto mt-2.5">
        <TurnBar turn={turn} maxTurns={info.max_turns} accent={accent.primary} />
      </div>
    </header>
  );
}

// ── Role brief strip ───────────────────────────────────────────────────────────

function RoleStrip({
  info, accent,
}: { info: StartSessionResponse; accent: ReturnType<typeof getAccent> }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="shrink-0 border-b border-white/[0.04] cursor-pointer"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="max-w-5xl mx-auto px-4 py-2.5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 text-xs text-white/40 min-w-0">
          <span className="flex items-center gap-1.5 shrink-0">
            <Target className="w-3 h-3" style={{ color: accent.primary }} />
            <span className="text-white/60">Target</span>
            <span className="font-mono font-semibold text-white/80">
              {info.user_brief.target.toLocaleString()} {info.value_unit}
            </span>
          </span>
          <span className="hidden sm:flex items-center gap-1.5 shrink-0">
            <Shield className="w-3 h-3 text-amber-400" />
            <span className="text-white/60">BATNA</span>
            <span className="font-mono font-semibold text-white/80">
              {info.user_brief.batna.toLocaleString()} {info.value_unit}
            </span>
          </span>
          {expanded && (
            <span className="text-white/40 text-[11px] line-clamp-1 animate-fade-up">
              {info.user_brief.context}
            </span>
          )}
        </div>
        <span className="text-[10px] text-white/20 shrink-0">
          {expanded ? '▲ hide' : '▼ context'}
        </span>
      </div>
    </div>
  );
}

// ── Completion banner ──────────────────────────────────────────────────────────

function CompletionBanner({
  outcome, accent,
}: { outcome: string | null; accent: ReturnType<typeof getAccent> }) {
  const config = {
    deal_closed: { emoji: '🤝', text: 'Deal reached!', sub: 'View your results to see how you performed.', color: '#34d399' },
    walked_away: { emoji: '🚶', text: 'Opponent walked.', sub: 'No deal was reached. Check your results.', color: '#f87171' },
    timeout:     { emoji: '⏱️', text: 'Time\'s up.', sub: 'Maximum turns reached. See your score.', color: '#fbbf24' },
  }[outcome ?? ''] ?? { emoji: '🏁', text: 'Complete', sub: '', color: accent.primary };

  return (
    <div
      className="shrink-0 mx-4 mb-3 px-4 py-3 rounded-2xl border text-center animate-fade-up"
      style={{
        background: `${config.color}08`,
        borderColor: `${config.color}30`,
      }}
    >
      <span className="text-lg mr-2">{config.emoji}</span>
      <span className="text-sm font-semibold" style={{ color: config.color }}>{config.text}</span>
      <span className="text-sm text-white/40 ml-2">{config.sub}</span>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function NegotiationPage({
  params,
}: {
  params: { id: string };
}) {
  const router = useRouter();
  const sessionId = params.id;

  const [session, setSession] = useState<SessionState | null>(null);
  const [scenarioId, setScenarioId] = useState('salary_v1');
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);



  // ── Load session from sessionStorage ────────────────────────────────────────
  useEffect(() => {
    const stored = sessionStorage.getItem(`session_${sessionId}`);
    if (!stored) {
      router.replace('/');
      return;
    }
    const info: StartSessionResponse = JSON.parse(stored);
    // sessionStorage may also store the scenario_id from RoleBriefScreen
    const storedScenarioId = sessionStorage.getItem(`scenario_id_${sessionId}`) ?? 'salary_v1';
    setScenarioId(storedScenarioId);
    setSession({
      info,
      messages: [{
        id: 'opener',
        role: 'opponent',
        content: info.opponent_opener,
        turn: 0,
        isNew: true,
      }],
      lastCritic: null,
      lastCriticTurn: 0,
      isComplete: false,
      outcome: null,
      currentOpponentOffer: info.opening_offer,
      turn: 0,
    });
  }, [sessionId, router]);

  // ── Auto-scroll to bottom on new messages ──────────────────────────────────
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    chatEndRef.current?.scrollIntoView({ behavior, block: 'end' });
  }, []);

  useEffect(() => {
    // Immediate on first load
    if (session?.messages.length === 1) scrollToBottom('instant' as ScrollBehavior);
    else scrollToBottom();
  }, [session?.messages, isThinking, scrollToBottom]);

  // ── Submit move ─────────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async (userMessage: string) => {
    if (!session || isThinking || session.isComplete) return;
    setError(null);

    // Optimistic: add user bubble immediately
    const optimisticMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: userMessage,
      turn: session.turn + 1,
      isNew: true,
    };
    setSession((prev) =>
      prev ? { ...prev, messages: [...prev.messages, optimisticMsg] } : prev
    );
    setIsThinking(true);

    try {
      const res = await submitMove(sessionId, userMessage);

      const oppMsg: Message = {
        id: `o-${Date.now()}`,
        role: 'opponent',
        content: res.opponent_response,
        turn: res.turn_number,
        isNew: true,
      };

      setSession((prev) =>
        prev
          ? {
              ...prev,
              messages: [...prev.messages, oppMsg],
              isComplete: res.is_complete,
              outcome: res.outcome ?? null,
              currentOpponentOffer: res.opponent_current_offer,
              turn: res.turn_number,
            }
          : prev
      );
      setIsThinking(false);

      // Async critic — fire and forget
      evaluateMove(sessionId, userMessage, res.turn_number)
        .then((evalRes) => {
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  lastCritic: evalRes.critic_feedback,
                  lastCriticTurn: res.turn_number,
                }
              : prev
          );
        })
        .catch((e) => console.warn('Critic eval (non-fatal):', e));
    } catch (e: unknown) {
      // Surface a user-friendly error — detect specific API failure modes
      let errorMsg = 'Something went wrong. Please try again.';
      if (e instanceof ApiRequestError) {
        if (e.status === 429) {
          errorMsg = '⚠️ Gemini API quota exhausted. The free tier limit has been reached. Get a new key at https://aistudio.google.com/apikey';
        } else if (e.status === 401) {
          errorMsg = '🔑 Invalid Gemini API key. Keys must start with "AIza". Get one at https://aistudio.google.com/apikey';
        } else if (e.status === 409) {
          errorMsg = 'This negotiation has already ended.';
        } else if (e.status === 504) {
          errorMsg = '⏱️ The AI took too long to respond. Please try again.';
        } else {
          errorMsg = e.message || errorMsg;
        }
      } else if (e instanceof Error) {
        errorMsg = e.message || errorMsg;
      }
      setError(errorMsg);
      // Roll back optimistic message
      setSession((prev) =>
        prev ? { ...prev, messages: prev.messages.slice(0, -1) } : prev
      );
      setIsThinking(false);
    }
  }, [session, isThinking, sessionId]);

  // ── Loading state ───────────────────────────────────────────────────────────
  if (!session) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          <p className="text-sm text-white/30">Loading negotiation room…</p>
        </div>
      </div>
    );
  }

  const { info } = session;
  const accent = getAccent(scenarioId);
  const inputDisabled = isThinking || session.isComplete;

  return (
    <div className="h-screen flex flex-col overflow-hidden">

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <NegotiationHeader
        info={info}
        turn={session.turn}
        accent={accent}
        isComplete={session.isComplete}
        onViewResults={() => router.push(`/results/${sessionId}`)}
      />

      {/* ── Role strip ───────────────────────────────────────────────────── */}
      <RoleStrip info={info} accent={accent} />

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex min-h-0 max-w-5xl w-full mx-auto px-4 py-4 gap-5">

        {/* ── Chat column ──────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-h-0 gap-3">

          {/* Messages scroll area */}
          <div
            ref={chatScrollRef}
            className="flex-1 overflow-y-auto pr-1 space-y-4 scroll-smooth"
            style={{ scrollbarGutter: 'stable' }}
          >
            {/* Session start divider */}
            <DateSeparator label="Session started" />

            {session.messages.map((msg, i) => {
              // Insert a divider between opener and first real turn
              const showDivider = i === 1 && session.messages[0].role === 'opponent';
              return (
                <div key={msg.id}>
                  {showDivider && <DateSeparator label="Negotiation begins" />}
                  <ChatMessage
                    role={msg.role}
                    content={msg.content}
                    turn={msg.turn}
                    opponentRole={info.opponent_role}
                    accentColor={accent.primary}
                    isNew={msg.isNew}
                  />
                </div>
              );
            })}

            {/* Typing indicator */}
            {isThinking && (
              <TypingIndicator
                opponentRole={info.opponent_role}
                accentColor={accent.primary}
              />
            )}

            {/* Error inline */}
            {error && (
              <div className="mx-auto max-w-sm px-4 py-2.5 rounded-xl bg-red-500/5 border border-red-500/20 animate-fade-up">
                <p className="text-xs text-red-300 text-center">{error}</p>
              </div>
            )}

            {/* Scroll anchor */}
            <div ref={chatEndRef} className="h-2" />
          </div>

          {/* Completion banner above input */}
          {session.isComplete && (
            <CompletionBanner outcome={session.outcome} accent={accent} />
          )}

          {/* Input box */}
          <div className="shrink-0">
            <InputBox
              onSubmit={handleSubmit}
              disabled={inputDisabled}
              accentColor={accent.primary}
              placeholder={
                session.isComplete
                  ? 'Negotiation ended — view your results above'
                  : `Make your offer in ${info.value_unit}…`
              }
            />
          </div>
        </div>

        {/* ── Critic sidebar — desktop ──────────────────────────────────── */}
        <div className="hidden lg:flex flex-col w-72 shrink-0 gap-3">

          {/* Offer tracker */}
          <div className="rounded-2xl bg-white/[0.03] border border-white/[0.06] p-4">
            <p className="text-[10px] text-white/30 uppercase tracking-widest mb-3 font-semibold">
              Live Offer Tracker
            </p>
            <div className="flex items-end justify-between gap-2">
              <div>
                <p className="text-[10px] text-white/30 mb-1">Opponent offering</p>
                <p
                  className="text-2xl font-bold font-mono"
                  style={{ color: accent.primary }}
                >
                  {session.currentOpponentOffer.toLocaleString()}
                </p>
                <p className="text-[10px] text-white/30 mt-0.5">{info.value_unit}</p>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-white/30 mb-1">Your target</p>
                <p className="text-lg font-bold font-mono text-white/60">
                  {info.user_brief.target.toLocaleString()}
                </p>
              </div>
            </div>

            {/* Gap bar */}
            <div className="mt-3">
              <div className="h-1 bg-white/[0.05] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.max(0, 100 - Math.abs(session.currentOpponentOffer - info.user_brief.target) /
                        Math.max(Math.abs(info.opening_offer - info.user_brief.target), 1) * 100)
                    )}%`,
                    background: `linear-gradient(90deg, #f87171, ${accent.primary})`,
                  }}
                />
              </div>
              <p className="text-[9px] text-white/20 mt-1 text-center">
                Gap: {Math.abs(session.currentOpponentOffer - info.user_brief.target).toLocaleString()} {info.value_unit}
              </p>
            </div>
          </div>

          {/* Critic panel */}
          {session.lastCritic ? (
            <div className="flex-1 overflow-y-auto">
              <p className="text-[10px] text-white/30 uppercase tracking-widest mb-2 font-semibold flex items-center gap-1.5">
                <Zap className="w-3 h-3" style={{ color: accent.primary }} />
                Live Coaching
              </p>
              <CriticPanel
                feedback={session.lastCritic}
                turn={session.lastCriticTurn}
              />
            </div>
          ) : (
            <div className="flex-1 rounded-2xl border border-white/[0.04] bg-white/[0.02] flex items-center justify-center p-6">
              <div className="text-center">
                <Zap className="w-6 h-6 text-white/10 mx-auto mb-2" />
                <p className="text-xs text-white/20">
                  Coaching feedback will appear after your first move.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Mobile critic — below chat ────────────────────────────────────── */}
      {session.lastCritic && (
        <div className="lg:hidden border-t border-white/[0.05] px-4 py-3 shrink-0">
          <p className="text-[10px] text-white/30 uppercase tracking-widest mb-2 font-semibold">
            Live Coaching
          </p>
          <CriticPanel feedback={session.lastCritic} turn={session.lastCriticTurn} />
        </div>
      )}
    </div>
  );
}
