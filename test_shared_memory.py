#!/usr/bin/env python3
"""
Test shared memory frame reading.
"""

import sys
import os
import json
import redis

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from camera_capture.storage.shared_memory_impl import SharedMemoryImpl

redis_client = redis.Redis(
    host="localhost",
    port=6380,
    db=0,
    decode_responses=True
)

# Get a task from queue
task_json = redis_client.rpop("vg:critical")
if not task_json:
    task_json = redis_client.rpop("vg:high")
if not task_json:
    task_json = redis_client.rpop("vg:medium")

if not task_json:
    print("No tasks in any queue!")
    sys.exit(1)

task_data = json.loads(task_json)
shared_memory_key = task_data["shared_memory_key"]
frame_id = task_data["frame_id"]
camera_id = task_data["camera_id"]

print(f"Testing frame read:")
print(f"  Frame ID: {frame_id}")
print(f"  Camera: {camera_id}")
print(f"  Shared Memory Key: {shared_memory_key}")

# Try to read from shared memory
shared_mem = SharedMemoryImpl(max_frame_size_mb=10)
frame = shared_mem.read_frame(shared_memory_key)

if frame is not None:
    print(f"\n✓ Frame successfully read from shared memory!")
    print(f"  Shape: {frame.shape}")
    print(f"  Data type: {frame.dtype}")
    print(f"  Min/Max values: {frame.min()}/{frame.max()}")
else:
    print(f"\n✗ Frame NOT found in shared memory!")
    print(f"  This explains why workers are not producing detections.")
    print(f"  Workers log 'Frame not found' and skip to next task.")

# Put task back
redis_client.lpush(task_data.get("priority", "vg:critical"), task_json)
print(f"\n[Task returned to queue]")

