/**
 * Typed FastAPI client for ParleyLab — v2
 *
 * Routes to use:
 *   GET  /api/scenario/list      → listScenarios()
 *   POST /api/scenario/start     → startSession()
 *   POST /api/chat/message       → submitMove()
 *   POST /api/chat/evaluate      → evaluateMove()
 *   GET  /session/{id}/reveal    → revealSession()   (legacy, kept)
 *   GET  /healthz                → getHealth()
 *
 * All network calls go through this module. Never call fetch() directly
 * from a page or component — always use these typed wrappers.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// ── Type definitions (must exactly match backend schemas/responses.py) ─────────

export interface ScenarioSummary {
  id:            string;
  display_name:  string;
  user_role:     string;
  opponent_role: string;
  icon:          string;
  description:   string;
  max_turns:     number;
  value_unit:    string;
}

export interface UserBrief {
  target:  number;
  batna:   number;
  context: string;
}

/** Returned by POST /api/scenario/start */
export interface StartSessionResponse {
  session_id:            string;
  user_role:             string;
  opponent_role:         string;
  user_brief:            UserBrief;
  opening_offer:         number;
  opponent_opener:       string;
  max_turns:             number;
  value_unit:            string;
  scenario_display_name: string;
}

export interface CriticFeedback {
  strengths:   string[];
  weaknesses:  string[];
  suggestion:  string;
  concept_tag: string;
}

/** Returned by POST /api/chat/message */
export interface MoveResponse {
  turn_number:            number;
  opponent_response:      string;
  opponent_current_offer: number;
  critic_feedback:        CriticFeedback | null;
  is_complete:            boolean;
  outcome:                'deal_closed' | 'walked_away' | 'timeout' | null;
}

/** Returned by POST /api/chat/evaluate */
export interface EvaluateResponse {
  session_id:      string;
  turn_number:     number;
  critic_feedback: CriticFeedback;
}

export interface OpponentHidden {
  target:  number;
  batna:   number;
  persona: string;
  urgency: string;
}

export interface Performance {
  score:      number;
  rating:     string;
  best_move:  { turn: number; summary: string } | null;
  worst_move: { turn: number; summary: string } | null;
}

export interface TranscriptMessage {
  role:      string;
  content:   string;
  turn:      number;
  timestamp: string;
}

export interface RevealResponse {
  outcome:          string;
  final_deal_value: number | null;
  opponent_hidden:  OpponentHidden;
  performance:      Performance;
  full_transcript:  TranscriptMessage[];
  value_unit:       string;
}

export interface HealthResponse {
  status:          string;
  rl_model_loaded: boolean;
  llm_provider:    string;
}

/** Standard error envelope from the backend */
export interface ApiError {
  error:  string;
  detail: string;
  errors: { field: string | null; message: string }[];
}

// ── Internal helpers ───────────────────────────────────────────────────────────

class ApiRequestError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly errors: ApiError['errors'] = [],
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let code    = `http_${res.status}`;
    let detail  = `HTTP ${res.status}`;
    let errors: ApiError['errors'] = [];
    try {
      const err: ApiError = await res.json();
      code   = err.error  ?? code;
      detail = err.detail ?? detail;
      errors = err.errors ?? [];
    } catch {
      // ignore JSON parse failure on error body
    }
    throw new ApiRequestError(code, detail, res.status, errors);
  }

  // Safe parse: backend should always return JSON on success, but guard anyway.
  const rawText = await res.text();
  try {
    return JSON.parse(rawText) as T;
  } catch {
    // Backend returned non-JSON with a 2xx status — surface it as a typed error
    const preview = rawText.slice(0, 200);
    console.error('[api] Non-JSON success response:', preview);
    throw new ApiRequestError(
      'invalid_response',
      `Server returned a non-JSON response: ${preview}`,
      res.status,
    );
  }
}

// ── Public API ─────────────────────────────────────────────────────────────────

/** Check backend health. */
export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/healthz');
}

/**
 * List all available negotiation scenarios.
 * Returns the flat array for backward compat with existing components.
 */
export async function listScenarios(): Promise<ScenarioSummary[]> {
  const res = await request<{ scenarios: ScenarioSummary[]; count: number }>(
    '/api/scenario/list',
  );
  return res.scenarios;
}

/**
 * Create a new negotiation session from a scenario ID.
 * POST /api/scenario/start
 */
export async function startSession(
  scenario_id: string,
): Promise<StartSessionResponse> {
  return request<StartSessionResponse>('/api/scenario/start', {
    method: 'POST',
    body: JSON.stringify({ scenario_id }),
  });
}

/**
 * Submit a negotiation move and get the opponent's reply.
 * POST /api/chat/message
 *
 * critic_feedback is null — call evaluateMove() separately for coaching.
 */
export async function submitMove(
  session_id: string,
  message: string,
): Promise<MoveResponse> {
  return request<MoveResponse>('/api/chat/message', {
    method: 'POST',
    body: JSON.stringify({ session_id, message }),
  });
}

/**
 * Evaluate a user move with the Critic Agent.
 * POST /api/chat/evaluate
 *
 * Call this after submitMove() resolves so the coaching card loads
 * without blocking the opponent reply.
 */
export async function evaluateMove(
  session_id: string,
  message: string,
  turn_number: number,
): Promise<EvaluateResponse> {
  return request<EvaluateResponse>('/api/chat/evaluate', {
    method: 'POST',
    body: JSON.stringify({ session_id, message, turn_number }),
  });
}

/**
 * Reveal hidden opponent state after the session ends.
 * GET /session/{id}/reveal  (legacy endpoint — still works)
 */
export async function revealSession(
  session_id: string,
): Promise<RevealResponse> {
  return request<RevealResponse>(`/session/${session_id}/reveal`);
}

// ── Re-export error class for typed catch blocks ───────────────────────────────
export { ApiRequestError };
