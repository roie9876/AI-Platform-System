#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────
# AI Platform — Docker Compose Startup
# Runs everything in containers (DB, Redis, backend, frontend)
# ─────────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create .env if missing
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp .env.example .env
fi

echo -e "${GREEN}Building and starting all services...${NC}"
docker compose up --build -d

echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
until docker compose exec -T db pg_isready -U aiplatform >/dev/null 2>&1; do
    sleep 1
done

# Run migrations inside the backend container
echo -e "${GREEN}Running database migrations...${NC}"
docker compose exec -T backend alembic upgrade head 2>/dev/null || \
    echo -e "${YELLOW}Migration warning (may be fine on first run)${NC}"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} AI Platform running (Docker)!${NC}"
echo -e "${GREEN}   Frontend:  http://localhost:3000${NC}"
echo -e "${GREEN}   Backend:   http://localhost:8000${NC}"
echo -e "${GREEN}   API Docs:  http://localhost:8000/docs${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Logs:  docker compose logs -f"
echo "Stop:  docker compose down"
