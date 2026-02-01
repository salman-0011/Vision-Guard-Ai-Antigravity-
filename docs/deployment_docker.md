# VisionGuard AI - Docker Deployment Guide

## Quick Start (CPU-Only)

```bash
# 1. Clone and navigate
cd "Vision Guard Ai ( Anti gravity)"

# 2. Copy environment file
cp .env.example .env

# 3. Build and start
docker-compose build
docker-compose up -d

# 4. Verify
docker-compose ps
curl http://localhost:8000/health
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker Network                     │
│                  (visionguard)                       │
├─────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐ │
│  │  Redis  │  │ Backend │  │   Camera Capture    │ │
│  │ :6379   │  │ :8000   │  │                     │ │
│  └────┬────┘  └────┬────┘  └─────────┬───────────┘ │
│       │            │                  │             │
│       ▼            ▼                  ▼             │
│  ┌─────────────────────────────────────────────────┐│
│  │              Redis Queues                       ││
│  │  vg:critical | vg:high | vg:medium             ││
│  └────────────────────┬───────────────────────────┘│
│                       ▼                             │
│  ┌─────────────────────────────────────────────────┐│
│  │          AI Workers (scalable)                  ││
│  │      ──► vg:ai:results stream                   ││
│  └────────────────────┬───────────────────────────┘│
│                       ▼                             │
│  ┌─────────────────────────────────────────────────┐│
│  │       ECS (SINGLETON - DO NOT SCALE)            ││
│  │       Consumes vg:ai:results via XREAD          ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

---

## Service Management

### Start All Services
```bash
docker-compose up -d
```

### Scale Workers (ONLY workers can scale)
```bash
# Scale to 3 workers
docker-compose up -d --scale worker=3

# Scale to 5 workers
docker-compose up -d --scale worker=5
```

### Stop All
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ecs
docker-compose logs -f worker
```

---

## GPU Workers (Optional)

GPU workers require NVIDIA Docker runtime.

### Prerequisites
```bash
# Install nvidia-docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### Enable GPU Workers
Uncomment the `worker-gpu` service in `docker-compose.yml`:

```yaml
worker-gpu:
  build:
    context: .
    dockerfile: docker/Dockerfile.worker-gpu
  ...
```

Then:
```bash
docker-compose up -d worker-gpu
```

---

## ECS Singleton Enforcement

> ⚠️ **CRITICAL**: ECS must NEVER be scaled. It maintains a correlation buffer.

**Enforced by:**
1. `deploy.replicas: 1` in docker-compose.yml
2. `container_name: vg-ecs` (unique name)
3. Process supervision (supervisord)

**DO NOT RUN:**
```bash
# ❌ NEVER DO THIS
docker-compose up -d --scale ecs=2
```

---

## Failure Scenarios

| Scenario | Behavior | Recovery |
|----------|----------|----------|
| Redis down | All services pause | Auto-reconnect when Redis returns |
| Backend crash | Does NOT affect ECS or workers | supervisord restarts backend |
| ECS crash | Stream consumption pauses | supervisord restarts ECS; resumes from last offset |
| Worker crash | Other workers continue | supervisord restarts worker |
| Worker overload | Queue grows, TTL evicts old frames | Scale workers: `--scale worker=N` |

---

## Volumes

| Volume | Path | Purpose |
|--------|------|---------|
| vg-redis-data | /data (redis) | Redis persistence |
| vg-app-data | /data | SQLite DB, configs |
| vg-logs | /var/log/visionguard | Application logs |
| vg-shm | /dev/shm | Shared memory for frames |

---

## Environment Variables

See `.env.example` for full list. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| BACKEND_PORT | 8000 | API port |
| REDIS_PORT | 6379 | Redis port |
| ECS_LOG_LEVEL | INFO | ECS logging |
| WORKER_MODEL_TYPE | weapon | Worker model |
| ONNX_EXECUTION_PROVIDER | CPUExecutionProvider | CPU or GPU |

---

## Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Backend status (detailed)
curl http://localhost:8000/status

# Redis check
docker-compose exec redis redis-cli ping
```

---

## Troubleshooting

### Services not starting
```bash
docker-compose logs | grep -i error
```

### ECS not consuming
```bash
# Check Redis stream
docker-compose exec redis redis-cli XLEN vg:ai:results
```

### Worker memory issues
```bash
# Increase limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 2G
```
