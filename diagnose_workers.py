#!/usr/bin/env python3
"""
Diagnostic script to understand worker behavior and queue processing.
"""

import redis
import json
import time
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Connect to Redis
redis_client = redis.Redis(
    host="localhost",
    port=6380,
    db=0,
    decode_responses=True
)

try:
    redis_client.ping()
    print("✓ Connected to Redis")
except Exception as e:
    print(f"✗ Redis connection failed: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("QUEUE STATUS")
print("="*70)

queues = {
    "vg:critical": "Weapon Detector",
    "vg:high": "Fire Detector",
    "vg:medium": "Fall Detector"
}

for queue_name, desc in queues.items():
    length = redis_client.llen(queue_name)
    print(f"{queue_name:20} ({desc:20}): {length:5} frames waiting")

print("\n" + "="*70)
print("RESULTS STREAM STATUS")
print("="*70)

stream_len = redis_client.xlen("vg:ai:results")
print(f"vg:ai:results stream length: {stream_len}")

if stream_len > 0:
    entries = redis_client.xrange("vg:ai:results", count=5)
    print(f"\nLast {min(5, len(entries))} detections:")
    for entry_id, data in entries[-5:]:
        print(f"  [{entry_id}] {data}")

print("\n" + "="*70)
print("TASK CONSUMPTION TEST")
print("="*70)

# Try to consume one task from each queue
for queue_name, desc in queues.items():
    task = redis_client.rpop(queue_name)
    if task:
        try:
            task_data = json.loads(task)
            print(f"\n✓ {desc} ({queue_name}):")
            print(f"  Camera ID: {task_data.get('camera_id')}")
            print(f"  Frame ID: {task_data.get('frame_id')}")
            print(f"  Shared Memory Key: {task_data.get('shared_memory_key')}")
            print(f"  Timestamp: {task_data.get('timestamp')}")
            
            # Put it back
            redis_client.lpush(queue_name, task)
            print(f"  [Task returned to queue]")
        except Exception as e:
            print(f"✗ Error parsing task: {e}")
    else:
        print(f"\n✗ {desc} ({queue_name}): No tasks available")

print("\n" + "="*70)
print("WORKER HEALTH CHECK")
print("="*70)

# Get worker status from heartbeat pattern
worker_keys = redis_client.keys("vg:worker:*")
print(f"Found {len(worker_keys)} worker status keys")

for key in worker_keys:
    data = redis_client.hgetall(key)
    if data:
        print(f"\n{key}:")
        for k, v in data.items():
            print(f"  {k}: {v}")

print("\n" + "="*70)
print("REAL-TIME QUEUE DRAIN TEST (10 seconds)")
print("="*70)

# Watch queue sizes over time
print("\nTime      | Critical | High | Medium | Stream")
print("----------|----------|------|--------|--------")

for i in range(10):
    critical = redis_client.llen("vg:critical")
    high = redis_client.llen("vg:high")
    medium = redis_client.llen("vg:medium")
    stream = redis_client.xlen("vg:ai:results")
    
    print(f"{i:2d}s      | {critical:8d} | {high:4d} | {medium:6d} | {stream:6d}")
    
    if i < 9:
        time.sleep(1)

print("\n" + "="*70)
print("POSTPROCESSOR CONFIDENCE THRESHOLD")
print("="*70)

print("""
Expected behavior:
- Workers consume frames from queues
- Run ONNX inference (0.3s per frame due to hardcoded sleep)
- Postprocessor filters by confidence (default 0.70)
- If confidence >= 0.70, publish to vg:ai:results stream
- If confidence < 0.70, log "below threshold" and skip

Current observation:
- Stream length = 0 → No detections above threshold
- Queues draining → Workers ARE consuming frames
- But NO inference logs → Workers may be failing silently

Hypothesis:
1. Workers are consuming frames ✓
2. But shared memory reads are failing (returning None)
3. So inference never runs
4. Queue drains anyway because task is considered "processed"
""")

