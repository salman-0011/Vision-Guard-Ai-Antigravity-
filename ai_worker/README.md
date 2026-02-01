# VisionGuard AI - AI Worker Module

**CPU-only, single-model AI inference worker for VisionGuard AI surveillance system.**

## Overview

This module provides stateless, headless AI inference workers that process frames from Redis queues using ONNX models. Each worker is specialized for ONE model and ONE queue.

### What This Module Does

✅ Consumes tasks from ONE dedicated Redis queue  
✅ Reads frames from shared memory (READ-ONLY)  
✅ Runs CPU-only ONNX inference  
✅ Publishes results to Redis stream  
✅ Includes `shared_memory_key` for Event Classification cleanup  

### What This Module Does NOT Do

❌ Cleanup shared memory (Event Classification Service owns this)  
❌ Control cameras or perform motion detection  
❌ Send alerts or notifications  
❌ Write to databases  
❌ Expose HTTP APIs  
❌ Combine multiple models or consume multiple queues  

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend / FastAPI                        │
│          (Starts/stops/monitors AI workers)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │   ai_worker module         │
         │   (Public API)             │
         └─────────────┬──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │ Weapon  │   │  Fire   │   │  Fall   │
   │ Worker  │   │ Worker  │   │ Worker  │
   │(PID1)   │   │(PID2)   │   │(PID3)   │
   └────┬────┘   └────┬────┘   └────┬────┘
        │             │             │
   vg:critical   vg:high      vg:medium
        │             │             │
        └─────────────┼─────────────┘
                      │
              ┌───────▼────────┐
              │  Shared Memory │
              │  (READ-ONLY)   │
              └───────┬────────┘
                      │
              ┌───────▼────────┐
              │ vg:ai:results  │
              │  Redis Stream  │
              └────────────────┘
```

---

## Critical: Frame Lifecycle Ownership

**AI Worker is READ-ONLY for shared memory.**

```
Camera Module
  → writes frame to shared memory
  → enqueues task to Redis

AI Worker
  → reads frame from shared memory (READ-ONLY)
  → runs inference
  → publishes result (with shared_memory_key) to Redis

Event Classification Service
  → consumes AI results
  → correlates multi-model outputs
  → CLEANS UP shared memory
```

**Why**: Enables multi-model inference, temporal reasoning, and prevents race conditions.

---

## Installation

### Requirements

- Python 3.8+
- ONNX Runtime (CPU)
- Redis server
- Camera capture module (for shared memory access)

### Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
onnxruntime>=1.16.0
redis>=5.0.0
numpy>=1.24.0
opencv-python>=4.8.0
pydantic>=2.0.0
```

---

## Usage

### Basic Example

```python
from ai_worker import start_worker, WorkerConfig

# Configure weapon detection worker
config = WorkerConfig(
    model_type="weapon",
    redis_input_queue="vg:critical",
    onnx_model_path="/models/weapon_detector.onnx",
    confidence_threshold=0.85,
    
    # ONNX Runtime thread tuning
    intra_op_num_threads=4,
    inter_op_num_threads=2,
    
    # Model input size
    input_width=640,
    input_height=640
)

# Start worker
worker = start_worker(config)

# Worker runs in background process
# Stop when done
from ai_worker import stop_worker
stop_worker(worker)
```

### Worker Specialization Examples

#### Weapon Detection Worker

```python
weapon_config = WorkerConfig(
    model_type="weapon",
    redis_input_queue="vg:critical",  # High priority queue
    onnx_model_path="/models/yolov8n_weapon.onnx",
    confidence_threshold=0.85
)
weapon_worker = start_worker(weapon_config)
```

#### Fire Detection Worker

```python
fire_config = WorkerConfig(
    model_type="fire",
    redis_input_queue="vg:high",
    onnx_model_path="/models/fire_detector.onnx",
    confidence_threshold=0.75
)
fire_worker = start_worker(fire_config)
```

#### Fall Detection Worker

```python
fall_config = WorkerConfig(
    model_type="fall",
    redis_input_queue="vg:medium",
    onnx_model_path="/models/fall_detector.onnx",
    confidence_threshold=0.80
)
fall_worker = start_worker(fall_config)
```

### Configuration from File

```python
import json
from ai_worker import WorkerConfig, start_worker

# Load from JSON
with open("worker_config.json") as f:
    config_dict = json.load(f)

config = WorkerConfig(**config_dict)
worker = start_worker(config)
```

---

## Configuration Reference

### WorkerConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_type` | str | **required** | Model type: "weapon", "fire", "fall" |
| `redis_input_queue` | str | **required** | Queue: "vg:critical", "vg:high", "vg:medium" |
| `onnx_model_path` | str | **required** | Path to .onnx model file |
| `confidence_threshold` | float | 0.75 | Min confidence (0.0-1.0) |
| `redis_host` | str | "localhost" | Redis host |
| `redis_port` | int | 6379 | Redis port |
| `redis_db` | int | 0 | Redis database number |
| `intra_op_num_threads` | int | 4 | ONNX intra-op threads |
| `inter_op_num_threads` | int | 2 | ONNX inter-op threads |
| `input_width` | int | 640 | Model input width |
| `input_height` | int | 640 | Model input height |
| `normalize_mean` | list | [0.485, 0.456, 0.406] | Normalization mean (RGB) |
| `normalize_std` | list | [0.229, 0.224, 0.225] | Normalization std (RGB) |

