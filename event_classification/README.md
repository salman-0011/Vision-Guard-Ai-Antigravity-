# VisionGuard AI - Event Classification Service

**Single-instance, CPU-only, deterministic classification brain for VisionGuard AI.**

## Overview

The Event Classification Service (ECS) is the **sole authority** for event classification, frame correlation, and shared memory cleanup in the VisionGuard AI system.

### What This Module Does

✅ Consumes AI results from Redis stream (`vg:ai:results`)  
✅ Correlates multi-model results in memory  
✅ Applies deterministic classification rules  
✅ Dispatches outputs (alerts, database, frontend)  
✅ **OWNS shared memory cleanup** (authoritative)  

### What This Module Does NOT Do

❌ Horizontal scaling (single instance only)  
❌ AI inference  
❌ HTTP endpoints  
❌ Probabilistic fusion or ML logic  

---

## Critical Design Principles

> [!CRITICAL]
> **Single Instance Only**
> ECS runs as ONE SINGLE PROCESS with NO replicas. It is the sole authority for event classification and frame cleanup.

> [!CRITICAL]
> **Frame Cleanup Ownership**
> ECS is the ONLY component allowed to free shared memory. AI workers are READ-ONLY. Cleanup occurs when frame TTL expires, classification completes, or frame is discarded.

> [!IMPORTANT]
> **Deterministic Classification**
> Rule-based only with strict priority: Weapon → Fire → Fall. No probabilistic fusion, no ML logic.

---

## Architecture

```
AI Workers
  └── Redis Stream: vg:ai:results
               ↓
     EVENT CLASSIFICATION SERVICE (ECS)
     ├── Frame Buffer (in-memory)
     ├── Rule Engine (deterministic)
     ├── Cleanup Manager (authoritative)
     └── Output Dispatchers (async)
               ↓
   Alerts / DB / Frontend / Cleanup
```

---

## Installation

### Requirements

- Python 3.8+
- Redis server
- Camera capture module (for shared memory access)

### Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
redis>=5.0.0
pydantic>=2.0.0
```

---

## Usage

### Basic Example

```python
from event_classification import start_ecs, ECSConfig

# Configure ECS
config = ECSConfig(
    redis_host="localhost",
    redis_port=6379,
    correlation_window_ms=400,
    hard_ttl_seconds=2.0,
    weapon_confidence_threshold=0.85,
    fire_confidence_threshold=0.75,
    fire_min_frames=2,
    fall_confidence_threshold=0.80
)

# Start ECS
ecs = start_ecs(config)

# ECS runs in background process
# Stop when done
from event_classification import stop_ecs
stop_ecs(ecs)
```

---

## Configuration Reference

### ECSConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `redis_host` | str | "localhost" | Redis host |
| `redis_port` | int | 6379 | Redis port |
| `input_stream` | str | "vg:ai:results" | Redis stream to consume |
| `correlation_window_ms` | int | 400 | Correlation window (300-500ms) |
| `hard_ttl_seconds` | float | 2.0 | Hard TTL for frames |
| `weapon_confidence_threshold` | float | 0.85 | Weapon detection threshold |
| `fire_confidence_threshold` | float | 0.75 | Fire detection threshold |
| `fire_min_frames` | int | 2 | Min frames for fire persistence |
| `fall_confidence_threshold` | float | 0.80 | Fall detection threshold |
| `enable_alerts` | bool | True | Enable alert dispatching |
| `enable_database` | bool | True | Enable database writing |
| `enable_frontend` | bool | True | Enable frontend publishing |

---

## Classification Rules

### Strict Priority Order

1. **Weapon** → CRITICAL (immediate, bypasses correlation window)
2. **Fire** → HIGH (requires persistence: ≥ 2 frames)
3. **Fall** → MEDIUM (requires temporal confirmation)

### Rules

- Only ONE final event per frame
- Weapon detection short-circuits correlation window
- Fire requires persistence (fire_seen_count ≥ fire_min_frames)
- Deterministic only (no probabilistic fusion)

---

## Frame Lifecycle

```
Camera Module
  → writes frame to shared memory
  → enqueues task to Redis

