# VisionGuard AI — Backend API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

---

## System

### GET /health

Health check endpoint.

```json
{
  "status": "healthy",
  "timestamp": "2026-02-27T18:00:00Z",
  "version": "1.0.0"
}
```

### GET /status

System status with component states and uptime.

```json
{
  "status": "running",
  "uptime_seconds": 3600,
  "components": {
    "redis": "connected",
    "database": "connected",
    "ecs": "running"
  },
  "cameras": {
    "total": 2,
    "running": 1
  }
}
```

### GET /metrics

System performance metrics.

```json
{
  "cpu_percent": 45.2,
  "memory_percent": 62.1,
  "memory_used_gb": 4.8,
  "memory_total_gb": 7.7,
  "disk_used_gb": 12.3,
  "disk_total_gb": 50.0,
  "uptime_seconds": 3600
}
```

---

## ECS Control

### POST /ecs/start

Start the Event Classification Service.

```json
{
  "success": true,
  "message": "ECS started successfully",
  "state": "running"
}
```

### POST /ecs/stop

Stop the Event Classification Service.

```json
{
  "success": true,
  "message": "ECS stopped",
  "state": "stopped"
}
```

### POST /ecs/restart

Restart the Event Classification Service.

```json
{
  "success": true,
  "message": "ECS restarted",
  "state": "running"
}
```

### GET /ecs/status

Current ECS state and statistics.

```json
{
  "state": "running",
  "uptime_seconds": 1200,
  "events_processed": 47,
  "events_classified": 12,
  "last_event_ts": 1709049600.0
}
```

---

## Camera Management

### GET /cameras

List all cameras from `cameras.json` merged with runtime status.

```json
[
  {
    "id": "ip_webcam",
    "name": "IP Webcam Stream",
    "source": "http://192.168.18.253:8080/video",
    "fps": 5,
    "priority": "critical",
    "enabled": false,
    "status": "unknown",
    "pid": null
  },
  {
    "id": "local_video_test",
    "name": "Local Test Video",
    "source": "/app/test-video.mp4",
    "fps": 5,
    "priority": "medium",
    "enabled": true,
    "status": "running",
    "pid": 12345
  }
]
```

### GET /cameras/status

Runtime status of registered cameras (process-level info).

```json
{
  "total": 1,
  "running": 1,
  "stopped": 0,
  "cameras": {
    "local_video_test": {
      "camera_id": "local_video_test",
      "is_running": true,
      "fps": 5,
      "frames_captured": 1500,
      "frames_with_motion": 230
    }
  }
}
```

### POST /cameras/register

Register a new camera for management.

**Request body:**

```json
{
  "camera_id": "lobby_cam",
  "rtsp_url": "rtsp://admin:pass@192.168.1.100:554/stream",
  "fps": 5,
  "motion_threshold": 0.02
}
```

**Response:**

```json
{
  "success": true,
  "message": "Camera lobby_cam registered",
  "camera": {
    "camera_id": "lobby_cam",
    "rtsp_url": "rtsp://admin:pass@192.168.1.100:554/stream",
    "fps": 5,
    "is_running": false
  }
}
```

### POST /cameras/{id}/start

Start a registered camera.

```json
{
  "success": true,
  "message": "Camera lobby_cam started",
  "camera": {
    "camera_id": "lobby_cam",
    "is_running": true
  }
}
```

### POST /cameras/{id}/stop

Stop a running camera.

```json
{
  "success": true,
  "message": "Camera lobby_cam stopped",
  "camera": {
    "camera_id": "lobby_cam",
    "is_running": false
  }
}
```

### DELETE /cameras/{id}

Unregister a camera (must be stopped first).

```json
{
  "success": true,
  "message": "Camera lobby_cam unregistered"
}
```

### GET /cameras/{id}/status

Status of a specific registered camera.

```json
{
  "camera_id": "local_video_test",
  "is_running": true,
  "fps": 5,
  "frames_captured": 1500,
  "frames_with_motion": 230,
  "registered_at": "2026-02-27T10:00:00",
  "started_at": "2026-02-27T10:01:00"
}
```

---

## Events and Alerts

### GET /events

List detected events. Supports filtering and pagination.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max results |
| `offset` | int | 0 | Pagination offset |
| `camera_id` | string | — | Filter by camera |
| `event_type` | string | — | Filter: `fire`, `weapon`, `fall` |
| `severity` | string | — | Filter: `critical`, `high`, `medium` |

**Response:**

```json
{
  "events": [
    {
      "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
      "camera_id": "local_video_test",
      "event_type": "weapon",
      "severity": "critical",
      "start_ts": 1709049600.0,
      "end_ts": 1709049602.0,
      "confidence": 0.72,
      "model_version": "yolov8n",
      "created_at": 1709049602.5
    }
  ],
  "total": 47,
  "limit": 50,
  "offset": 0
}
```

### GET /events/stats

Aggregated event statistics.

```json
{
  "total_events": 47,
  "by_type": {
    "fire": 12,
    "weapon": 28,
    "fall": 7
  },
  "by_severity": {
    "critical": 28,
    "high": 12,
    "medium": 7
  }
}
```

### GET /events/{id}

Single event by ID.

```json
{
  "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "camera_id": "local_video_test",
  "event_type": "weapon",
  "severity": "critical",
  "start_ts": 1709049600.0,
  "end_ts": 1709049602.0,
  "confidence": 0.72,
  "model_version": "yolov8n",
  "created_at": 1709049602.5
}
```

### GET /alerts

List dispatched alerts.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max results |
| `offset` | int | 0 | Pagination offset |
| `status` | string | — | Filter: `pending`, `sent`, `failed` |
| `severity` | string | — | Filter by event severity |
| `camera_id` | string | — | Filter by camera |

**Response:**

```json
{
  "alerts": [
    {
      "id": "b2c3d4e5-6789-01bc-def0-234567890abc",
      "event_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
      "channel": "webhook",
      "status": "sent",
      "attempts": 1,
      "last_attempt_ts": 1709049603.0,
      "created_at": 1709049602.5
    }
  ],
  "total": 12,
  "limit": 50,
  "offset": 0
}
```

### GET /alerts/{id}

Single alert by ID.

```json
{
  "id": "b2c3d4e5-6789-01bc-def0-234567890abc",
  "event_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "channel": "webhook",
  "status": "sent",
  "attempts": 1,
  "last_attempt_ts": 1709049603.0,
  "created_at": 1709049602.5
}
```
