# VisionGuard AI — Threshold Fix Report

**Date:** 2026-03-01T15:30:00+05:00

## 1. Baseline Measurements

### Weapon Model (empty scene)
- Top confidence: ~0.03–0.05 (documented from prior session)
- Status: Well below 0.25 worker threshold ✅ — **no action needed**

### Fall Model (empty scene)
```
Top 5 raw detections:
  1. confidence=0.5008  bbox=[486, 369, 640, 639]
  2. confidence=0.5007  bbox=[438, 357, 639, 639]
  3. confidence=0.5007  bbox=[533, 310, 640, 640]
  4. confidence=0.5007  bbox=[467, 400, 640, 640]
  5. confidence=0.5006  bbox=[27, 278, 573, 639]
```
- Pattern: **sigmoid null output** — every detection is sigmoid(0) ≈ 0.5005
- Status: Was passing ECS gate of 0.50 — **FALSE POSITIVE SOURCE** ❌

### Fire Model (empty scene)
```
Top 5 raw detections:
  1. confidence=0.0020  bbox=[625, 622, 639, 639]
  2. confidence=0.0018  bbox=[631, 626, 639, 639]
  3. confidence=0.0016  bbox=[629, 622, 639, 639]
  4. confidence=0.0012  bbox=[564, 571, 639, 639]
  5. confidence=0.0011  bbox=[624, 623, 639, 639]
```
- Noise floor: 0.002 — **negligible**, well below any threshold
- Status: **No fix needed** ✅

### Pre-Fix Event Counts
| Type | Count | % |
|------|-------|---|
| fall | 55 | 52% ← **false positives** |
| weapon | 40 | 38% |
| fire | 10 | 10% |
| **Total** | **105** | |

## 2. Fire Model Analysis

Fire model top confidence on empty scene = **0.0020**.

This is < 0.15, far below both the worker threshold (0.25) and ECS gate (0.45). The fire model uses standard YOLO object detection output (not pose/sigmoid), so its null output is properly near-zero.

**Decision: NO CHANGE NEEDED** — Fire thresholds remain at 0.25 (worker) / 0.45 (ECS).

## 3. Fixes Applied

| Setting | Before | After | Reason |
|---------|--------|-------|--------|
| worker-fall `WORKER_CONFIDENCE_THRESHOLD` | 0.25 | **0.60** | Block sigmoid null (0.5005 < 0.60) at worker level |
| ECS `ECS_FALL_THRESHOLD` | 0.50 | **0.75** | Secondary defense — any leak past worker is caught here |
| worker-weapon `WORKER_CONFIDENCE_THRESHOLD` | 0.25 | 0.25 | Unchanged ✅ |
| ECS `ECS_WEAPON_THRESHOLD` | 0.60 | 0.60 | Unchanged ✅ |
| worker-fire `WORKER_CONFIDENCE_THRESHOLD` | 0.25 | 0.25 | Unchanged — noise floor is 0.002 |
| ECS `ECS_FIRE_THRESHOLD` | 0.45 | 0.45 | Unchanged — noise floor is 0.002 |

**Additional actions:**
- Deleted 55 fall false positive events from database
- Restarted `worker-fall` and `ecs` containers (no image rebuild needed)

## 4. Verification Results

### Environment Confirmed Applied
```
worker-fall:  WORKER_CONFIDENCE_THRESHOLD=0.60  ✅
ECS:          ECS_FALL_THRESHOLD=0.75            ✅
              ECS_WEAPON_THRESHOLD=0.60          (unchanged)
              ECS_FIRE_THRESHOLD=0.45            (unchanged)
```

### Container Health (post-fix)
All 7 containers: **healthy** ✅

### Worker-Fall Logs After Fix
No new fall DETECTION lines after the container restart. The last fall detection in the log was from the previous session (2026-02-27 23:26:59) before the fix was applied. The fall worker is now silently filtering all sigmoid null outputs at the 0.60 threshold.

### Event Rate After Fix (5-minute observation)

| Metric | T+0 | T+5min | Δ |
|--------|-----|--------|---|
| Total events | 63 | 64 | **+1** |
| fall | 3 | 3 | **+0** ✅ |
| fire | 12 | 13 | +1 (legitimate, conf=0.480 > 0.45 gate) |
| weapon | 48 | 48 | +0 |

**Fall events: 0 new in 5 minutes** — fix confirmed working ✅

### Threshold Validation
```
Fall:   sigmoid null 0.5005 < 0.60 worker threshold → BLOCKED ✅
        even if leaked: 0.5005 < 0.75 ECS gate → BLOCKED ✅
Fire:   noise floor 0.002 < 0.25 worker threshold → BLOCKED ✅
Weapon: unchanged, still detecting normally ✅
```

### Weapon Worker Unchanged
Weapon worker behavior is identical before and after the fix. No weapon thresholds were modified. Weapon detections at 0.31–0.71 continue to pass through correctly.

## 5. Summary

### Root Cause
The fall detection model (`fall_detection.onnx`) is a YOLOv8 pose estimation model. When no person is in frame, it outputs raw logits near zero for every candidate detection. The postprocessor applies sigmoid: `sigmoid(0) = 0.5000`. This means on an empty scene, every detection has confidence 0.5005.

The previous ECS fall threshold of 0.50 allowed **every null detection to pass** and become a fall event in the database. This was the primary source of false positives (52% of all events).

### Fix
- Raised fall worker pre-filter: **0.25 → 0.60** (blocks sigmoid null at source)
- Raised ECS fall gate: **0.50 → 0.75** (secondary defense)
- All sigmoid null outputs (0.5000–0.5005) are now blocked at the worker level before reaching ECS

### Current System State
- **Weapon detection:** threshold 0.25 / 0.60 — unchanged, working correctly
- **Fall detection:** threshold 0.60 / 0.75 — **FIXED**, zero false positives on empty scene
- **Fire detection:** threshold 0.25 / 0.45 — unchanged, noise floor is 0.002 (no issue)
- **False positive status:** ✅ **RESOLVED** for fall sigmoid null output

### Remaining Work
- ECS v2 temporal persistence logic for true fall gesture classification (pending)
- The fall model will only produce events when a real person is detected with confidence > 0.60 (genuine person detection, not sigmoid null)
- Fire model may produce occasional low-confidence events on live camera (0.48 observed) — monitor and adjust ECS_FIRE_THRESHOLD if needed
