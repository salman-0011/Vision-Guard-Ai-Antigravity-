#!/bin/bash
# VisionGuard AI - Stop All Services
# Stops services started by start.sh using saved PIDs

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_DIR/.vg_pids"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}   VisionGuard AI - Stopping Services${NC}"
echo -e "${RED}========================================${NC}"
echo ""

stopped=0

# Stop PIDs from file
if [ -f "$PID_FILE" ] && [ -s "$PID_FILE" ]; then
    echo -e "${YELLOW}Sending SIGTERM to saved PIDs...${NC}"
    while read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo -e "  Sent SIGTERM to PID $pid"
            stopped=$((stopped + 1))
        fi
    done < "$PID_FILE"

    # Wait for graceful shutdown
    echo -e "\n${YELLOW}Waiting 3 seconds for graceful shutdown...${NC}"
    sleep 3

    # Force kill any survivors
    while read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo -e "  ${RED}PID $pid still running, sending SIGKILL${NC}"
            kill -9 "$pid" 2>/dev/null
        fi
    done < "$PID_FILE"

    # Clear PID file
    > "$PID_FILE"
else
    echo -e "${YELLOW}No PID file found or empty${NC}"
fi

# Kill stray processes by name (fallback)
echo -e "\n${YELLOW}Cleaning up stray processes...${NC}"
for pattern in \
    "event_classification/main.py" \
    "ai_worker/main.py" \
    "camera_capture/main.py" \
    "backend/main.py"; do
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        pkill -f "$pattern" 2>/dev/null
        echo -e "  Killed stray: $pattern"
        stopped=$((stopped + 1))
    fi
done

echo ""
echo -e "${GREEN}========================================${NC}"
if [ "$stopped" -gt 0 ]; then
    echo -e "${GREEN}   Stopped $stopped process(es)${NC}"
else
    echo -e "${GREEN}   No running services found${NC}"
fi
echo -e "${GREEN}========================================${NC}"
