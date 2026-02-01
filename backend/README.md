# VisionGuard AI - Backend Supervisor

## Overview

The FastAPI Backend Supervisor is the **control plane** for VisionGuard AI. It manages, monitors, and exposes APIs for the system without performing inference or classification.

## Quick Start

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Start the server
python main.py

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation

Once running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/status` | Full system status |
| GET | `/metrics` | System metrics |

### ECS Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ecs/start` | Start ECS process |
| POST | `/ecs/stop` | Stop ECS gracefully |
| POST | `/ecs/restart` | Restart ECS |
| GET | `/ecs/status` | Get ECS status |

### Cameras
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/cameras/register` | Register camera |
| DELETE | `/cameras/{id}` | Unregister camera |
| POST | `/cameras/{id}/start` | Start camera |
| POST | `/cameras/{id}/stop` | Stop camera |
| POST | `/cameras/start-all` | Start all cameras |
| POST | `/cameras/stop-all` | Stop all cameras |
| GET | `/cameras/status` | All cameras status |
| GET | `/cameras/{id}/status` | Single camera status |

### Events & Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events` | List events |
| GET | `/events/{id}` | Get event |
| GET | `/alerts` | List alerts |
| POST | `/alerts/{id}/acknowledge` | Acknowledge alert |

## Architecture

```
Backend Supervisor
├── API Layer (FastAPI routers)
│   ├── system.py - Health, status, metrics
│   ├── ecs.py - ECS lifecycle control
│   ├── cameras.py - Camera management
│   └── events.py - Events and alerts
├── Services Layer
│   ├── ecs_manager.py - ECS process control
│   └── camera_manager.py - Camera process control
├── Core
│   ├── config.py - Configuration
│   ├── supervisor.py - Process management
│   └── lifecycle.py - App lifecycle
└── Models (Pydantic)
    ├── system.py, ecs.py, cameras.py, events.py
```

## Configuration

Environment variables (prefix: `VG_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `VG_HOST` | 0.0.0.0 | Server host |
| `VG_PORT` | 8000 | Server port |
| `VG_ENVIRONMENT` | development | dev/production |
| `VG_REDIS_HOST` | localhost | Redis host |
| `VG_REDIS_PORT` | 6379 | Redis port |
| `VG_LOG_LEVEL` | INFO | Log level |

## Example Usage

```bash
# Check health
curl http://localhost:8000/health

# Start ECS
curl -X POST http://localhost:8000/ecs/start

# Register a camera
curl -X POST http://localhost:8000/cameras/register \
  -H "Content-Type: application/json" \
  -d '{"camera_id": "cam_001", "rtsp_url": "rtsp://192.168.1.100/stream"}'

# Start the camera
curl -X POST http://localhost:8000/cameras/cam_001/start

# Get system status
curl http://localhost:8000/status
```

## Safety Rules

1. **ECS crash → Backend stays alive**
2. **Redis down → APIs respond with degraded status**
3. **No infinite retries on failures**
4. **Non-blocking startup**
5. **Graceful shutdown with timeout**
