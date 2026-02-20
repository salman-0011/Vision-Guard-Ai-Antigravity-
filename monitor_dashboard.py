#!/usr/bin/env python3
"""
Real-time dashboard for Vision Guard AI worker system.
Shows queue status, detection rate, and worker health.
"""

import redis
import time
import os
from datetime import datetime
from collections import deque

# Connect to Redis
try:
    r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)
    r.ping()
except:
    print("Cannot connect to Redis on localhost:6380")
    print("Make sure docker-compose services are running")
    exit(1)

# Track metrics
metrics = {
    'critical_samples': deque(maxlen=10),
    'high_samples': deque(maxlen=10),
    'medium_samples': deque(maxlen=10),
    'detections_samples': deque(maxlen=10),
    'iteration': 0
}

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def get_fps(queue_name):
    """Calculate frames per second based on queue length change."""
    samples = metrics[f'{queue_name}_samples']
    if len(samples) < 2:
        return 0
    return (samples[0] - samples[-1]) / (len(samples) - 1)

try:
    while True:
        clear_screen()
        
        # Get current metrics
        critical_len = r.llen('vg:critical')
        high_len = r.llen('vg:high')
        medium_len = r.llen('vg:medium')
        results_len = r.xlen('vg:ai:results')
        
        # Store samples for trend analysis
        metrics['critical_samples'].append(critical_len)
        metrics['high_samples'].append(high_len)
        metrics['medium_samples'].append(medium_len)
        metrics['detections_samples'].append(results_len)
        metrics['iteration'] += 1
        
        # Calculate rates
        critical_fps = get_fps('critical')
        high_fps = get_fps('high')
        medium_fps = get_fps('medium')
        
        # Display dashboard
        print("=" * 90)
        print("VISION GUARD AI - REAL-TIME MONITORING")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  Iteration: {metrics['iteration']}")
        print("=" * 90)
        
        print("\n📊 TASK QUEUE STATUS")
        print("-" * 90)
        print(f"  vg:critical (Weapon):  {critical_len:4d} frames  │  Drain rate: {critical_fps:6.2f} fps")
        print(f"  vg:high     (Fire):    {high_len:4d} frames  │  Drain rate: {high_fps:6.2f} fps")
        print(f"  vg:medium   (Fall):    {medium_len:4d} frames  │  Drain rate: {medium_fps:6.2f} fps")
        
        print("\n🎯 DETECTION RESULTS")
        print("-" * 90)
        print(f"  vg:ai:results stream:  {results_len:4d} detections")
        
        if results_len > 0:
            # Get last few detections
            print(f"\n  Latest detections:")
            latest = r.xrevrange('vg:ai:results', count=3)
            for entry_id, data in latest:
                frame_id = data.get('frame_id', 'unknown')
                confidence = float(data.get('confidence', 0))
                model_type = data.get('model_type', 'unknown')
                print(f"    - [ID: {entry_id}] {model_type:8s} confidence={confidence:.3f} ({frame_id})")
        
        print("\n⚠️  STATUS INDICATORS")
        print("-" * 90)
        
        total_queued = critical_len + high_len + medium_len
        avg_drain = (critical_fps + high_fps + medium_fps) / 3
        
        if total_queued == 0:
            print("  ✓ All queues empty (camera not capturing or processing complete)")
        elif avg_drain > 1:
            print(f"  ✓ Queues draining at {avg_drain:.2f} fps avg (healthy)")
        elif avg_drain > 0:
            print(f"  ⚠ Queues draining slowly at {avg_drain:.2f} fps (check worker logs)")
        else:
            print(f"  ✗ Queues not draining! Workers may be frozen")
        
        if results_len == 0 and total_queued > 0:
            print("  ⚠ No detections yet (may indicate frame reading issues or low confidence)")
        elif results_len > 0 and total_queued > 0:
            print(f"  ✓ Detections being produced ({results_len} in stream)")
        
        print("\n🔍 EXPECTED LOG PATTERNS")
        print("-" * 90)
        print("  When camera is streaming:")
        print("    1. Queue lengths should decrease")
        print("    2. Worker logs should show: PROCESSING_TASK")
        print("    3. If detection: DETECTION frame_id confidence=X.XXX")
        print("    4. If < threshold: BELOW_THRESHOLD frame_id")
        print("    5. If missing frame: FRAME_NOT_FOUND frame_id")
        
        print("\n💡 COMMAND REFERENCE")
        print("-" * 90)
        print("  # View worker logs with detections:")
        print("    docker logs vg-worker-fire 2>&1 | grep DETECTION")
        print("")
        print("  # View frame errors:")
        print("    docker logs vg-worker-weapon 2>&1 | grep FRAME_NOT_FOUND")
        print("")
        print("  # View all results in stream:")
        print("    docker exec vg-redis redis-cli XRANGE vg:ai:results 0 -1")
        print("")
        print("  # Press Ctrl+C to exit this monitor")
        print("=" * 90)
        
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\n\nMonitoring stopped.")
except Exception as e:
    print(f"\nError: {e}")
