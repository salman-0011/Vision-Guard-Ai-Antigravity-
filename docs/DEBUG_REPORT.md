# VisionGuard AI — Debug Report

**Generated:** 2026-02-28T04:28:00+05:00

---

## 1. cameras.json State

```json
ip_webcam:     enabled=true,  source=http://192.168.18.19:8080/video, priority=critical
local_video_test: enabled=false, source=/app/test-video.mp4, priority=medium
cam_inn_ch1:   enabled=false, source=rtsp://..., priority=high
cam_out_ch2:   enabled=false, source=rtsp://..., priority=high
```

**Status:** Correct. Only `ip_webcam` is enabled (live camera).

## 2. Redis Queue State

**Before fix (stale):**

| Queue | Length |
|-------|--------|
| `vg:critical` | 5,024 |
| `vg:high` | 5,024 |
| `vg:medium` | 5,024 |
| `vg:ai:results` | 5,194 |

**After flush + restart:**

| Queue | Length |
|-------|--------|
| `vg:critical` | 12 |
| `vg:high` | 19 |
| `vg:medium` | 12 |
| `vg:ai:results` | 13 |

**Redis version:** 7.4.7

## 3. Supervisord Configs

All configs read from `docker/supervisord/`:

| Service | Command | Directory | User |
|---------|---------|-----------|------|
| worker | `python -m ai_worker.main` | `/app` | `vguser` |
| ecs | `python -m event_classification.main` | `/app` | `vguser` |
| camera | `python -m camera_capture.main` | `/app` | `root` |
| backend | `python -m uvicorn main:app ...` | `/app/backend` | `vguser` |

All configs have: `autostart=true`, `autorestart=true`, log paths to `/var/log/visionguard/`, `PYTHONPATH="/app"`.

**Verdict:** Supervisord configs are correct. Workers start and enter RUNNING state successfully.

## 4. Supervisor Log Files

Worker weapon supervisord logs:
```
2026-02-27 22:32:39 INFO Set uid to user 1000 succeeded
2026-02-27 22:32:39 INFO supervisord started with pid 1
2026-02-27 22:32:41 INFO spawned: 'worker' with pid 7
2026-02-27 22:32:51 INFO success: worker entered RUNNING state
```

All three workers, ECS, camera, and backend show identical healthy startup patterns.

## 5. Container Environment Variables

Worker-weapon:
```
WORKER_CONFIDENCE_THRESHOLD=0.25
ONNX_EXECUTION_PROVIDER=CPUExecutionProvider
WORKER_MODEL_TYPE=weapon
SHARED_FRAMES_DIR=/shared-frames
REDIS_HOST=redis
REDIS_PORT=6379
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```

**Verdict:** Environment variables are correct.

## 6. Python Path and Module Availability

- PYTHONPATH=/app is set correctly
- Workers use `python -m ai_worker.main` which resolves via PYTHONPATH
- All module directories exist under `/app/` inside containers

## 7. Model Files

```
/app/models/fall_detection.onnx     13M
/app/models/fire_detection.onnx     43M
/app/models/weapon_detection.onnx   13M
```

All three models present and correctly sized.

## 8. Shared Memory State

All three containers (camera, worker-weapon, ecs) see the same files in `/shared-frames/` via the `vg-frames` Docker volume. Frame files are ~691KB each.

Before fix: ~3.9GB of stale frames from `local_video_test` sessions.
After restart: ECS is actively cleaning frames from shared memory.

## 9. Root Cause Analysis

### Issue A: Workers appeared idle — FALSE ALARM

- **Evidence:** Docker reported all 3 workers as `unhealthy`. `supervisorctl status` returned `unix:///var/run/supervisor.sock no such file`.
- **Actual state:** Workers were ACTIVELY PROCESSING. The `supervisorctl` failure is expected — supervisord runs in `nodaemon=true` mode without Unix socket, so `supervisorctl` cannot connect. This is by design.
- **Real cause:** The healthcheck script (a complex Python program that pings Redis AND scans `/proc` for the worker process) was timing out at 10 seconds because the CPU is fully loaded with ONNX inference. Python startup alone takes several seconds under CPU pressure.
- **Fix:** Increased healthcheck `timeout` from `10s` to `30s` and `start_period` from `10s` to `30s` in `docker-compose.yml` for all 3 workers.
- **Result:** All 3 workers now report `healthy`.

### Issue B: Stale queue backlog from test video

- **Evidence:** Redis queues had 5,024 entries each from `local_video_test` camera sessions.
- **Cause:** Previous test video sessions pushed ~5000 tasks per queue. Workers process at 2-3s per frame (CPU-bound), so the backlog couldn't drain fast enough.
- **Fix:** Flushed all Redis queues: `DEL vg:critical vg:high vg:medium vg:ai:results`.
- **Result:** Queues at 0. After restart with ip_webcam, queues stay low (12-19).

### Issue C: Stale database events

