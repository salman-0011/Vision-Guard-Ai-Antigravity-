# VisionGuard AI — Confidence Threshold Tuning Guide

## 1. How Thresholds Work

VisionGuard uses a **two-tier confidence system**:

1. **Worker pre-filter** (loose, fast) — Applied in the AI worker immediately after ONNX inference. Detections below this threshold are discarded before leaving the worker. This keeps the Redis stream clean and reduces ECS load.

2. **ECS gate** (strict, final) — Applied in the Event Classification Service when deciding whether to write an event to the database. Only detections that pass this threshold generate a confirmed event and trigger alerts.

The worker threshold should always be **lower** than the ECS threshold. The worker acts as a coarse filter to remove obvious noise. The ECS applies the real decision.

## 2. Where to Configure

### Worker Pre-filter

Set in `docker-compose.yml` under each worker's environment section:

```yaml
# Fire worker
- WORKER_CONFIDENCE_THRESHOLD=0.25

# Weapon worker
- WORKER_CONFIDENCE_THRESHOLD=0.25

# Fall worker
- WORKER_CONFIDENCE_THRESHOLD=0.25
```

After changing, restart the affected worker container:

```bash
docker compose restart vg-worker-fire
```

### ECS Gate Thresholds

Set in `event_classification/config.py` (defaults shown):

```python
weapon_confidence_threshold = 0.60
fire_confidence_threshold = 0.45
fall_confidence_threshold = 0.75
```

These can also be overridden via environment variables in `docker-compose.yml` for the ECS container.

## 3. Current Values

| Threshold | Value | Meaning |
|-----------|-------|---------|
| Worker pre-filter (weapon) | 0.25 | Weapon detections below 25% confidence are silently dropped at the worker level |
| Worker pre-filter (fire) | 0.25 | Fire detections below 25% confidence are silently dropped |
| Worker pre-filter (fall) | 0.60 | Fall detections below 60% confidence are dropped — blocks sigmoid null output (0.5005) |
| ECS weapon gate | 0.60 | Weapon detections need ≥60% confidence to generate an event |
| ECS fire gate | 0.45 | Fire detections need ≥45% confidence to generate an event |
| ECS fall gate | 0.75 | Fall detections need ≥75% confidence to generate an event |

Weapon has the highest ECS threshold because false positives (everyday objects misidentified as weapons) are the most damaging to system credibility.

## 4. How to Inspect Real Scores

Use `scripts/check_confidence.py` to see what the model actually outputs on your camera:

```bash
# Check weapon model scores
python scripts/check_confidence.py --model weapon

# Check fire model scores
python scripts/check_confidence.py --model fire

# Check fall model scores
python scripts/check_confidence.py --model fall
```

The script will:
1. Read `cameras.json` and grab a frame from the first enabled camera
2. Run the ONNX model on that frame with the exact same preprocessing as the real worker
3. Print the top 5 raw detection scores with bounding boxes
4. Show current thresholds for comparison

Example output:

```
  Model: weapon_detection.onnx
  Camera source: http://192.168.18.253:8080/video
  Frame: 640x480 grabbed

  Top 5 raw detections:
    1. confidence=0.72  bbox=[120, 45, 380, 290]
    2. confidence=0.31  bbox=[130, 50, 370, 280]
    3. confidence=0.08  bbox=[400, 100, 500, 200]
    4. confidence=0.04  bbox=[10, 10, 50, 50]
    5. confidence=0.02  bbox=[200, 300, 250, 350]

  Current thresholds (from docker-compose.yml / ECS config):
    Worker pre-filter:  0.25
    ECS weapon gate:    0.50
```

## 5. Signs Thresholds Are Wrong

### Too low (false positives)

- Events generated when the room is empty
- Events triggered by blank walls, furniture, or lighting changes
- The dashboard fills with hundreds of events in minutes
- Detection types that don't match what's actually in the scene

### Too high (false negatives)

- No events generated when a real threat is clearly visible
- The model reports high confidence in `check_confidence.py` output but no events appear in the database
- Camera is capturing motion but the event list stays empty

## 6. Tuning Process

1. **Observe noise floor** — Point the camera at a safe scene (empty room, hallway). Run `check_confidence.py` several times. Note the highest confidence score. This is your noise floor.

2. **Observe real signal** — Introduce the target object (or use a test video). Run `check_confidence.py` again. Note the confidence score for the real detection.

3. **Set worker threshold** — Set `WORKER_CONFIDENCE_THRESHOLD` just above the noise floor. This lets real detections through while filtering noise.

4. **Set ECS threshold** — Set the ECS gate threshold halfway between the noise floor and the real detection score. For example:
   - Noise floor: 0.15
   - Real detection: 0.65
   - ECS threshold: ~0.40

5. **Restart workers** — Apply the changes:

   ```bash
   docker compose restart vg-worker-fire vg-worker-weapon vg-worker-fall
   docker compose restart vg-ecs
   ```

6. **Monitor** — Watch the dashboard for 10 minutes. Check:
   - Are events being generated?
   - Are they real or noise?
   - Adjust ECS threshold up if too many false positives, down if real events are being missed.

7. **Clear test data** — After tuning, clear the test events:

   ```bash
   python scripts/clear_db.py
   ```
