#!/usr/bin/env bash
# dev.sh — Start ParleyLab dev servers on Linux
#
# Usage:  ./dev.sh
#
# This script:
#   1. Kills anything already on ports 8000 / 3000
#   2. Starts the FastAPI backend in the CURRENT terminal
#   3. Opens a SEPARATE terminal for live LLM usage logs
#   4. Opens a SEPARATE terminal for the Next.js frontend
#
# Requirements: gnome-terminal (default on Ubuntu/GNOME), or xterm as fallback.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$PROJECT_ROOT/.venv"

# ── Colours ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ── Kill processes on a port ───────────────────────────────────────────────────
kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo -e "${YELLOW}Killing processes on port $port...${NC}"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi
}

# ── Detect terminal emulator ──────────────────────────────────────────────────
detect_terminal() {
  if command -v gnome-terminal &>/dev/null; then
    echo "gnome-terminal"
  elif command -v xterm &>/dev/null; then
    echo "xterm"
  elif command -v konsole &>/dev/null; then
    echo "konsole"
  elif command -v xfce4-terminal &>/dev/null; then
    echo "xfce4-terminal"
  else
    echo "none"
  fi
}

TERM_APP=$(detect_terminal)

open_in_terminal() {
  local title="$1"
  local cmd="$2"
  case "$TERM_APP" in
    gnome-terminal)
      gnome-terminal --title="$title" -- bash -c "$cmd; exec bash" &
      ;;
    konsole)
      konsole --new-tab -e bash -c "$cmd; exec bash" &
      ;;
    xfce4-terminal)
      xfce4-terminal --title="$title" -e "bash -c '$cmd; exec bash'" &
      ;;
    xterm)
      xterm -title "$title" -e "bash -c '$cmd; exec bash'" &
      ;;
    *)
      echo -e "${RED}No supported terminal emulator found. Running in background.${NC}"
      bash -c "$cmd" &
      ;;
  esac
}

# ── Main ──────────────────────────────────────────────────────────────────────

echo -e "${CYAN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           ParleyLab Dev Launcher               ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}Stopping any existing servers...${NC}"
kill_port 8000
kill_port 3000
kill_port 3001
kill_port 3002
sleep 1

# ── Activate venv if present ─────────────────────────────────────────────────
ACTIVATE=""
if [[ -f "$VENV_DIR/bin/activate" ]]; then
  ACTIVATE="source $VENV_DIR/bin/activate &&"
fi

# ── Start LLM monitor terminal ──────────────────────────────────────────────
echo -e "${GREEN}Opening LLM monitor terminal...${NC}"
LLM_MONITOR_CMD="$ACTIVATE echo -e '${CYAN}═══ ParleyLab LLM Monitor ═══${NC}' && echo 'Waiting for backend to start...' && sleep 3 && echo 'Polling /api/status/llm every 3s...' && while true; do echo '──────────────────────────────────' && date '+%H:%M:%S' && curl -s http://localhost:8000/api/status/llm 2>/dev/null | python3 -m json.tool 2>/dev/null || echo '⏳ Backend not ready yet...'; sleep 3; done"
open_in_terminal "ParleyLab — LLM Monitor" "$LLM_MONITOR_CMD"

# ── Start Next.js frontend in separate terminal ─────────────────────────────
echo -e "${GREEN}Starting Next.js frontend (port 3000) in new terminal...${NC}"
FRONTEND_CMD="cd $FRONTEND_DIR && npm run dev"
open_in_terminal "ParleyLab — Frontend (3000)" "$FRONTEND_CMD"

sleep 1

# ── Start FastAPI backend in THIS terminal ───────────────────────────────────
echo -e "${GREEN}Starting FastAPI backend (port 8000) in this terminal...${NC}"
echo ""
echo -e "${CYAN}Backend:  http://localhost:8000/docs${NC}"
echo -e "${CYAN}Frontend: http://localhost:3000${NC}"
echo -e "${CYAN}Health:   http://localhost:8000/healthz${NC}"
echo ""

cd "$BACKEND_DIR"
if [[ -f "$VENV_DIR/bin/activate" ]]; then
  source "$VENV_DIR/bin/activate"
fi

exec python -m uvicorn main:app --port 8000 --reload
