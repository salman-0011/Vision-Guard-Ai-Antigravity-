"""
VisionGuard AI - Deterministic Classification Rule Engine

Rule-based event classification with strict priority order.
NO probabilistic fusion, NO ML logic, deterministic only.
"""

import logging
from typing import Optional
from ..buffer.frame_state import FrameState
from ..config import ECSConfig
from .event_models import Event


class RuleEngine:
    """
    Deterministic classification rule engine.
    
    Applies rules in strict priority order:
    1. Weapon (immediate CRITICAL)
    2. Fire/Smoke (requires persistence)
    3. Fall (requires temporal confirmation)
    
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
        
        self.logger.info(
            "Rule engine initialized",
            extra={
                "weapon_threshold": config.weapon_confidence_threshold,
                "fire_threshold": config.fire_confidence_threshold,
                "fire_min_frames": config.fire_min_frames,
                "fall_threshold": config.fall_confidence_threshold
            }
        )
    
    def classify(self, frame_state: FrameState) -> Optional[Event]:
        """
        Classify frame using deterministic rules.
        
        STRICT PRIORITY ORDER:
        1. Weapon → CRITICAL (immediate)
        2. Fire → HIGH (requires persistence)
        3. Fall → MEDIUM (requires temporal confirmation)
        
        Args:
            frame_state: Frame state with AI results
            
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
        # REFINEMENT: Weapon short-circuits correlation window
        if frame_state.has_weapon():
            weapon_result = frame_state.weapon_result
            
            # Defensive normalization safeguard
            confidence = normalize_confidence(weapon_result.confidence)
            
            if confidence >= self.config.weapon_confidence_threshold:
                self.logger.debug(
                    "Weapon threshold passed",
                    extra={
                        "confidence": confidence,
                        "threshold": self.config.weapon_confidence_threshold
                    }
                )
                
                self.weapon_events += 1
                
                event = Event(
                    event_id=frame_state.frame_id,
                    event_type="weapon_detected",
                    severity="CRITICAL",
                    camera_id=frame_state.camera_id,
                    frame_id=frame_state.frame_id,
                    timestamp=weapon_result.timestamp,
                    confidence=confidence,  # Use normalized confidence
                    bbox=weapon_result.bbox,
                    model_type="weapon",
                    correlation_age_ms=frame_state.get_age_ms()
                )
                
                self.logger.warning(
                    f"WEAPON DETECTED (CRITICAL)",
                    extra={
                        "frame_id": frame_state.frame_id,
                        "camera_id": frame_state.camera_id,
                        "confidence": confidence,  # Use normalized confidence
                        "age_ms": frame_state.get_age_ms()
                    }
                )
                
                return event
        
        # PRIORITY 2: Fire Detection (HIGH - requires persistence)
        # REFINEMENT: Check fire_seen_count for persistence
        if frame_state.has_fire():
            fire_result = frame_state.fire_result

            # Defensive normalization safeguard
            confidence = normalize_confidence(fire_result.confidence)

            if (confidence >= self.config.fire_confidence_threshold and
                frame_state.fire_seen_count >= self.config.fire_min_frames):
                
                self.fire_events += 1
                
                event = Event(
                    event_id=frame_state.frame_id,
                    event_type="fire_detected",
                    severity="HIGH",
                    camera_id=frame_state.camera_id,
                    frame_id=frame_state.frame_id,
                    timestamp=fire_result.timestamp,
                    confidence=confidence,
                    bbox=fire_result.bbox,
                    model_type="fire",
                    correlation_age_ms=frame_state.get_age_ms()
                )
                
                self.logger.warning(
                    f"FIRE DETECTED (HIGH)",
                    extra={
                        "frame_id": frame_state.frame_id,
                        "camera_id": frame_state.camera_id,
                        "confidence": confidence,
                        "fire_seen_count": frame_state.fire_seen_count,
                        "age_ms": frame_state.get_age_ms()
                    }
                )
                
                return event
        
        # PRIORITY 3: Fall Detection (MEDIUM - requires temporal confirmation)
        if frame_state.has_fall():
            fall_result = frame_state.fall_result

            # Defensive normalization safeguard
            confidence = normalize_confidence(fall_result.confidence)

            if confidence >= self.config.fall_confidence_threshold:
                self.fall_events += 1
                
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
        
        REFINEMENT: Weapon detection bypasses correlation window.
        
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
        """
        Get classification statistics.
        
        Returns:
            Dictionary with classification stats
        """
        return {
            "classifications_run": self.classifications_run,
            "weapon_events": self.weapon_events,
            "fire_events": self.fire_events,
            "fall_events": self.fall_events,
            "no_event": self.no_event
        }
