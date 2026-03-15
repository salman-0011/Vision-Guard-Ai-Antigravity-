# ECS v2 Specification: Temporal Persistence & Adaptive Classification

**Document Version:** 1.0  
**Date:** February 20, 2026  
**Status:** Design Specification (Not Yet Implemented)

---

## Executive Summary

Current ECS v1 fails to classify events reliably because:

1. **Correlation window (400ms) << real inference latency (4-8s)**
2. **Fire persistence tied to same frame_id, but each frame_id appears only once per model**
3. **Hard TTL (2s) expires frames before meaningful multi-model fusion**

**v2 Solution:** Camera-level temporal tracking + adaptive classification trigger + realistic timing windows.

---

## Current Architecture Problems (v1)

### Problem 1: Frame-Level Persistence Doesn't Work

```python
# Current logic (frame_state.py)
fire_seen_count: int = 0  # Increments per frame_id

# Reality: Each frame_id appears once per model
# Camera produces: frame_A → fire detects → fire_seen_count = 1 forever
# fire_min_frames > 1 is unreachable in current data flow
```

### Problem 2: Correlation Window vs Reality

```yaml
correlation_window_ms: 400 # When to classify after first result
# Observed worker latency: 4500-7800ms
# Result: Most frames expire before correlation completes
```

### Problem 3: No Camera Context

```python
# Current: Each frame tracked independently
# Missing: "Has camera X seen fire in last N seconds?"
```

---

## V2 Design: Camera-Temporal State Machine

### Core Concept

Replace **per-frame state** with **per-camera temporal state** for persistence-requiring events (fire).

### New Data Structures

#### 1. Camera Event History (New)

```python
@dataclass
class CameraEventHistory:
    """
    Temporal event history per camera.
    Tracks recent detections across multiple frames.
    """
    camera_id: str

    # Recent detection timestamps (sliding window)
    fire_detections: deque[tuple[float, float]]  # (timestamp, confidence)
    weapon_detections: deque[tuple[float, float]]
    fall_detections: deque[tuple[float, float]]

    # Configuration
    history_window_seconds: float = 10.0  # Keep last 10s of history

    def add_detection(self, event_type: str, timestamp: float, confidence: float):
        """Add detection and prune old entries."""
        cutoff = time.time() - self.history_window_seconds

        if event_type == "fire":
            self.fire_detections.append((timestamp, confidence))
            # Prune old
            while self.fire_detections and self.fire_detections[0][0] < cutoff:
                self.fire_detections.popleft()

    def get_recent_fire_count(self, window_seconds: float = 5.0) -> int:
        """Count fire detections in last N seconds."""
        cutoff = time.time() - window_seconds
        return sum(1 for ts, _ in self.fire_detections if ts >= cutoff)

    def get_max_fire_confidence(self, window_seconds: float = 5.0) -> float:
        """Get highest fire confidence in last N seconds."""
        cutoff = time.time() - window_seconds
        recent = [conf for ts, conf in self.fire_detections if ts >= cutoff]
        return max(recent) if recent else 0.0
```

#### 2. Enhanced Frame State (Modified)

```python
@dataclass
class FrameState:
    """Frame state with classification metadata."""

    # Existing fields
    frame_id: str
    camera_id: str
    shared_memory_key: str
    weapon_result: Optional[AIResult] = None
    fire_result: Optional[AIResult] = None
    fall_result: Optional[AIResult] = None
    first_seen_ts: float = field(default_factory=time.time)
    last_update_ts: float = field(default_factory=time.time)

    # NEW: Classification trigger tracking
    classification_attempted: bool = False
    classification_reason: Optional[str] = None  # "weapon_immediate", "window_elapsed", "ttl_expiry"

    # REMOVE: fire_seen_count (moved to CameraEventHistory)
```

---

## V2 Classification Strategy

### Decision Flow

```
For each incoming AI result message:

1. Add result to frame_state
2. Update camera_event_history with detection
3. Check classification triggers:

   TRIGGER A: Weapon Immediate (unchanged)
   IF weapon_result AND confidence >= weapon_threshold:
       → Classify immediately → Emit WEAPON event → Cleanup

   TRIGGER B: Correlation Window Elapsed
   IF frame_age_ms >= correlation_window_ms:
       → Classify using current frame state + camera history
       → Emit event if rules pass → Cleanup

   TRIGGER C: Hard TTL Expiry (periodic scan)
   IF frame_age_seconds >= hard_ttl_seconds:
       → Force classify with partial results
       → Cleanup regardless

4. After classification:
   - Emit event (if any)
   - Add event to camera_event_history
   - Cleanup shared memory
   - Remove from frame buffer
```

