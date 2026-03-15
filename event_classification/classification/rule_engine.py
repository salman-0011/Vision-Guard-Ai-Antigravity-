"""
VisionGuard AI - Deterministic Classification Rule Engine (v2)

Rule-based event classification with strict priority order.
v2: Camera-level temporal persistence + cooldown deduplication.
"""

import logging
from typing import Optional
from ..buffer.frame_state import FrameState
from ..buffer.camera_history import CameraEventHistory
from ..config import ECSConfig
from .event_models import Event


class RuleEngine:
    """
    Deterministic classification rule engine (v2).
    
    Applies rules in strict priority order:
    1. Weapon (immediate CRITICAL) — with cooldown
    2. Fire/Smoke (temporal persistence) — camera-level history
    3. Fall (immediate MEDIUM) — with cooldown
    
    Only ONE final event per frame.
    """
    
    def __init__(self, config: ECSConfig):
        """
        Initialize rule engine.
        
        Args:
            config: ECS configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.classifications_run = 0
        self.weapon_events = 0
        self.fire_events = 0
        self.fall_events = 0
        self.no_event = 0
        self.cooldown_suppressed = 0
        
        self.logger.info(
            "Rule engine v2 initialized",
            extra={
                "weapon_threshold": config.weapon_confidence_threshold,
                "fire_threshold": config.fire_confidence_threshold,
                "fire_min_detections": config.fire_min_detections,
                "fire_persistence_window_sec": config.fire_persistence_window_sec,
                "fall_threshold": config.fall_confidence_threshold,
                "weapon_cooldown": config.weapon_cooldown_seconds,
                "fire_cooldown": config.fire_cooldown_seconds,
                "fall_cooldown": config.fall_cooldown_seconds,
            }
        )
    
    def classify(
        self,
        frame_state: FrameState,
        camera_history: CameraEventHistory
    ) -> Optional[Event]:
        """
        Classify frame using deterministic rules with camera-level
        temporal awareness and cooldown deduplication.
        
        STRICT PRIORITY ORDER:
        1. Weapon → CRITICAL (immediate, cooldown 30s)
        2. Fire → HIGH (temporal persistence, cooldown 60s)
        3. Fall → MEDIUM (immediate, cooldown 30s)
        
        Args:
            frame_state: Frame state with AI results
            camera_history: Per-camera detection history
            
        Returns:
            Event if classification successful, None otherwise
        """
        self.classifications_run += 1

        def normalize_confidence(raw_confidence: float) -> float:
            confidence = float(raw_confidence)
            if confidence > 1.0:
                confidence = confidence / 100.0
            if not (0.0 <= confidence <= 1.0):
                raise ValueError(
                    f"[CONFIDENCE SCALE ERROR] Invalid confidence value: {confidence}"
                )
            return confidence
        
        # PRIORITY 1: Weapon Detection (IMMEDIATE CRITICAL)
        if frame_state.has_weapon():
            weapon_result = frame_state.weapon_result
            confidence = normalize_confidence(weapon_result.confidence)
            
            if confidence >= self.config.weapon_confidence_threshold:
                frame_state.classification_reason = "weapon_immediate"
                
                # Check cooldown — suppress duplicate events
                if camera_history.is_in_cooldown(
                    'weapon', self.config.weapon_cooldown_seconds
                ):
                    self.cooldown_suppressed += 1
                    self.logger.debug(
                        "Weapon suppressed (cooldown)",
                        extra={
                            "frame_id": frame_state.frame_id,
                            "camera_id": frame_state.camera_id,
                            "confidence": confidence,
                        }
                    )
                    # Still add to history for tracking
                    camera_history.add_detection(
                        'weapon', weapon_result.timestamp, confidence
                    )
                    return None
                
                self.weapon_events += 1
                camera_history.add_detection(
                    'weapon', weapon_result.timestamp, confidence
                )
                camera_history.mark_event_written('weapon')
                
                event = Event(
                    event_id=frame_state.frame_id,
                    event_type="weapon_detected",
                    severity="CRITICAL",
                    camera_id=frame_state.camera_id,
                    frame_id=frame_state.frame_id,
                    timestamp=weapon_result.timestamp,
                    confidence=confidence,
                    bbox=weapon_result.bbox,
                    model_type="weapon",
                    correlation_age_ms=frame_state.get_age_ms()
                )
                
                self.logger.warning(
                    f"WEAPON DETECTED (CRITICAL)",
                    extra={
                        "frame_id": frame_state.frame_id,
                        "camera_id": frame_state.camera_id,
                        "confidence": confidence,
                        "age_ms": frame_state.get_age_ms()
                    }
                )
                
                return event
        
        # PRIORITY 2: Fire Detection (TEMPORAL PERSISTENCE)
        if frame_state.has_fire():
            fire_result = frame_state.fire_result
            confidence = normalize_confidence(fire_result.confidence)
            
            if confidence >= self.config.fire_confidence_threshold:
                # Add to camera history for persistence tracking
                camera_history.add_detection(
                    'fire', fire_result.timestamp, confidence
                )
                
                # Check camera-level persistence
                recent_count = camera_history.get_recent_count(
                    'fire', self.config.fire_persistence_window_sec
                )
                
                if recent_count >= self.config.fire_min_detections:
                    frame_state.classification_reason = "window_elapsed"
                    
                    # Check cooldown
                    if camera_history.is_in_cooldown(
                        'fire', self.config.fire_cooldown_seconds
                    ):
                        self.cooldown_suppressed += 1
                        self.logger.debug(
                            "Fire suppressed (cooldown)",
                            extra={
                                "frame_id": frame_state.frame_id,
                                "camera_id": frame_state.camera_id,
                                "confidence": confidence,
                                "recent_count": recent_count,
                            }
                        )
                        return None
                    
                    # Use max confidence from window for event
                    max_confidence = camera_history.get_max_confidence(
                        'fire', self.config.fire_persistence_window_sec
                    )
                    
                    self.fire_events += 1
                    camera_history.mark_event_written('fire')
                    
                    event = Event(
                        event_id=frame_state.frame_id,
                        event_type="fire_detected",
                        severity="HIGH",
                        camera_id=frame_state.camera_id,
                        frame_id=frame_state.frame_id,
                        timestamp=fire_result.timestamp,
                        confidence=max_confidence,
                        bbox=fire_result.bbox,
                        model_type="fire",
                        correlation_age_ms=frame_state.get_age_ms()
                    )
                    
                    self.logger.warning(
                        f"FIRE DETECTED (HIGH) — persistence confirmed",
                        extra={
                            "frame_id": frame_state.frame_id,
                            "camera_id": frame_state.camera_id,
                            "confidence": max_confidence,
                            "recent_fire_count": recent_count,
                            "age_ms": frame_state.get_age_ms()
                        }
                    )
                    
                    return event
        
        # PRIORITY 3: Fall Detection (IMMEDIATE MEDIUM)
        if frame_state.has_fall():
            fall_result = frame_state.fall_result
            confidence = normalize_confidence(fall_result.confidence)
            
            if confidence >= self.config.fall_confidence_threshold:
                frame_state.classification_reason = "window_elapsed"
                
                # Check cooldown
                if camera_history.is_in_cooldown(
                    'fall', self.config.fall_cooldown_seconds
                ):
                    self.cooldown_suppressed += 1
                    self.logger.debug(
                        "Fall suppressed (cooldown)",
                        extra={
                            "frame_id": frame_state.frame_id,
                            "camera_id": frame_state.camera_id,
                            "confidence": confidence,
                        }
                    )
                    camera_history.add_detection(
                        'fall', fall_result.timestamp, confidence
                    )
                    return None
                
                self.fall_events += 1
                camera_history.add_detection(
                    'fall', fall_result.timestamp, confidence
                )
                camera_history.mark_event_written('fall')
                
                event = Event(
                    event_id=frame_state.frame_id,
                    event_type="fall_detected",
                    severity="MEDIUM",
                    camera_id=frame_state.camera_id,
                    frame_id=frame_state.frame_id,
                    timestamp=fall_result.timestamp,
                    confidence=confidence,
                    bbox=fall_result.bbox,
                    model_type="fall",
                    correlation_age_ms=frame_state.get_age_ms()
                )
                
                self.logger.info(
                    f"FALL DETECTED (MEDIUM)",
                    extra={
                        "frame_id": frame_state.frame_id,
                        "camera_id": frame_state.camera_id,
                        "confidence": confidence,
                        "age_ms": frame_state.get_age_ms()
                    }
                )
                
                return event
        
        # No event classified
        self.no_event += 1
        frame_state.classification_reason = "no_detection"
        
        self.logger.debug(
            f"No event classified",
            extra={
                "frame_id": frame_state.frame_id,
                "has_weapon": frame_state.has_weapon(),
                "has_fire": frame_state.has_fire(),
                "has_fall": frame_state.has_fall()
            }
        )
        
        return None
    
    def should_classify_immediately(self, frame_state: FrameState) -> bool:
        """
        Check if frame should be classified immediately (weapon short-circuit).
        
        Args:
            frame_state: Frame state
            
        Returns:
            True if should classify immediately (weapon detected)
        """
        if frame_state.has_weapon():
            weapon_result = frame_state.weapon_result
            if weapon_result.confidence >= self.config.weapon_confidence_threshold:
                return True
        
        return False
    
    def get_stats(self) -> dict:
        """Get classification statistics."""
        return {
            "classifications_run": self.classifications_run,
            "weapon_events": self.weapon_events,
            "fire_events": self.fire_events,
            "fall_events": self.fall_events,
            "no_event": self.no_event,
            "cooldown_suppressed": self.cooldown_suppressed,
        }
