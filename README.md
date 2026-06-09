<<<<<<< HEAD
# ParleyLab: AI Negotiation Coach 🎙️🤝

**ParleyLab** is an advanced AI-powered negotiation simulator built for the IEEE AI/ML Hackathon track by team **Hell's Kitchen**. It provides users with a realistic, high-pressure negotiation environment against an AI opponent, offering real-time strategic coaching and feedback.

## 🌟 The 6-Stage Negotiation Pipeline

ParleyLab employs a unique, decoupled AI architecture to simulate realistic opponents and provide actionable coaching:

1. **Move Parser (LLM)**: Extracts structured data from the user's free-form text input (e.g., identifying concessions, anchors, and tone).
2. **State Update**: Converts the parsed move into a 7-dimensional normalized observation vector representing the current negotiation gap.
3. **RL Policy (PPO)**: A trained Reinforcement Learning agent decides the opponent's strategic action (Hold Firm, Concede Small, Concede Large, Bluff, or Walk Away) in sub-milliseconds.
4. **Opponent LLM**: Translates the RL agent's numeric strategy into natural, in-character dialogue.
5. **Critic LLM (Parallel)**: Analyzes the user's move against negotiation theory to provide real-time strengths, weaknesses, and actionable suggestions.
6. **State Persist**: The session is updated, and the opponent's response is delivered to the UI, while the coaching feedback streams in asynchronously.

## 🚀 Getting Started Locally

To run the full stack locally, you need two terminal windows: one for the FastAPI backend and one for the Next.js frontend.

### Prerequisites

1. Clone the repository.
2. Copy `.env.example` to `.env` in the root directory:
   ```bash
   cp .env.example .env
   ```
3. Add your Gemini API key to the `.env` file:
   ```env
   GEMINI_API_KEY=AIzaSy_your_actual_key_here
   ```

### 1. Start the FastAPI Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```
The backend will load the RL model and connect to Gemini. Wait until you see `Orchestrator ready`.

### 2. Start the Next.js Frontend

In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser. Select a scenario and begin your negotiation!

## 🤖 Models Architecture

The `models/` directory contains the trained Proximal Policy Optimization (PPO) weights (`best_model.zip`) used to drive the opponent's strategic decision-making. These models are lightweight (~140KB each) and are committed directly to the repository without needing Git LFS.
=======
# ParleyLab — AI Negotiation Simulator

An AI negotiation coach that pits the user against an adaptive opponent
driven by a trained reinforcement learning policy.

---

## parley_ai — Python package (AI/ML layer)

`parley_ai` is the self-contained AI/ML package that the FastAPI backend
imports. It exposes five functions covering the full per-turn pipeline.

### Installation (dev)

```bash
pip install -r requirements.txt
```

### Quick test

```bash
python scripts/test_stubs.py
```

---

### Public API

#### `parse_move(user_message, history) → dict`

Converts the user's raw negotiation text into a structured move.

| Return key | Type | Description |
|---|---|---|
| `primary_move` | str | Dominant tactic: `anchor`, `counteroffer`, `concession`, `bluff`, `inquiry`, `walk` |
| `offered_value` | float \| None | Numeric offer extracted from the message |
| `signals` | list[str] | Tactical signals: `competing_bid_disclosure`, `bundled_demand`, `deadline_pressure`, … |
| `tone` | str | `collaborative`, `assertive`, or `neutral` |

**Used by:** FastAPI orchestrator — first step of every turn.

---

#### `get_strategic_action(state_vector) → dict`

Runs the trained PPO policy on the current game state to decide the
opponent's next strategic move.

`state_vector` is a 7-element list of floats in `[0, 1]`:

```
[own_offer_norm, opponent_offer_norm, turn_norm,
 own_concession_rate, opponent_concession_rate,
 gap_norm, turns_since_last_concession_norm]
```

| Return key | Type | Description |
|---|---|---|
| `action_id` | int | 0=Hold Firm, 1=Concede Small, 2=Concede Large, 3=Bluff, 4=Walk Away |
| `action_name` | str | Human-readable label |
| `description` | str | What the action means in game terms |

**Used by:** FastAPI orchestrator — after state update, before opponent LLM call.

---

#### `generate_opponent_response(action, hidden_context, history, parsed_user_move) → str`

Translates the RL policy's strategic decision into natural language,
staying consistent with the opponent's persona.

Returns a single string ready for the frontend chat UI.

**Used by:** FastAPI orchestrator — runs in parallel with `get_critic_feedback`.

---

#### `get_critic_feedback(parsed_user_move, history) → dict`

Evaluates the user's move against negotiation theory. The critic never
sees the opponent's hidden state — its judgment is unconditional.

| Return key | Type | Description |
|---|---|---|
| `strengths` | list[str] | What the user did well |
| `weaknesses` | list[str] | What could be improved |
| `suggestion` | str | One concrete actionable improvement |
| `concept_tag` | str | Negotiation concept: `anchoring`, `reciprocity`, `concession_pacing`, `batna_awareness` |

**Used by:** FastAPI orchestrator — runs in parallel with `generate_opponent_response`.

---

#### `score_session(history) → dict`

Analyses the full transcript after the negotiation ends and returns a
performance score.

| Return key | Type | Description |
|---|---|---|
| `score` | int | 0–100 |
| `rating` | str | `Excellent`, `Good`, `Fair`, or `Needs Work` |
| `best_move` | dict | `{turn: int, summary: str}` |
| `worst_move` | dict | `{turn: int, summary: str}` |

**Used by:** FastAPI `GET /session/{id}/reveal` endpoint.

---

## LLM stack

| Priority | Provider | Notes |
|---|---|---|
| 1 | Ollama (local) | Primary — zero cost, private |
| 2 | Groq | Cloud fallback — fast free tier |
| 3 | Gemini | Cloud fallback — generous free tier |

Configure via environment variables (copy `.env.example` → `.env`):

```
PARLEYLAB_LLM_PROVIDER=ollama
PARLEYLAB_OPPONENT_MODEL=llama3.1:8b
PARLEYLAB_CRITIC_MODEL=qwen2.5:7b
PARLEYLAB_PARSER_MODEL=qwen2.5:7b
GROQ_API_KEY=...
GEMINI_API_KEY=...
```
>>>>>>> 301cf31a (Add Backend Files and test scripts)