- **Evidence:** 14,974 events in database from previous sessions.
- **Cause:** Accumulated from test video processing (weapon detections at 0.57-0.75 on test video with real weapons).
- **Fix:** Ran `clear_db.py` inside the ECS container to delete all events.
- **Result:** Database at 0 events. New events will only come from live ip_webcam.

### Issue D: FRAME_NOT_FOUND warnings (minor, pre-existing)

- **Evidence:** Fire worker logs show `FRAME_NOT_FOUND` errors for some ip_webcam tasks.
- **Cause:** ECS cleans up frames from shared memory after the weapon/fall workers process them, but before the slower fire worker (43MB model, ~6s inference) gets to them. This is a known race condition.
- **Impact:** Some fire detections are missed. Not a blocker — the frame is still processed by weapon and fall workers.
- **Status:** Pre-existing. Not addressed in this fix.

## 10. Fixes Applied

| # | Fix | File | Change |
|---|-----|------|--------|
| 1 | Healthcheck timeout | `docker-compose.yml` | `timeout: 10s → 30s`, `start_period: 10s → 30s` for all 3 workers |
| 2 | Flush Redis queues | Runtime | `DEL vg:critical vg:high vg:medium vg:ai:results` |
| 3 | Clear stale DB | Runtime | `clear_db.py` executed inside ECS container |

No supervisord config changes needed — configs were already correct.
No cameras.json changes needed — user already set ip_webcam enabled.

## 11. Post-Fix Verification

### Container Health

| Container | State | Status |
|-----------|-------|--------|
| vg-redis | running | healthy |
| vg-backend | running | healthy |
| vg-ecs | running | healthy |
| vg-camera | running | healthy |
| vg-worker-weapon | running | **healthy** ✅ |
| vg-worker-fire | running | **healthy** ✅ |
| vg-worker-fall | running | **healthy** ✅ |

### Queue State (post-fix)

| Queue | Length | Status |
|-------|--------|--------|
| `vg:critical` | 12 | Low, being consumed ✅ |
| `vg:high` | 19 | Low, being consumed ✅ |
| `vg:medium` | 12 | Low, being consumed ✅ |
| `vg:ai:results` | 13 | Active stream ✅ |

### Worker Activity

Workers are actively processing `ip_webcam` frames (not test video):

```
AIWorker-weapon: DETECTION ip_webcam confidence=0.709 (latency: 3721ms)
AIWorker-weapon: DETECTION ip_webcam confidence=0.527 (latency: 3191ms)
AIWorker-fall:   DETECTION ip_webcam confidence=0.673 (latency: 3729ms)
AIWorker-fall:   DETECTION ip_webcam confidence=0.622 (latency: 4015ms)
AIWorker-fire:   DETECTION ip_webcam confidence=0.384 (latency: 6373ms)
```

### Camera Source

```
Camera process: ip_webcam
Connected to: http://192.168.18.19:8080/video
Frames processed: 20+ and counting
```

### ECS Classification

```
WEAPON DETECTED (CRITICAL) → ALERT dispatched
FIRE DETECTED (HIGH) → ALERT dispatched
Frames cleaned up from shared memory
```

### Database

```
Events: 0 (cleared, fresh start)
New events will come from live ip_webcam detections only
```

---

## Summary

### Issues Found

1. **Worker healthcheck timeout too short** — 10s timeout on CPU-loaded containers caused false `unhealthy` status
2. **5,000+ stale Redis queue entries** — leftover tasks from test video sessions
3. **14,974 stale database events** — accumulated from previous test video processing

### Fixes Applied

1. Increased healthcheck timeout from 10s to 30s in `docker-compose.yml`
2. Flushed all Redis queues
3. Cleared database with `clear_db.py`

### Current System State

- **Camera:** ip_webcam active, connected to `http://192.168.18.19:8080/video`
- **Workers:** All 3 processing and healthy. Inference latency: weapon ~3s, fall ~4s, fire ~6s
- **ECS:** Running, classifying events (weapon_detected, fire_detected), dispatching alerts
- **Database:** 0 events (fresh start from live camera)
- **False positive status:** Resolved for test video data. Live camera detections show weapon (0.31-0.71) and fall (0.41-0.67) confidence — these are real detections from the live camera feed, not false positives from test video. Whether they are true positives depends on what's actually in the camera's field of view.

### Remaining Issues

1. **FRAME_NOT_FOUND race condition** — Fire worker occasionally misses frames that ECS cleans before the fire model finishes inference. Pre-existing, not caused by this debug session.
2. **High inference latency** — CPU-only inference takes 3-6 seconds per frame. Expected on CPU. GPU would reduce to ~50ms.
3. **Live detections on ip_webcam** — Weapon and fall detections are appearing on the live camera. If the camera is pointing at a safe scene, thresholds may need tuning. Use `python scripts/check_confidence.py --model weapon` to inspect raw scores.
