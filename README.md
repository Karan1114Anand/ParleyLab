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

## 🤖 Models

The `models/` directory contains the trained Proximal Policy Optimization (PPO) weights (`best_model.zip`) used to drive the opponent's strategic decision-making. These models are lightweight (~140 KB each) and are committed directly to the repository without needing Git LFS.

---

## parley_ai — AI/ML Package (developer reference)

`parley_ai` is the self-contained Python package that contains all AI/ML logic. The FastAPI backend imports from `backend/parley_ai/` (Taanush's Gemini-based, class-oriented version). A root-level `parley_ai/` package also exists with an Ollama-primary, function-based API used for standalone testing.

### Standalone tests (no server needed)

```bash
python scripts/test_stubs.py        # public API smoke test — 35 checks
python scripts/test_rl_policy.py    # PPO policy predictions
python scripts/test_move_parser.py  # LLM move parser (requires Ollama)
python scripts/test_opponent.py     # LLM opponent agent (requires Ollama)
python scripts/test_critic.py       # LLM critic agent (requires Ollama)
```

### API smoke test (requires running backend)

```bash
cd backend
python smoke_test.py
```