AI Workers
  → read frame from shared memory (READ-ONLY)
  → run inference
  → publish result to vg:ai:results

ECS
  → consumes AI results
  → correlates in frame buffer
  → applies classification rules
  → dispatches outputs
  → CLEANS UP shared memory (AUTHORITATIVE)
```

---

## Redis Contracts

### Input (from AI Workers)

**Stream**: `vg:ai:results`

**Payload**:
```json
{
  "frame_id": "cam_001_1737385973123456",
  "camera_id": "cam_001",
  "model": "weapon",
  "confidence": 0.91,
  "timestamp": 1737385973.123456,
  "shared_memory_key": "a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "bbox": [100, 200, 300, 400],
  "inference_latency_ms": 45.2
}
```

### Output (to Downstream)

**Event structure**:
```json
{
  "event_id": "cam_001_1737385973123456",
  "event_type": "weapon_detected",
  "severity": "CRITICAL",
  "camera_id": "cam_001",
  "frame_id": "cam_001_1737385973123456",
  "timestamp": 1737385973.123456,
  "confidence": 0.91,
  "bbox": [100, 200, 300, 400],
  "model_type": "weapon",
  "correlation_age_ms": 45.2
}
```

---

## Main Processing Loop

```python
while not stop:
    # 1. Consume AI results from Redis stream
    messages = stream_consumer.consume()
    
    for msg in messages:
        # 2. Add to frame buffer
        frame_state = frame_buffer.add_result(...)
        
        # 3. Check if ready for classification
        if weapon_detected or correlation_window_elapsed:
            # 4. Classify (deterministic rules)
            event = rule_engine.classify(frame_state)
            
            if event:
                # 5. Dispatch outputs (async, non-blocking)
                alert_dispatcher.dispatch(event)
                database_writer.write(event)
                frontend_publisher.publish(event)
            
            # 6. Cleanup shared memory (AUTHORITATIVE)
            cleanup_manager.cleanup_frame(shared_memory_key)
            
            # 7. Remove from buffer
            frame_buffer.remove_frame(frame_id)
    
    # 8. Handle expired frames (TTL)
    for expired in frame_buffer.get_expired_frames(hard_ttl):
        cleanup_manager.cleanup_frame(shared_memory_key)
        frame_buffer.remove_frame(frame_id)
```

---

## Failure & Recovery

### On Crash

- Redis stream retains data
- On restart: resume from last processed ID or start from latest (configurable)

### Redis Unavailable

- ECS waits safely
- No state corruption

### Memory Pressure

- TTL-based eviction (hard TTL: 2 seconds)
- Cleanup expired frames

---

## Performance

- **CPU-only**: No GPU assumptions
- **Constant-time**: Per-message operations
- **No busy waiting**: Block with timeout
- **No unbounded growth**: TTL-based eviction

---

## Forbidden Actions

❌ **MUST NOT**:
- Introduce consumer groups
- Introduce ECS replicas
- Add HTTP endpoints
- Add AI inference
- Modify Redis contracts
- Delete shared memory outside ECS

---

## Development

### Project Structure

```
event_classification/
├── __init__.py              # Public API
├── config.py                # Configuration models
├── requirements.txt         # Dependencies
├── core/
│   ├── service.py           # Main ECS process
│   └── lifecycle.py         # Startup/shutdown hooks
├── buffer/
│   ├── frame_state.py       # Frame state models
│   └── frame_buffer.py      # In-memory buffer
├── classification/
│   ├── event_models.py      # Event output models
│   └── rule_engine.py       # Deterministic rules
├── redis_client/
│   └── stream_consumer.py   # XREAD consumer
├── cleanup/
│   └── cleanup_manager.py   # Authoritative cleanup
└── output/
    ├── alert_dispatcher.py  # Alert output
    ├── database_writer.py   # DB output
    └── frontend_publisher.py # Frontend output
```

---

## License

Part of VisionGuard AI surveillance system.

---

## Support

For issues or questions, refer to the main VisionGuard AI documentation.
