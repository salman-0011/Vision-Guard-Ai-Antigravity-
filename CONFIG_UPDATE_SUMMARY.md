# CONFIGURATION UPDATE SUMMARY

## ✅ Changes Applied

### 1. **Updated Confidence Thresholds** (Production Values)

```yaml
# docker-compose.yml

worker-weapon: 0.75  (was 0.10)
  → High precision for weapon detection
  → Minimizes false alarms

worker-fire:   0.25  (was 0.10)  
  → Lowered to match model's natural output (0.28-0.35)
  → Will catch real fire detections

worker-fall:   0.55  (was 0.10)
  → Moderate threshold for safety-critical fall detection
```

### 2. **Enabled Motion Detection**

```json
// cameras.json

"global": {
    "motion_detection": true,  // was false
    "default_fps": 5,
    "reconnect_delay_sec": 5
}
```

**Motion Detection Configuration:**
- **Threshold**: 0.02 (2% of frame needs motion to trigger)
- **Algorithm**: MOG2 Background Subtraction (fast, CPU-efficient)
- **Purpose**: Skip static frames to save processing power

---

## How Motion Detection Works

### Processing Flow:

```
Camera grabs frame (5 fps)
         ↓
Motion Detector analyzes
         ↓
    Has motion? (> 2% change)
         ↓
    YES → Enqueue to all 3 queues → Workers process
    NO  → Skip frame (save compute)
```

### Motion Detector Algorithm:

**MOG2 (Mixture of Gaussians V2)**:
- Builds a background model over time (500 frame history)
- Compares each new frame to background
- Pixels that differ = "motion"
- If > 2% of pixels changed → motion detected

**Performance:**
- Very fast (milliseconds per frame)
- CPU-only (no GPU needed)
- Adapts to gradual changes (lighting, weather)

---

## Expected Behavior

### With Motion Detection ON:

✅ **Static scenes** (no movement):
- Camera still captures at 5 fps
- Motion detector filters out frames
- No tasks sent to workers
- **Result**: Save 90%+ compute when nothing happening

✅ **Movement detected** (fire, person, object):
- Motion detector triggers
- Frame sent to all 3 workers
- Normal processing resumes

⚠️ **Gradual changes** (sunrise, sunset):
- Background model adapts slowly
- Won't trigger false motion

❌ **First ~500 frames**:
- Background model building
- May get false positives initially
- Stabilizes after ~2 minutes

---

## Verification Steps

### 1. Check if motion detection is filtering frames:

```bash
docker logs vg-camera 2>&1 | grep -i motion
```

Expected: Should see motion detection stats in logs

### 2. Monitor queue with motion ON vs OFF:

**With motion OFF:**
```
5 fps × 3 queues = 15 tasks/sec
After 1 minute = ~900 tasks queued
```

**With motion ON (static scene):**
```
~0 tasks/sec (no motion)
After 1 minute = ~0 tasks
```

### 3. Test motion triggering:

Move something in front of camera → should see tasks appear in queues

```bash
# Watch queue sizes
docker exec vg-redis redis-cli LLEN vg:critical
```

---

## Threshold Strategy Explained

### Fire: 0.25
**Why so low?**
- Your fire detector outputs 0.28-0.35 on real fire
- Threshold 0.25 = catches all your real detections
- Test on non-fire to verify false positive rate

### Weapon: 0.75
**Why high?**
- Weapon false alarms are VERY costly (panic, police response)
- Need high confidence to avoid crying wolf
- Better to miss some than false alarm

### Fall: 0.55
**Why moderate?**
- Falls are safety-critical (need to detect)
- But not as urgent as weapons
- Balanced between sensitivity and precision

---

## Next Steps

### After Restart:

1. **Verify motion detection working:**
   ```bash
   docker logs vg-camera --follow | grep motion
   ```

2. **Test with fire video:**
   - Point IP Webcam at fire video
   - Should get detections with confidence ~0.28-0.35
   - Check: `docker exec vg-redis redis-cli XLEN vg:ai:results`

3. **Test static scene:**
   - Point camera at static object
   - Should see minimal/no tasks being queued
   - Verify motion detection is filtering

4. **Measure false positive rate:**
   - Record non-fire video for 5 minutes
   - Count how many fire detections appear
   - If > 1-2 false positives = raise threshold to 0.30

---

## Summary

| Setting | Old | New | Reason |
|---------|-----|-----|--------|
| Fire threshold | 0.10 | 0.25 | Match model output |
| Weapon threshold | 0.10 | 0.75 | High precision |
| Fall threshold | 0.10 | 0.55 | Safety balance |
| Motion detection | OFF | ON | Save compute |

All changes saved in:
- `docker-compose.yml` (thresholds)
- `cameras.json` (motion detection)

**Ready to restart and test!**

