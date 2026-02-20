"""
VisionGuard AI - Debug UI Event Parser

Parses and structures event data from Redis stream.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ParsedEvent:
    """Structured event data for UI display."""
    
    event_id: str
    timestamp: str
    camera_id: str
    event_type: str
    priority: str
    confidence: float
    inference_latency_ms: float
    model_type: str
    bbox: Optional[List[float]]
    frame_data: Optional[str]  # Base64 encoded if present
    raw_data: Dict[str, Any]
    
    @property
    def severity_color(self) -> str:
        """Get color based on priority."""
        colors = {
            "CRITICAL": "#FF4444",
            "HIGH": "#FF8800",
            "MEDIUM": "#FFBB00",
            "LOW": "#44AA44",
        }
        return colors.get(self.priority.upper(), "#888888")
    
    @property
    def display_time(self) -> str:
        """Format timestamp for display."""
        try:
            if isinstance(self.timestamp, str):
                if "T" in self.timestamp:
                    dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromtimestamp(float(self.timestamp))
                return dt.strftime("%H:%M:%S.%f")[:-3]
        except:
            pass
        return str(self.timestamp)[:12]


def parse_event(event_id: str, raw_data: Dict[str, Any]) -> ParsedEvent:
    """
    Parse raw Redis stream data into structured event.
    
    Args:
        event_id: Redis stream message ID
        raw_data: Raw event data dictionary
        
    Returns:
        ParsedEvent with structured fields
    """
    
    # Extract with safe defaults
    camera_id = raw_data.get("camera_id", "unknown")
    # Worker publishes 'model' field, not 'event_type'
    event_type = raw_data.get("event_type", raw_data.get("model", raw_data.get("type", "unknown")))
    
    # Priority / severity
    priority = raw_data.get("priority", raw_data.get("severity", "MEDIUM"))
    if isinstance(priority, str):
        priority = priority.upper()
    
    # Confidence - normalize to 0-1 range if needed
    confidence = 0.0
    try:
        conf_raw = float(raw_data.get("confidence", 0))
        # If confidence is > 1, it's likely a raw score that needs normalization
        # Model outputs values like 35-50, should be 0.35-0.50
        if conf_raw > 1.0:
            confidence = conf_raw / 100.0
        else:
            confidence = conf_raw
    except:
        pass
    
    # Inference latency
    latency = 0.0
    try:
        latency = float(raw_data.get("inference_latency_ms", 
                        raw_data.get("latency_ms", 0)))
    except:
        pass
    
    # Timestamp
    timestamp = raw_data.get("timestamp", event_id.split("-")[0])
    
    # Model type
    model_type = raw_data.get("model_type", raw_data.get("model", "unknown"))
    
    # Bounding box
    bbox = None
    bbox_raw = raw_data.get("bbox", raw_data.get("bounding_box"))
    if bbox_raw:
        try:
            if isinstance(bbox_raw, str):
                bbox = json.loads(bbox_raw)
            elif isinstance(bbox_raw, list):
                bbox = bbox_raw
        except:
            pass
    
    # Frame data (base64)
    frame_data = raw_data.get("frame", raw_data.get("frame_base64"))
    
    return ParsedEvent(
        event_id=event_id,
        timestamp=timestamp,
        camera_id=camera_id,
        event_type=event_type,
        priority=priority,
        confidence=confidence,
        inference_latency_ms=latency,
        model_type=model_type,
        bbox=bbox,
        frame_data=frame_data,
        raw_data=raw_data
    )


def format_metadata_json(event: ParsedEvent) -> str:
    """Format event metadata as pretty JSON for display."""
    display_data = {
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "camera_id": event.camera_id,
        "event_type": event.event_type,
        "priority": event.priority,
        "confidence": round(event.confidence, 4),
        "inference_latency_ms": round(event.inference_latency_ms, 2),
        "model_type": event.model_type,
        "bbox": event.bbox,
        "has_frame": event.frame_data is not None
    }
    return json.dumps(display_data, indent=2)