### New Rule Engine Logic

```python
def classify_v2(self, frame_state: FrameState, camera_history: CameraEventHistory) -> Optional[Event]:
    """
    V2 classification with camera-level temporal awareness.
    """

    # PRIORITY 1: Weapon (unchanged - immediate)
    if frame_state.has_weapon():
        confidence = normalize(frame_state.weapon_result.confidence)
        if confidence >= self.config.weapon_threshold:
            return create_weapon_event(frame_state, confidence)

    # PRIORITY 2: Fire (NEW - camera-level persistence)
    if frame_state.has_fire():
        confidence = normalize(frame_state.fire_result.confidence)

        # Check current frame threshold
        if confidence >= self.config.fire_threshold:
            # Check camera-level persistence
            recent_fire_count = camera_history.get_recent_fire_count(
                window_seconds=self.config.fire_persistence_window_sec
            )

            if recent_fire_count >= self.config.fire_min_detections:
                return create_fire_event(frame_state, confidence, recent_fire_count)

    # PRIORITY 3: Fall (unchanged for now)
    if frame_state.has_fall():
        confidence = normalize(frame_state.fall_result.confidence)
        if confidence >= self.config.fall_threshold:
            return create_fall_event(frame_state, confidence)

    return None
```

---

## V2 Configuration Changes

### New ECS Config Parameters

```python
class ECSConfig(BaseModel):
    # Timing (UPDATED defaults)
    correlation_window_ms: int = Field(
        default=2000,  # Increased from 400ms
        description="Wait time for multi-model correlation (based on p50 latency)"
    )
    hard_ttl_seconds: float = Field(
        default=10.0,  # Increased from 2.0s
        description="Absolute max frame lifetime (based on p95 latency)"
    )

    # Fire persistence (REDESIGNED)
    fire_confidence_threshold: float = Field(default=0.25)
    fire_min_detections: int = Field(
        default=2,  # Min detections across frames
        description="Min fire detections in persistence window"
    )
    fire_persistence_window_sec: float = Field(
        default=5.0,  # 5 second sliding window
        description="Time window for counting fire detections"
    )

    # Camera history
    camera_history_window_sec: float = Field(
        default=10.0,
        description="How long to keep camera detection history"
    )

    # Classification triggers
    enable_periodic_classification: bool = Field(
        default=True,
        description="Allow periodic classification of aged frames"
    )
    periodic_classification_interval_sec: float = Field(
        default=1.0,
        description="How often to check for aged frames needing classification"
    )
```

---

## Implementation Plan

### Phase 1: Data Structure Updates (Low Risk)

**Files to Create:**

1. `event_classification/buffer/camera_history.py`
   - Implement `CameraEventHistory` class
   - Implement `CameraHistoryManager` (dict of camera_id → history)

**Files to Modify:** 2. `event_classification/buffer/frame_state.py`

- Remove `fire_seen_count` field
- Add `classification_attempted`, `classification_reason`

3. `event_classification/config.py`
   - Update timing defaults
   - Add fire persistence parameters
   - Add camera history parameters

### Phase 2: Classification Logic Updates (Medium Risk)

**Files to Modify:** 4. `event_classification/classification/rule_engine.py`

- Update `classify()` signature to accept `camera_history`
- Implement new fire persistence logic
- Add classification reason tracking

5. `event_classification/buffer/frame_buffer.py`
   - Add method: `get_frames_needing_classification(correlation_window_ms)`
   - Return frames old enough but not yet classified

### Phase 3: Service Integration (Medium Risk)

**Files to Modify:** 6. `event_classification/core/service.py`

- Initialize `CameraHistoryManager`
- Update classification loop:
  - Pass camera_history to rule_engine.classify()
  - Add periodic classification scan
- Update result handling to populate camera_history

7. `event_classification/main.py`
   - Add environment variable parsing for new config params

### Phase 4: Observability (Low Risk)

**Files to Create/Modify:** 8. Add metrics/logging:

- Classification trigger distribution
- Camera-level fire detection rate
- Average frame age at classification
- TTL expiry rate

---

## Migration Strategy

### Backward Compatibility

