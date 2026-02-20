# DEBUGGING SUMMARY - Vision Guard AI Detection System

## PROBLEMS IDENTIFIED

### 1. **Worker Logging was Silent**
- **Symptom**: Queue draining but NO logs about frame processing
- **Root Cause**: Workers had minimal logging for frame consumption/inference
- **How we found it**: Worker logs showed only heartbeats, never actual frame processing
- **Fix**: Added explicit INFO-level logs for:
  - `PROCESSING_TASK` - Log when task is consumed
  - `FRAME_NOT_FOUND` - Log if shared memory read fails (ERROR level)
  - `DETECTION` - Log when confidence >= threshold with confidence score
  - `BELOW_THRESHOLD` - Log when result filtered by confidence

### 2. **Slow Throughput**
- **Symptom**: Queue drain rate ~0.3 frames/sec per worker
- **Root Cause**: Hardcoded `time.sleep(0.3)` before inference in worker.py line 258
- **Fix**: Removed the sleep - no justification in code comments
- **Expected Impact**: ~3-10x faster processing

### 3. **Too High Confidence Threshold (for testing)**
- **Old Settings**:
  - weapon: 0.70
  - fire: 0.60
  - fall: 0.70
- **New Settings**: All = 0.10 (capture everything)
- **Purpose**: To verify if models are detecting anything at all
- **Fix**: Updated all 3 worker services in docker-compose.yml

## SYSTEM STATE BEFORE FIXES

```
Queue Status (at restart):
- vg:critical (weapon):   104 frames
- vg:high (fire):         200 frames  
- vg:medium (fall):       112 frames
- vg:ai:results (stream):   0 detections ❌

Drain Rate (observed):
- Critical: 3 frames/10 sec = 0.3 fps
- High:     1 frame/10 sec = 0.1 fps
- Medium:   3 frames/10 sec = 0.3 fps

Worker Status:
- All 3 workers: Running + Heartbeating
- Processing Activity: NONE VISIBLE → Worker logs show only heartbeats
- Frame Reading: Unknown (no error logs visible)
```

## ARCHITECTURE UNDERSTANDING

```
Camera → Enqueue (3× per frame) → Task Queues
                ↓
         [vg:critical, vg:high, vg:medium]
                ↓
         Workers (Weapon/Fire/Fall)
                ↓
         Inference → Filter by Confidence (0.10 new)
                ↓
         vg:ai:results Stream  
                ↓
         ECS (Event Classification Service)
                ↓
         Database + Alerts
```

## DEPLOYMENT

### Changes Made:
1. **ai_worker/core/worker.py**:
   - Added explicit logging for task consumption
   - Changed from `logger.warning/debug` to `base_logger.info/error`
   - Removed hardcoded 0.3 second sleep

2. **docker-compose.yml**:
   - worker-weapon: WORKER_CONFIDENCE_THRESHOLD=0.70 → 0.10
   - worker-fire: WORKER_CONFIDENCE_THRESHOLD=0.60 → 0.10
   - worker-fall: WORKER_CONFIDENCE_THRESHOLD=0.70 → 0.10

### Restart:
```bash
docker compose down && docker compose up -d --build
```

## NEXT STEPS

1. **Monitor logs after camera starts capturing**:
   ```bash
   docker logs vg-worker-fire --follow | grep -E "DETECTION|PROCESSING|FRAME_NOT_FOUND"
   ```

2. **Check Results Stream**:
   ```bash
   docker exec vg-redis redis-cli XRANGE vg:ai:results 0 -1 | head -20
   ```

3. **Analyze Findings**:
   - If DETECTION logs appear → Models ARE detecting, just needed lower threshold
   - If FRAME_NOT_FOUND logs appear → Shared memory issue, frames not persisting
   - If PROCESSING logs but no DETECTION/BELOW_THRESHOLD → Model output broken

## EXPECTED OUTCOMES

### If Models are Working:
- Detection logs will show confidence scores like: `DETECTION ip_webcam_XXX confidence=0.45`
- Results stream will populate: `docker exec vg-redis redis-cli XLEN vg:ai:results` > 0
- Fire video should trigger fire detections

### If Shared Memory Issue:
- Logs will show: `FRAME_NOT_FOUND` repeatedly
- No inference will run
- Need to debug: camera_capture → shared memory writing

### If Model Quality Issue:
- Processing logs appear but no detections
- Confidence scores all < 0.10
- Indicates models not trained on the specific content in video

## CONFIDENCE THRESHOLD STRATEGY

Currently set to 0.10 to:
- Capture ALL model outputs regardless of confidence
- Understand what the models are actually detecting
- See if fire detector works on fire video

Once we understand model behavior:
- Adjust thresholds based on precision/recall trade-off
- weapon: 0.60-0.80 (high precision needed)
- fire: 0.40-0.60 (detect fire reliably)
- fall: 0.50-0.70 (balance sensitivity)

