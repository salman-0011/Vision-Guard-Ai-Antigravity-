# VisionGuard AI - Camera Capture Module

**Low-level camera ingestion service for VisionGuard AI surveillance system.**

## Overview

This module provides CPU-only, edge-based camera capture and motion detection for the VisionGuard AI system. It is designed to be **orchestrated by FastAPI**, not to run standalone.

### What This Module Does

✅ Connects to multiple RTSP cameras (one OS process per camera)  
✅ Captures frames at configurable FPS  
✅ Performs lightweight motion detection  
✅ Stores frames in shared memory  
✅ Enqueues task metadata to Redis queues  

### What This Module Does NOT Do

❌ AI inference or event classification  
❌ Alert generation or notifications  
❌ Database operations  
❌ HTTP endpoints or web UI  
❌ Auto-restart crashed processes (FastAPI's responsibility)  

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                        │
│  (Control Plane - starts/stops/monitors camera processes)  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ imports camera_capture
                       │
         ┌─────────────▼──────────────┐
         │  camera_capture module     │
         │  (Public API)              │
         └─────────────┬──────────────┘
                       │
         ┌─────────────▼──────────────┐
         │   ProcessManager           │
         │   (Multi-camera control)   │
         └─────────────┬──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │ Camera  │   │ Camera  │   │ Camera  │
   │ Process │   │ Process │   │ Process │
   │  (PID1) │   │  (PID2) │   │  (PID3) │
   └────┬────┘   └────┬────┘   └────┬────┘
        │             │             │
        │ Motion?     │ Motion?     │ Motion?
        │             │             │
        ├─────────────┼─────────────┤
        │                           │
   ┌────▼────┐              ┌──────▼──────┐
   │ Shared  │              │    Redis    │
   │ Memory  │              │   Queues    │
   │ (frames)│              │ (metadata)  │
   └─────────┘              └─────────────┘
```

---

## Installation

### Requirements

- Python 3.8+
- OpenCV with RTSP support
- Redis server

### Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
opencv-python>=4.8.0
redis>=5.0.0
pydantic>=2.0.0
numpy>=1.24.0
```

---

## FastAPI Integration

### Basic Usage

```python
from fastapi import FastAPI
from camera_capture import start_cameras, stop_cameras, get_status, CaptureConfig, CameraConfig

app = FastAPI()

# Global process manager
manager = None

@app.on_event("startup")
async def startup():
    global manager
    
    # Create configuration
    config = CaptureConfig(
        cameras=[
            CameraConfig(
                camera_id="cam_001",
                rtsp_url="rtsp://192.168.1.100:554/stream",
                fps=5,
                motion_threshold=0.02
            ),
            CameraConfig(
                camera_id="cam_002",
                rtsp_url="rtsp://192.168.1.101:554/stream",
                fps=5,
                motion_threshold=0.02
            )
        ]
    )
    
    # Start all cameras
    manager = start_cameras(config)

@app.on_event("shutdown")
async def shutdown():
    global manager
    if manager:
        stop_cameras(manager)

@app.get("/cameras/status")
async def cameras_status():
    """Get status of all cameras."""
    return get_status(manager)

@app.post("/cameras/{camera_id}/restart")
async def restart_camera(camera_id: str):
    """Restart a specific camera."""
    from camera_capture import restart_camera
    success = restart_camera(manager, camera_id)
    return {"success": success}
```

### Configuration from File

```python
import json
from camera_capture import CaptureConfig

# Load from JSON
with open("camera_config.json") as f:
    config_dict = json.load(f)

config = CaptureConfig(**config_dict)
manager = start_cameras(config)
```

**camera_config.json:**
```json
{
  "cameras": [
    {
      "camera_id": "cam_001",
      "rtsp_url": "rtsp://192.168.1.100:554/stream",
      "fps": 5,
      "motion_threshold": 0.02
    }
  ],
  "redis": {
    "host": "localhost",
    "port": 6379,
    "db": 0
  },
  "logging": {
    "level": "INFO",
    "format": "json"
  }
}
```

---

## Configuration Reference

### CameraConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `camera_id` | str | **required** | Unique camera identifier |
| `rtsp_url` | str | **required** | RTSP stream URL |
| `fps` | int | 5 | Frames per second (1-30) |
| `motion_threshold` | float | 0.02 | Motion detection threshold (0.0-1.0) |

### RedisConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | str | "localhost" | Redis host |
| `port` | int | 6379 | Redis port |
| `db` | int | 0 | Redis database number |
| `password` | str | None | Redis password (optional) |

### SharedMemoryConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_frame_size_mb` | int | 10 | Maximum frame size in MB |
| `cleanup_interval_seconds` | int | 300 | Cleanup interval for stale blocks |

### RetryConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_retries` | int | 5 | Maximum retry attempts |
| `initial_backoff_seconds` | float | 1.0 | Initial backoff duration |
| `max_backoff_seconds` | float | 60.0 | Maximum backoff duration |
| `backoff_multiplier` | float | 2.0 | Backoff multiplier |

### BufferConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_buffer_size` | int | 100 | Max tasks to buffer when Redis unavailable |
| `drop_policy` | str | "oldest" | Drop policy: "oldest" or "newest" |

---

## Redis Contract

### Queue Names

- `vg:critical` → Fast-path processing
- `vg:high` → Normal processing priority
- `vg:medium` → Low urgency processing

**Important:** Priority represents **operational urgency**, NOT threat classification. AI workers will later map detected events to appropriate queues.

### Task Payload Structure

```json
{
  "camera_id": "cam_001",
  "frame_id": "cam_001_1737385973123456",
  "shared_memory_key": "a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "timestamp": 1737385973.123456,
  "priority": "medium"
}
```

**Strict Rules:**
- ❌ NO raw frames in Redis
- ❌ NO detection results
- ❌ NO backend state
- ✅ ONLY metadata references

---

## Shared Memory Contract

### Write (Camera Module)

```python
from camera_capture.storage import SharedMemoryImpl

shm = SharedMemoryImpl(max_frame_size_mb=10)
key = shm.write_frame(frame)  # Returns unique key
```

### Read (AI Workers)

```python
frame = shm.read_frame(key)  # Returns NumPy array
```

### Cleanup

```python
shm.cleanup(key)  # Release memory
```

---

## Guarantees

### What This Module Guarantees

✅ **One process per camera** for isolation  
✅ **Automatic RTSP reconnection** with exponential backoff  
✅ **FPS throttling** to prevent overwhelming downstream  
✅ **Motion filtering** to reduce unnecessary AI inference  
✅ **Graceful shutdown** with resource cleanup  
✅ **Crash detection** (reported via `get_status()`)  

### What This Module Does NOT Guarantee

❌ **Auto-restart** on crash (FastAPI decides)  
❌ **Frame delivery** if shared memory is full (skips safely)  
❌ **Task delivery** if Redis buffer is full (drops oldest)  
❌ **Real-time guarantees** (best-effort CPU processing)  

---

## Error Handling

### Camera Disconnect

- **Behavior:** Automatic reconnection with exponential backoff
- **Max retries:** Configurable (default: 5)
- **Status:** Reported as "reconnecting" then "alive" or "dead"

### Redis Unavailable

- **Behavior:** Buffer tasks briefly (default: 100 tasks)
- **Buffer full:** Drop oldest/newest based on policy
- **Reconnection:** Automatic, flushes buffer on success

### Shared Memory Full

- **Behavior:** Skip frame safely, log warning
- **No crash:** Process continues capturing

### Process Crash

- **Behavior:** Process exits, status becomes "dead"
- **Restart:** FastAPI must call `restart_camera(manager, camera_id)`

---

## Logging

### Required Context Fields

All logs include:
- `camera_id`: Camera identifier
- `process_id`: OS process ID
- `module_name`: Module name

### Log Formats

**JSON (default):**
```json
{
  "timestamp": "2026-01-20 19:42:53",
  "level": "INFO",
  "camera_id": "cam_001",
  "process_id": 12345,
  "module_name": "camera_capture.core.camera_process",
  "message": "Frame captured"
}
```

**Text:**
```
[2026-01-20 19:42:53] [INFO] [cam_001] [12345] [camera_capture.core.camera_process] Frame captured
```

---

## Performance

### Motion Detection

- **Algorithm:** OpenCV BackgroundSubtractorMOG2
- **Performance:** Significantly cheaper than AI inference
- **Target:** Real-time CPU processing (hardware-dependent)

### Resource Usage

- **CPU:** ~5-10% per camera (1080p @ 5 FPS)
- **Memory:** ~50-100 MB per camera process
- **Shared Memory:** Configurable (default: 10 MB per frame)

---

## Troubleshooting

### Camera won't connect

1. Check RTSP URL is correct
2. Verify network connectivity
3. Check camera supports RTSP
4. Review logs for connection errors

### High CPU usage

1. Reduce FPS
2. Lower motion detection sensitivity
3. Check for camera reconnection loops

### Redis tasks not appearing

1. Verify Redis is running
2. Check Redis connection config
3. Review buffer statistics in logs

### Process keeps crashing

1. Check logs for error details
2. Verify RTSP stream is stable
3. Check shared memory limits
4. Review motion detection threshold

---

## Development

### Project Structure

```
camera_capture/
├── __init__.py              # Public API
├── config.py                # Configuration models
├── core/
│   ├── camera_process.py    # Single camera process
│   ├── process_manager.py   # Multi-camera orchestration
│   └── lifecycle.py         # FastAPI integration hooks
├── capture/
│   ├── rtsp_handler.py      # RTSP connection management
│   └── frame_grabber.py     # FPS control
├── detection/
│   └── motion_detector.py   # Motion detection
├── storage/
│   ├── shared_memory_interface.py  # Abstract interface
│   └── shared_memory_impl.py       # Concrete implementation
├── queue/
│   ├── task_models.py       # Redis payload structure
│   └── redis_producer.py    # Redis enqueueing
└── utils/
    ├── retry.py             # Retry logic
    └── logging.py           # Structured logging
```

---

## License

Part of VisionGuard AI surveillance system.

---

## Support

For issues or questions, refer to the main VisionGuard AI documentation.
