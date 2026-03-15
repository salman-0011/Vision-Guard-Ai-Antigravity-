#!/bin/bash
# VisionGuard AI - Unified Startup Script
# Runs all services in background with proper logging

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/.vg_pids"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Create log directory
mkdir -p "$LOG_DIR"

# Export environment
export VG_DB_PATH="${VG_DB_PATH:-/tmp/visionguard/events.db}"
export ECS_DATABASE_PATH="$VG_DB_PATH"
export CAMERA_CONFIG_PATH="$PROJECT_DIR/cameras.json"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export WORKER_MODEL_TYPE="${WORKER_MODEL_TYPE:-weapon}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   VisionGuard AI - Starting All Services${NC}"
echo -e "${GREEN}========================================${NC}"

# Check Redis
echo -e "\n${YELLOW}[1/6] Checking Redis...${NC}"
if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
    echo "Starting Redis..."
    redis-server --daemonize yes
    sleep 1
fi
echo -e "${GREEN}✓ Redis is running${NC}"

# Initialize database
echo -e "\n${YELLOW}[2/6] Initializing Database...${NC}"
mkdir -p "$(dirname "$VG_DB_PATH")"
cd "$PROJECT_DIR"
source venv/bin/activate
python -c "from db import init_database; init_database()" 2>/dev/null || true
echo -e "${GREEN}✓ Database ready: $VG_DB_PATH${NC}"

# Clear old PIDs
> "$PID_FILE"

# Start Backend
echo -e "\n${YELLOW}[3/6] Starting Backend API...${NC}"
cd "$PROJECT_DIR/backend"
python main.py > "$LOG_DIR/backend.log" 2>&1 &
echo $! >> "$PID_FILE"
echo -e "${GREEN}✓ Backend started (PID: $!) → http://localhost:8000${NC}"

sleep 2

# Start ECS
echo -e "\n${YELLOW}[4/6] Starting Event Classification Service...${NC}"
cd "$PROJECT_DIR"
python event_classification/main.py > "$LOG_DIR/ecs.log" 2>&1 &
echo $! >> "$PID_FILE"
echo -e "${GREEN}✓ ECS started (PID: $!)${NC}"

sleep 1

# Start AI Worker
echo -e "\n${YELLOW}[5/6] Starting AI Worker ($WORKER_MODEL_TYPE)...${NC}"
cd "$PROJECT_DIR"
python ai_worker/main.py > "$LOG_DIR/ai_worker.log" 2>&1 &
echo $! >> "$PID_FILE"
echo -e "${GREEN}✓ AI Worker started (PID: $!)${NC}"

sleep 1

# Start Camera Capture
echo -e "\n${YELLOW}[6/6] Starting Camera Capture...${NC}"
cd "$PROJECT_DIR"
python camera_capture/main.py > "$LOG_DIR/camera.log" 2>&1 &
echo $! >> "$PID_FILE"
echo -e "${GREEN}✓ Camera Capture started (PID: $!)${NC}"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}   All Services Started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Access Points:"
echo "  • API:      http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo ""
echo "Logs: $LOG_DIR/"
echo "  • backend.log"
echo "  • ecs.log"
echo "  • ai_worker.log"
echo "  • camera.log"
echo ""
echo "To stop all services: bash scripts/stop.sh"
echo "To view logs: tail -f $LOG_DIR/*.log"
