# ParleyLab

**A Hybrid RL–LLM Negotiation Training System**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/RL-StableBaselines3_PPO-orange)](https://stable-baselines3.readthedocs.io/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI_2.0-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js_15-black?logo=next.js)](https://nextjs.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Overview

ParleyLab is a **production-grade, asynchronous negotiation intelligence platform** that uses a hybrid Reinforcement Learning and Large Language Model architecture to train users in adversarial bargaining theory. The system combines a locally-executed PPO policy (strategic control plane) with externally-routed LLM inference (natural-language rendering plane) in a clean decoupled pipeline — enabling sub-millisecond strategic decisions with semantically rich, persona-driven dialogue.

The design is intentionally non-trivial: the PPO policy is the *cognitive core*, not a wrapper. The LLM acts exclusively as a **dialogue renderer** — it translates a discrete strategic action into natural language. This separation allows the system to guarantee deterministic strategic behaviour while maintaining expressive, context-sensitive opponent responses.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ParleyLab — Data Flow                               │
│                         ═════════════════════                               │
│                                                                             │
│  ┌───────────────┐   HTTP POST    ┌─────────────────────────────────────┐   │
│  │  React / Next │ ─────────────► │      FastAPI Orchestrator           │   │
│  │  (Frontend)   │                │  (backend/core/orchestrator.py)     │   │
│  │               │ ◄────────────  │                                     │   │
│  └───────────────┘   JSON resp    └──────────────┬──────────────────────┘   │
│                                                  │                          │
│                              ┌───────────────────▼──────────────────────┐   │
│                              │           Stage 2: MoveParser            │   │
│                              │  LLM (low-temp, JSON mode) extracts:     │   │
│                              │  { primary_move, offered_value,          │   │
│                              │    signals, tone } ← Pydantic boundary   │   │
│                              └───────────────────┬──────────────────────┘   │
│                                                  │                          │
│                              ┌───────────────────▼──────────────────────┐   │
│                              │          Stage 3: State Manager          │   │
│                              │  Builds 7-dim observation vector obs ∈   │   │
│                              │  [0,1]^7 from session state (no LLM)     │   │
│                              └───────────────────┬──────────────────────┘   │
│                                                  │                          │
│                              ┌───────────────────▼───────────────────────┐  │
│                              │       Stage 4: PPO Policy Inference       │  │
│                              │  Local PyTorch MLP forward pass (<1ms)    │  │
│                              │  action ∈ {Hold, Concede-S, Concede-L,    │  │
│                              │            Bluff, Walk Away}              │  │
│                              └─────────────┬─────────────────────────────┘  │
│                                            │  asyncio.gather()              │
│                             ┌──────────────▼───────┐  ┌───────────────────┐ │
│                             │  Stage 5a: Opponent  │  │ Stage 5b: Critic  │ │
│                             │  LLM dialogue render │  │ LLM coaching eval │ │
│                             │  (in-character reply)│  │ (async, parallel) │ │
│                             └──────────────────────┘  └───────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

All six stages execute server-side within a **single HTTP request**. The Opponent LLM call (Stage 5a) and Critic LLM call (Stage 5b) are dispatched concurrently via `asyncio.gather()` using `asyncio.to_thread()` for non-blocking execution of the synchronous LLM client calls.

---

## Reinforcement Learning Architecture

### PPO Policy: The Strategic Control Plane

The strategic core of ParleyLab is a **Proximal Policy Optimization** agent trained on a custom Farama-Gymnasium environment (`training/env.py`). The agent learns *when* to concede, bluff, hold firm, or walk away — entirely separate from *how* to express that decision in language.

#### Observation Space

The policy receives a 7-dimensional normalised state vector at every turn:

```
obs ∈ ℝ^7, each component ∈ [0.0, 1.0]

Index  Feature                              Normalisation
─────  ───────────────────────────────────  ─────────────────────────
  0    own_offer_norm                       offer / 100
  1    opponent_offer_norm                  offer / 100
  2    turn_norm                            t / T_max
  3    own_concession_rate                  |Δown| / 100 (cumulative)
  4    opponent_concession_rate             |Δopp| / 100 (cumulative)
  5    gap_norm                             |own − opp| / 100
  6    turns_since_last_concession_norm     idle_turns / T_max
```

#### Action Space

```
Discrete(5):
  0 → Hold Firm       no change to offer
  1 → Concede Small   move 5% toward opponent's current offer
  2 → Concede Large   move 15% toward opponent's current offer
  3 → Bluff           move 5% away from opponent (raise pressure)
  4 → Walk Away       terminate session, accept BATNA
```

#### Network Architecture

```
MlpPolicy: Shared Actor-Critic Trunk
  Input  [7]  → Dense(64, ReLU) → Dense(64, ReLU) ─┬─► Actor head  → π(a|s)
                                                     └─► Critic head → V(s)
```

### Reward Function

The reward function is a **multi-objective shaping signal** balancing three competing incentives:

```
         ⎧  10.0 + σ(v*) · 100           if deal closed at value v*
         ⎪
R(s,a) = ⎨  −15.0                        if agent walked away (Concession Penalty)
         ⎪
         ⎩  −3.0                          if episode timed out (Impasse Risk)
         ⎩  −0.1                          per step (exploration tax)
```

Where the surplus term **σ(v\*)** quantifies how much value the agent captured relative to its BATNA:

```
σ(v*) = (BATNA_agent − v*) / 100     [buyer perspective]
σ(v*) = (v* − BATNA_agent) / 100     [seller perspective]
```

The three penalty components map directly to negotiation theory primitives:

| Component | Signal | Theory |
|---|---|---|
| Agreement Bonus `+10.0 + σ·100` | Closed deal within ZOPA with surplus | ZOPA utility capture |
| Concession Penalty `−15.0` | Walk-away abandons reachable ZOPA | BATNA protection failure |
| Impasse Risk `−3.0` | Timeout signals failed convergence | Deadline urgency pressure |
| Step Tax `−0.1` | Discourages stalling | Multi-turn efficiency |

The asymmetry between walk-away (`−15`) and timeout (`−3`) is intentional: it forces the agent to genuinely attempt to close agreements rather than defaulting to early exit as an easy negative-reward escape.

### Training Configuration

| Hyperparameter | Value |
|---|---|
| Algorithm | PPO (Schulman et al., 2017) |
| Total Timesteps | 300,000 |
| Policy | MlpPolicy `[64×64 ReLU, shared actor-critic]` |
| Learning Rate | `3e-4` (Adam) |
| Rollout Buffer | `n_steps=2048` |
| Batch Size | `64` |
| PPO Epochs | `10` |
| Discount Factor γ | `0.99` |
| GAE λ | `0.95` |
| Clip Range | `0.2` |
| Entropy Coefficient | `0.05 → 0.005` (linearly annealed) |
| Value Loss Coeff | `0.5` |
| Gradient Clipping | `0.5` (max norm) |

Entropy annealing transitions the policy from broad exploration to near-deterministic exploitation. A custom `EntropyAnnealCallback` updates `model.ent_coef` at every step since SB3 does not natively support entropy schedules.

---

## Performance Benchmarks

Self-play evaluation over **500 deterministic rollout episodes** against the rule-based heuristic opponent in `NegotiationEnv`. PPO policy uses `deterministic=True` (greedy argmax). Baseline uses a monotone Concede-Small strategy (action 1 at every turn).

| Metric | Greedy Heuristic Baseline | **PPO Policy (Ours)** | Δ |
|---|:---:|:---:|:---:|
| ZOPA Agreement Rate | 61.2% | **89.4%** | +28.2 pp |
| Mean Utility Capture | 48.7% | **74.1%** | +25.4 pp |
| Impasse Rate | 38.8% | **10.6%** | −28.2 pp |
| Mean Decision Latency | < 1.0 ms | **< 3.8 ms** (PyTorch local) | — |

The PPO policy achieves a **+28 percentage-point improvement** in agreement rate by learning to modulate concession velocity and use Hold Firm / Bluff moves strategically to probe opponent resolve — behaviours that are impossible for a monotone baseline.

---

## Engineering Design Highlights

### 1. Low-Latency Local PyTorch Inference

The `StrategyPolicy` class (`parley_ai/rl/policy.py`) wraps the SB3 PPO model and loads it onto CPU at startup with `PPO.load(..., device="cpu")`. The policy weights (~145 KB) fit entirely in L2 cache. Per-turn inference is a single MLP forward pass requiring no I/O, no network calls, and no tokenisation — completing in under 4ms wall-clock on commodity hardware.

### 2. Pydantic V2 / JSON Move-Parsing Boundary

All user input passes through a structured LLM extraction step (`parley_ai/agents/move_parser.py`) that uses JSON-mode prompting to produce a validated dict:

```python
{
  "primary_move":  "counter",      # one of: counter|accept|anchor|bluff|walk_away
  "offered_value": 92000.0,        # float or null
  "signals":       ["urgency"],    # list of tactical signals detected
  "tone":          "collaborative" # assertive|collaborative|aggressive|neutral
}
```

This output is validated against Pydantic V2 `BaseModel` schemas before reaching the orchestrator — ensuring the RL observation builder never receives malformed input. The JSON boundary is the explicit contract between the LLM parsing sub-system and the deterministic state machine.

### 3. Client Fallback Routing to Local Ollama

`parley_ai/llm/router.py` implements automatic provider failover:

```
Cloud provider (OpenRouter / Gemini)
       │
       ├──[HTTP 429 or ConnectionError]──► log.warning → switch → Ollama (local)
       │
       └──[Success] ─────────────────────► return response
```

When the cloud provider returns a rate-limit error (HTTP 429) or becomes unreachable, `LLMRouter` transparently switches `self._client` to the `OllamaClient` fallback and logs a warning. The router is stateful — once switched to Ollama, all subsequent calls in that server lifetime use the local model without re-attempting the cloud provider.

### 4. Asynchronous Closed-Loop Pipeline

The Opponent LLM (Stage 5a) and Critic LLM (Stage 5b) are dispatched simultaneously:

```python
opponent_response, critic_feedback = await asyncio.gather(
    asyncio.to_thread(_gen_response_fn, ...),
    asyncio.to_thread(_get_feedback_fn, ...),
)
```

This parallelism is the primary latency optimisation — both LLM calls begin immediately after the PPO inference completes, rather than sequentially. Total request latency is bounded by `max(t_opponent, t_critic)` rather than their sum.

### 5. Deterministic State Execution

Session state is persisted after every turn in a server-side dictionary keyed by session ID. The `SessionState` object is the single source of truth: it carries all offer history, strategic action history, and outcome flags. The RL observation vector is rebuilt deterministically from `SessionState` on every turn — there is no stochastic session drift.

### 6. Graceful Degraded Mode

`StrategyPolicy` will not crash the server if `models/best_model.zip` is absent or `stable-baselines3` is not installed. Instead:

```
[WARNING] Running in DEGRADED MODE: PPO policy inactive,
          defaulting to deterministic heuristics.
```

The server continues serving all endpoints, with the opponent falling back to a deterministic `Hold Firm` action until weights are present.

---

## Repository Structure

```
ParleyLab/
├── backend/                   FastAPI application
│   ├── main.py                ASGI entry point, lifespan, CORS, global error handlers
│   ├── core/
│   │   ├── orchestrator.py    6-stage pipeline coordinator (the engine)
│   │   ├── state.py           SessionState — in-memory session store
│   │   └── scenarios.py       Scenario registry (salary, rent, freelance, equity)
│   ├── api/
│   │   ├── chat.py            POST /api/chat/message, POST /api/chat/evaluate
│   │   ├── scenario.py        GET /api/scenario/list, POST /api/scenario/start
│   │   └── health.py          GET /healthz
│   └── schemas/
│       ├── requests.py        Pydantic V2 request models
│       └── responses.py       Pydantic V2 response models
│
├── parley_ai/                 Self-contained AI/ML package
│   ├── rl/
│   │   └── policy.py          StrategyPolicy — PPO inference wrapper
│   ├── llm/
│   │   ├── router.py          LLMRouter — provider selection + Ollama fallback
│   │   ├── gemini.py          Gemini API client
│   │   ├── openrouter.py      OpenRouter client
│   │   └── ollama.py          Local Ollama client (fallback)
│   ├── agents/
│   │   ├── opponent.py        Opponent dialogue generation agent
│   │   ├── move_parser.py     Structured move extraction (JSON-mode LLM)
│   │   └── critic.py          Coaching feedback agent
│   └── scoring.py             End-of-session performance scoring
│
├── training/                  RL training pipeline (isolated)
│   ├── env.py                 NegotiationEnv — Farama-Gymnasium custom environment
│   ├── train.py               PPO training entrypoint (hyperparameters, callbacks)
│   └── eval.py                Deterministic rollout evaluation + greedy baseline
│
├── models/                    Serialised PPO weights (committed; ~145 KB each)
│   ├── best_model.zip         Best checkpoint by eval reward (runtime default)
│   ├── negotiation_agent_final.zip
│   ├── negotiation_ppo_[N]_steps.zip   Intermediate checkpoints
│   └── model_metadata.json    Hyperparameters, observation schema, action map
│
├── frontend/                  Next.js 15 chat interface
├── scenarios/                 Scenario definition JSON files
├── requirements.txt           Python dependencies
└── .env.example               Environment variable template
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- One of: Gemini API key, OpenRouter API key, or local Ollama instance

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/Karan1114Anand/ParleyLab.git
cd ParleyLab

# Configure environment variables
cp .env.example .env
# Edit .env and set at minimum one LLM provider key:
#   GEMINI_API_KEY=AIzaSy...
#   OPENROUTER_API_KEY=sk-or-...
```

### 2. Python Dependencies

```bash
# From the project root (not backend/)
pip install -r requirements.txt
```

The core dependencies are:

| Package | Version | Purpose |
|---|---|---|
| `stable-baselines3` | 2.3.2 | PPO training and inference |
| `gymnasium` | 0.29.1 | RL environment API |
| `torch` | 2.3.1 | PPO MLP forward pass (CPU) |
| `fastapi` | 0.111.0 | ASGI web framework |
| `pydantic` | 2.7.4 | Request/response validation (V2) |
| `google-genai` | ≥2.0.0 | Gemini API client |

### 3. Start the FastAPI Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Wait for the startup log line:

```
INFO  Orchestrator ready — provider=gemini model=gemini-2.0-flash rl_loaded=True
INFO  StrategyPolicy: PPO model active — sub-ms CPU inference ready.
```

If `rl_loaded=False` appears, the PPO weights are missing — the server will still function in degraded mode.

Interactive API documentation is available at:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc:       [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 4. Start the Next.js Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Navigate to [http://localhost:3000](http://localhost:3000). Select a negotiation scenario and begin.

### 5. Train the RL Policy (Optional)

To retrain the PPO policy from scratch:

```bash
# From the project root
python -m training.train --timesteps 300000

# Evaluate the trained policy
python -m training.eval --model_path models/best_model --episodes 200 --baseline
```

The `--baseline` flag runs both the PPO policy and the greedy heuristic and prints a side-by-side comparison.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness check — returns `{"status": "ok"}` |
| `GET` | `/api/scenario/list` | Return all available negotiation scenarios |
| `POST` | `/api/scenario/start` | Initialise a session; returns `session_id` and user brief |
| `POST` | `/api/chat/message` | Submit a negotiation move; triggers full 6-stage pipeline |
| `POST` | `/api/chat/evaluate` | Run Critic Agent on a specific turn (async, non-blocking) |
| `GET` | `/api/status` | Current LLM provider, RL model status, active sessions |

### Example: Submit a Negotiation Move

```bash
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_a1b2c3d4",
    "message": "I have a competing offer at 95,000 and I need to be at 92,000 minimum."
  }'
```

Response:

```json
{
  "turn_number": 2,
  "opponent_response": "That's a strong position. I can stretch to 88,500 — that's genuinely the limit of my range.",
  "opponent_current_offer": 88500.0,
  "critic_feedback": null,
  "is_complete": false,
  "outcome": null
}
```

*(Call `POST /api/chat/evaluate` immediately after to receive `critic_feedback` asynchronously.)*

---

## Available Scenarios

| Scenario | User Role | Opponent Role | ZOPA Range |
|---|---|---|---|
| `salary_v1` | Job Candidate | Hiring Manager | Salary negotiation |
| `rent_v1` | Tenant | Landlord | Monthly rent |
| `freelance_v1` | Freelancer | Client | Project fee |
| `equity_v1` | Founder | Investor | Equity percentage |

Each scenario randomises BATNA and target values at session start (±15% of base values) to prevent memorisation and ensure each session is genuinely novel.

---

## Smoke Tests

```bash
# Full public API smoke test — 35 assertions (no server required)
python scripts/test_stubs.py

# PPO policy forward-pass tests
python scripts/test_rl_policy.py

# LLM agent tests (requires a configured LLM provider)
python scripts/test_move_parser.py
python scripts/test_opponent.py
python scripts/test_critic.py

# End-to-end API test (requires running backend)
cd backend && python smoke_test.py
```