- V2 is **not backward compatible** with v1 database schema (new fields)
- Recommendation: Clear events table before deploy

### Rollout Steps

1. Deploy code changes
2. Update environment variables in docker-compose.yml
3. Restart ECS container
4. Monitor logs for classification_reason distribution
5. Tune fire_persistence_window_sec based on observed behavior

### Rollback Plan

- Keep v1 code in git branch
- If v2 underperforms, revert docker-compose.yml env vars and restart

---

## Expected Behavior Changes

### Before (v1)

```
Camera produces 10 fire detections at 0.28 confidence over 8 seconds
→ Each frame: fire_seen_count = 1
→ fire_min_frames = 2 never satisfied
→ RESULT: 0 fire events emitted
```

### After (v2)

```
Camera produces 10 fire detections at 0.28 confidence over 8 seconds
→ Camera history accumulates 10 detections
→ Frame 2+: recent_fire_count >= 2 in last 5 seconds
→ RESULT: 8 fire events emitted (after persistence threshold met)
```

---

## Testing Plan

### Unit Tests

1. `CameraEventHistory`:
   - Sliding window pruning
   - Count calculation across time boundaries
2. `RuleEngine.classify_v2()`:
   - Fire persistence logic with mock camera_history
   - Verify event only emitted when min_detections met

### Integration Tests

1. Simulated stream:
   - Inject 5 fire detections over 3 seconds
   - Verify 3-5 events emitted (after threshold met)
2. Latency tolerance:
   - Inject results with 6s delay
   - Verify frames still classified (not expired)

### Load Tests

1. 10 cameras × 5 FPS × 3 models = 150 msg/sec
2. Verify camera_history memory stays bounded
3. Verify no frame buffer leaks

---

## Performance Considerations

### Memory Impact

- **Camera History**: ~10s × 5 FPS × 3 models = 150 entries per camera
- **Per-camera overhead**: ~5 KB
- **10 cameras**: ~50 KB total (negligible)

### CPU Impact

- Periodic classification scan: O(N) where N = buffer size
- Expected N < 500 with new TTL (10s × 5 FPS × 10 cameras)
- Scan every 1s: ~500 iterations/sec (trivial)

### Latency Impact

- Camera history lookup: O(1) dict + O(M) deque scan where M = window size
- M = 50 detections in 10s window → ~50 iterations worst case
- Negligible compared to inference latency (ms vs seconds)

---

## Open Questions / Future Work

1. **Fall detection persistence?**
   - Currently immediate (like weapon)
   - Consider temporal confirmation for fall as well?

2. **Multi-camera correlation?**
   - "Fire in cam1 + smoke in adjacent cam2 = higher confidence"
   - Out of scope for v2, consider v3

3. **Confidence aggregation?**
   - Currently: emit event for each frame meeting criteria
   - Alternative: emit once per "burst" with max/avg confidence

4. **Event deduplication?**
   - If fire emitted at t=0, suppress similar events for next N seconds?
   - UI consideration: prevent alert fatigue

---

## Code Diff Summary (High-Level)

**New Files:**

- `event_classification/buffer/camera_history.py` (~150 lines)

**Modified Files:**

- `event_classification/buffer/frame_state.py` (-5, +10 lines)
- `event_classification/config.py` (+50 lines)
- `event_classification/classification/rule_engine.py` (+100, -30 lines)
- `event_classification/buffer/frame_buffer.py` (+40 lines)
- `event_classification/core/service.py` (+80, -20 lines)
- `event_classification/main.py` (+15 lines)
- `docker-compose.yml` (+8 env vars)

**Total Delta:** ~+450 lines (net ~+350 after removals)

---

## Success Criteria

✅ **Primary Goal:** Fire events emitted when camera shows persistent fire detections  
✅ **Latency Tolerance:** Frames classified even with 6-8s inference delay  
✅ **Observability:** Classification reason logged for debugging  
✅ **Performance:** No memory leaks, <50 KB overhead per 10 cameras

---

## Next Steps

1. **Review this spec** with stakeholders
2. **Implement Phase 1** (data structures) in feature branch
3. **Unit test** camera history logic
4. **Implement Phase 2-3** (classification + service integration)
5. **Integration test** with simulated stream
6. **Deploy to staging** with real camera feed
7. **Monitor & tune** fire_persistence_window_sec based on production data
8. **Merge to main** after validation

---

**End of Specification**
