#!/bin/bash
# VisionGuard AI - Stop All Services

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/.vg_pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}Stopping VisionGuard AI Services...${NC}"

if [ -f "$PID_FILE" ]; then
    while read pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "Stopping PID $pid..."
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Also kill by name (backup)
pkill -f "camera_capture/main.py" 2>/dev/null || true
pkill -f "ai_worker/main.py" 2>/dev/null || true
pkill -f "event_classification/main.py" 2>/dev/null || true
pkill -f "backend/main.py" 2>/dev/null || true

echo -e "${GREEN}✓ All services stopped${NC}"
