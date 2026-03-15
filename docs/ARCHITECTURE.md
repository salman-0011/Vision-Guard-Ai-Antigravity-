# VisionGuard AI — System Architecture

## Overview

VisionGuard AI is a real-time video surveillance system that detects fire, weapons, and fallen persons using CPU-based ONNX inference. Camera feeds are processed through a multi-stage pipeline, and confirmed events are stored in a SQLite database and displayed on a React dashboard.

## Pipeline Flow

```
[Camera Source]
    ↓ RTSP / HTTP / file stream
[Camera Capture] → Shared Memory (frames) + Redis Queues (tasks)
    ↓ vg:critical / vg:high / vg:medium
[AI Workers ×3] → fire_detection.onnx
                   weapon_detection.onnx
                   fall_detection.onnx
    ↓ vg:ai:results stream
[ECS — Event Classification Service]
    ↓                    ↓
[SQLite DB]         [Alert Dispatcher]
    ↓
[FastAPI Backend] → [React Dashboard]
```

## Component Responsibilities

### Camera Capture (`camera_capture/`)

Reads RTSP, HTTP, or file-based video streams. Runs background subtraction (MOG2) for motion detection. When motion is detected, writes the frame to POSIX shared memory and pushes task metadata (camera ID, frame path, timestamp) to priority-based Redis queues. One process runs per camera. Priority queues determine processing order: critical cameras go to `vg:critical`, high to `vg:high`, medium to `vg:medium`.

Key files: `core/camera_process.py`, `core/motion_detector.py`, `core/frame_writer.py`, `config.py`, `main.py`

### AI Workers (`ai_worker/`)

CPU-only ONNX inference workers. One worker per model type (fire, weapon, fall). Each worker listens on its assigned Redis queue, reads the frame from shared memory (read-only — never deletes or modifies frames), runs YOLOv8 inference through the ONNX model, applies preprocessing (resize 640×640, normalize, NCHW transpose) and postprocessing (NMS, confidence filtering), then publishes the result to the `vg:ai:results` Redis stream. Workers never touch shared memory cleanup.

Key files: `inference/preprocessor.py`, `inference/postprocessor.py`, `inference/onnx_runner.py`, `config.py`, `main.py`

### Event Classification Service (`event_classification/`)

Singleton service that consumes the `vg:ai:results` Redis stream. Correlates AI results in a frame buffer, applying deterministic classification rules with priority ordering (Weapon → Fire → Fall). When confidence exceeds the configured ECS threshold for a detection type, it writes a confirmed event to SQLite and dispatches alerts. The ECS is the authoritative owner of shared memory cleanup — it deletes frames from shared memory after all workers have processed them or after TTL expiration.

Key files: `core/classifier.py`, `core/frame_buffer.py`, `core/stream_consumer.py`, `alerts/dispatcher.py`, `config.py`, `main.py`

### FastAPI Backend (`backend/`)

Control plane only. Does NOT perform inference or classification. Provides a REST API for: system health and status, ECS lifecycle control (start/stop/restart), camera management (register, start, stop, status), and event and alert queries from the SQLite database.

Key files: `app/api/system.py`, `app/api/ecs.py`, `app/api/cameras.py`, `app/api/events.py`, `app/services/camera_manager.py`, `main.py`

### React Dashboard (`visionguard-dashboard-29/`)

Web UI built with React, TypeScript, Tailwind CSS, and shadcn/ui. Fetches data from the FastAPI backend via REST polling every 10 seconds using React Query. Pages: Dashboard (stats + recent events), Live Monitoring, Incidents (event list with filters), Analytics (detection charts), Cameras (status + start/stop controls), Settings. No WebSocket — polling only.

Key files: `src/pages/Dashboard.tsx`, `src/pages/Incidents.tsx`, `src/pages/Cameras.tsx`, `src/pages/Analytics.tsx`, `src/config/api.ts`

## Redis Keys and Streams

| Key | Type | Purpose |
|-----|------|---------|
| `vg:critical` | List | High priority camera task queue |
| `vg:high` | List | Medium priority camera task queue |
| `vg:medium` | List | Low priority camera task queue |
| `vg:ai:results` | Stream | AI worker output stream (consumed by ECS) |

## Database Schema

### Table: `events`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `camera_id` | TEXT | Source camera identifier |
| `event_type` | TEXT | `weapon`, `fire`, or `fall` |
| `severity` | TEXT | `critical`, `high`, or `medium` |
| `start_ts` | REAL | Event start epoch (seconds) |
| `end_ts` | REAL | Event end epoch (seconds) |
| `confidence` | REAL | 0.0–1.0 |
| `model_version` | TEXT | ONNX model identifier |
| `created_at` | REAL | Row creation epoch |

### Table: `event_evidence`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `event_id` | TEXT (FK) | References `events.id` |
| `evidence_type` | TEXT | `clip` or `snapshot` |
| `storage_provider` | TEXT | `cloudinary`, `s3`, or `local` |
| `public_url` | TEXT | URL to evidence file |
| `created_at` | REAL | Row creation epoch |

### Table: `alerts`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `event_id` | TEXT (FK) | References `events.id` |
| `channel` | TEXT | `webhook`, `email`, or `sms` |
| `status` | TEXT | `pending`, `sent`, or `failed` |
| `attempts` | INTEGER | Delivery attempt count |
| `last_attempt_ts` | REAL | Last attempt epoch |
| `created_at` | REAL | Row creation epoch |

## Current Limitations

- **CPU-only inference** — no GPU acceleration
- **No video clip storage** — events contain metadata only, no recorded evidence
- **No user authentication** — frontend bypasses auth (demo mode)
- **No WebSocket real-time push** — REST polling every 10 seconds
- **Fall detection limited** — identifies persons via pose model; fall gesture classification via ECS v2 temporal logic is pending
