#!/bin/bash
# Monitor worker activity in real-time

echo "======================================================================="
echo "VISION GUARD AI - WORKER MONITORING"
echo "======================================================================="
echo ""
echo "This script monitors worker logs for:"
echo "  - PROCESSING: Task consumption"
echo "  - DETECTION: Successful detections with confidence score"
echo "  - FRAME_NOT_FOUND: Shared memory errors"
echo "  - BELOW_THRESHOLD: Detections filtered by confidence"
echo ""
echo "======================================================================="
echo ""

# Create a named pipe for merging logs
mkfifo /tmp/worker1 /tmp/worker2 /tmp/worker3 2>/dev/null

# Start tailing all 3 workers and filter for keywords
(docker logs vg-worker-weapon -f 2>&1 | grep -E "PROCESSING|DETECTION|FRAME_NOT_FOUND|BELOW" | while read line; do echo "[WEAPON] $line"; done) > /tmp/worker1 &
PID1=$!

(docker logs vg-worker-fire -f 2>&1 | grep -E "PROCESSING|DETECTION|FRAME_NOT_FOUND|BELOW" | while read line; do echo "[FIRE] $line"; done) > /tmp/worker2 &
PID2=$!

(docker logs vg-worker-fall -f 2>&1 | grep -E "PROCESSING|DETECTION|FRAME_NOT_FOUND|BELOW" | while read line; do echo "[FALL] $line"; done) > /tmp/worker3 &
PID3=$!

# Merge and display
cat /tmp/worker1 /tmp/worker2 /tmp/worker3

# Cleanup on exit
cleanup() {
    kill $PID1 $PID2 $PID3 2>/dev/null
    rm -f /tmp/worker1 /tmp/worker2 /tmp/worker3
    exit
}

trap cleanup EXIT INT TERM

# Keep script running
wait