**Thread Tuning Guardrail**: Total ONNX threads per worker must not exceed `CPU cores / worker_count`.

---

## Redis Contracts

### Input (from Camera Module)

**Queue**: `vg:critical`, `vg:high`, or `vg:medium`

**Payload**:
```json
{
  "camera_id": "cam_001",
  "frame_id": "cam_001_1737385973123456",
  "shared_memory_key": "a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "timestamp": 1737385973.123456,
  "priority": "medium"
}
```

### Output (to Event Classification Service)

**Stream**: `vg:ai:results`

**Payload** (CRITICAL: includes `shared_memory_key`):
```json
{
  "camera_id": "cam_001",
  "frame_id": "cam_001_1737385973123456",
  "shared_memory_key": "a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "model": "weapon",
  "confidence": 0.91,
  "bbox": [100, 200, 300, 400],
  "timestamp": 1737385973.123456,
  "inference_latency_ms": 45.2
}
```

**Why `shared_memory_key` is included**: Event Classification Service needs it to cleanup frames after correlation.

---

## Inference Pipeline

### 1. Model Loading (Startup)

- Load ONNX model once
- Configure CPU execution provider
- Set thread tuning parameters
- Keep model resident in memory

### 2. Preprocessing

- Resize frame to model input size
- Convert BGR to RGB
- Normalize to [0, 1]
- Apply mean/std normalization
- Transpose to (C, H, W)
- Add batch dimension

### 3. Inference

- Run ONNX inference (CPU-only)
- One frame per inference (no batching)
- Track inference latency

### 4. Postprocessing

- Decode model output
- Apply confidence threshold
- Extract bounding boxes (if applicable)
- NO tracking, NO temporal logic

---

## Logging

### Required Context Fields

All logs include:
- `model_type`: Worker model type
- `camera_id`: Camera identifier
- `frame_id`: Frame identifier
- `process_id`: OS process ID
- `module_name`: Module name
- `inference_latency_ms`: Inference latency (for capacity planning)

### Log Format (JSON)

```json
{
  "timestamp": "2026-01-21 16:41:39",
  "level": "INFO",
  "model_type": "weapon",
  "camera_id": "cam_001",
  "frame_id": "cam_001_1737385973123456",
  "process_id": 12345,
  "module_name": "ai_worker.core.worker",
  "message": "Inference completed and published",
  "inference_latency_ms": 45.2
}
```

---

## Performance

### CPU-Only Execution

- **Provider**: CPUExecutionProvider (ONNX Runtime)
- **Thread Tuning**: Configurable intra-op and inter-op threads
- **Guardrail**: Total threads ≤ CPU cores / worker_count

### Typical Performance

- **YOLOv8n (640x640)**: ~50-100ms per frame (4-core CPU)
- **Fire CNN (224x224)**: ~20-30ms per frame
- **Pose Detection**: ~80-150ms per frame

**Note**: Performance varies by hardware and model complexity.

---

## Error Handling

### Shared Memory Read Fails

- **Behavior**: Log warning + skip frame
- **No cleanup**: Worker is READ-ONLY

### Inference Fails

- **Behavior**: Log error + skip frame
- **No cleanup**: Worker is READ-ONLY

### Redis Publish Fails

- **Behavior**: Retry 3 times with 100ms delay
- **Max retries exceeded**: Drop result

### Worker Crash

- **Behavior**: Process exits
- **Restart**: External supervisor (backend) restarts worker

---

## Troubleshooting

### Worker won't start

1. Check ONNX model path exists
2. Verify Redis is running
3. Check model type and queue are valid
4. Review logs for initialization errors

### High CPU usage

1. Reduce thread count (intra_op_num_threads, inter_op_num_threads)
2. Check total threads ≤ CPU cores / worker_count
3. Verify model is optimized for CPU

### Inference too slow

1. Use smaller model (e.g., YOLOv8n instead of YOLOv8m)
2. Reduce input size (e.g., 416x416 instead of 640x640)
3. Optimize ONNX model with graph optimization

### Results not appearing in Redis

1. Verify Redis stream exists
2. Check confidence threshold (may be too high)
3. Review publisher statistics in logs

---

## Development

### Project Structure

```
ai_worker/
├── __init__.py              # Public API
├── config.py                # Configuration models
├── requirements.txt         # Dependencies
├── core/
│   ├── worker.py            # Main worker process
│   └── lifecycle.py         # Startup/shutdown hooks
├── inference/
│   ├── model_loader.py      # ONNX model loading
│   ├── preprocessor.py      # Frame preprocessing
│   ├── inference_engine.py  # ONNX inference
│   └── postprocessor.py     # Result postprocessing
├── redis_client/
│   ├── task_consumer.py     # Redis queue consumer
│   └── result_publisher.py  # Redis stream publisher
├── shared_memory/
│   └── frame_manager.py     # Frame reader (READ-ONLY)
└── utils/
    └── logging.py           # Structured logging
```

---

## License

Part of VisionGuard AI surveillance system.

---

## Support

For issues or questions, refer to the main VisionGuard AI documentation.
