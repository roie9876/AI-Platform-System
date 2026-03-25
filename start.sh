#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────
# AI Platform — Local Dev Startup
# Starts DB + Redis in Docker, backend + frontend natively
# ─────────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── 0. Kill any previous instances ──
kill_stale() {
    local port=$1
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Killing existing process on port $port (PID: $pids)...${NC}"
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

kill_stale 8000
kill_stale 3000
kill_stale 8081
kill_stale 8082

BACKEND_PID=""
FRONTEND_PID=""
MCP_WEB_PID=""
MCP_ATLASSIAN_PID=""

cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    [ -n "$MCP_ATLASSIAN_PID" ] && kill "$MCP_ATLASSIAN_PID" 2>/dev/null || true
    [ -n "$MCP_WEB_PID" ] && kill "$MCP_WEB_PID" 2>/dev/null || true
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    [ -n "$MCP_ATLASSIAN_PID" ] && wait "$MCP_ATLASSIAN_PID" 2>/dev/null || true
    [ -n "$MCP_WEB_PID" ] && wait "$MCP_WEB_PID" 2>/dev/null || true
    [ -n "$BACKEND_PID" ] && wait "$BACKEND_PID" 2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && wait "$FRONTEND_PID" 2>/dev/null || true
    echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

# ── 1. Create .env if missing ──
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from .env.example (using localhost URLs)...${NC}"
    sed \
        -e 's|@db:|@localhost:|g' \
        -e 's|redis://redis:|redis://localhost:|g' \
        .env.example > .env
fi

# ── 2. Start infrastructure (DB + Redis) ──
if ! docker ps >/dev/null 2>&1; then
    echo -e "${YELLOW}Cannot connect to Docker daemon.${NC}"
    echo -e "${YELLOW}  • If Docker Desktop is not running, start it and wait for it to be ready.${NC}"
    echo -e "${YELLOW}  • If Docker Desktop shows running but this still fails, restart Docker Desktop.${NC}"
    exit 1
fi

echo -e "${GREEN}Starting PostgreSQL + Redis...${NC}"
docker compose up -d db redis

echo -e "${YELLOW}Waiting for DB to be healthy...${NC}"
until docker compose exec -T db pg_isready -U aiplatform >/dev/null 2>&1; do
    sleep 1
done
echo -e "${GREEN}DB ready.${NC}"

# ── 3. Backend ──
echo -e "${GREEN}Starting backend...${NC}"
cd "$ROOT_DIR/backend"

# Find a compatible Python (3.13 > 3.12 > 3.11 — 3.14+ not yet supported by pydantic)
PYTHON_BIN=""
for v in python3.13 python3.12 python3.11; do
    if command -v "$v" >/dev/null 2>&1; then
        PYTHON_BIN="$v"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo -e "${YELLOW}No compatible Python (3.11–3.13) found. Install one via: brew install python@3.13${NC}"
    exit 1
fi

if [ ! -d .venv ]; then
    echo -e "${YELLOW}Creating Python virtual environment ($PYTHON_BIN)...${NC}"
    "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate
echo -e "${YELLOW}Installing Python dependencies (first run may take a minute)...${NC}"
pip install -r requirements.txt

# Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
alembic upgrade head 2>/dev/null || echo -e "${YELLOW}Migration warning (may be fine on first run)${NC}"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ── 3b. MCP Servers (Demo) ──
echo -e "${GREEN}Starting MCP servers for demo...${NC}"

if [ -f "$ROOT_DIR/backend/mcp_server_web_tools.py" ]; then
    python "$ROOT_DIR/backend/mcp_server_web_tools.py" &
    MCP_WEB_PID=$!
    echo -e "${GREEN}  Web Tools MCP server on port 8081${NC}"
fi

if [ -f "$ROOT_DIR/backend/mcp_server_atlassian_mock.py" ]; then
    python "$ROOT_DIR/backend/mcp_server_atlassian_mock.py" &
    MCP_ATLASSIAN_PID=$!
    echo -e "${GREEN}  Atlassian (Jira + Confluence) MCP server on port 8082${NC}"
fi

# ── 4. Frontend ──
echo -e "${GREEN}Starting frontend...${NC}"
cd "$ROOT_DIR/frontend"
npm install --silent 2>/dev/null
npm run dev &
FRONTEND_PID=$!

# ── 5. Ready ──
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} AI Platform running!${NC}"
echo -e "${GREEN}   Frontend:  http://localhost:3000${NC}"
echo -e "${GREEN}   Backend:   http://localhost:8000${NC}"
echo -e "${GREEN}   API Docs:  http://localhost:8000/docs${NC}"
echo -e "${GREEN}   MCP Web:   http://localhost:8081/mcp${NC}"
echo -e "${GREEN}   MCP Jira:  http://localhost:8082/mcp${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Press Ctrl+C to stop all services."

wait
