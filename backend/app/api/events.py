"""
VisionGuard AI - Events & Alerts API Routes

Read-only endpoints for classified events and alerts.
GET /events
GET /events/{id}
GET /alerts
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path

from app.models.events import (
    Event, Alert, EventType, Severity,
    EventListResponse, AlertListResponse
)
from app.utils.logging import get_logger

router = APIRouter(tags=["Events & Alerts"])
logger = get_logger(__name__)

# In-memory storage for demo purposes
# In production, this would be replaced with database queries
_events_store: list = []
_alerts_store: list = []


def _generate_sample_events():
    """Generate sample events for demonstration."""
    return [
        Event(
            event_id="evt_001",
            event_type=EventType.WEAPON_DETECTED,
            severity=Severity.CRITICAL,
            camera_id="cam_001",
            frame_id="cam_001_1737385973123456",
            timestamp=datetime.utcnow().isoformat() + "Z",
            confidence=0.91,
            bbox=[100, 200, 300, 400],
            model_type="weapon",
            correlation_age_ms=45.2
        ),
        Event(
            event_id="evt_002",
            event_type=EventType.FIRE_DETECTED,
            severity=Severity.HIGH,
            camera_id="cam_002",
            frame_id="cam_002_1737385980123456",
            timestamp=datetime.utcnow().isoformat() + "Z",
            confidence=0.85,
            bbox=[50, 100, 200, 250],
            model_type="fire",
            correlation_age_ms=120.5
        ),
    ]


def _generate_sample_alerts():
    """Generate sample alerts for demonstration."""
    return [
        Alert(
            alert_id="alt_001",
            event_id="evt_001",
            event_type=EventType.WEAPON_DETECTED,
            severity=Severity.CRITICAL,
            camera_id="cam_001",
            timestamp=datetime.utcnow().isoformat() + "Z",
            message="CRITICAL: Weapon detected on Camera 001",
            acknowledged=False
        ),
    ]


@router.get("/events", response_model=EventListResponse)
async def list_events(
    limit: int = Query(default=50, ge=1, le=100, description="Max events to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    camera_id: Optional[str] = Query(default=None, description="Filter by camera"),
    event_type: Optional[EventType] = Query(default=None, description="Filter by event type"),
    severity: Optional[Severity] = Query(default=None, description="Filter by severity")
) -> EventListResponse:
    """
    List classified events.
    
    Returns events from the event store with optional filtering.
    Read-only endpoint - does not modify data.
    
    In production, this reads from the database.
    Currently returns sample data for demonstration.
    """
    # Get or generate sample events
    events = _generate_sample_events()
    
    # Apply filters
    if camera_id:
        events = [e for e in events if e.camera_id == camera_id]
    if event_type:
        events = [e for e in events if e.event_type == event_type]
    if severity:
        events = [e for e in events if e.severity == severity]
    
    # Apply pagination
    total = len(events)
    events = events[offset:offset + limit]
    
    return EventListResponse(
        total=total,
        limit=limit,
        offset=offset,
        events=events
    )


@router.get("/events/{event_id}", response_model=Event)
async def get_event(
    event_id: str = Path(..., description="Event ID")
) -> Event:
    """
    Get a specific event by ID.
    """
    events = _generate_sample_events()
    
    for event in events:
        if event.event_id == event_id:
            return event
    
    raise HTTPException(
        status_code=404,
        detail=f"Event {event_id} not found"
    )


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=100, description="Max alerts to return"),
    unacknowledged_only: bool = Query(default=False, description="Only show unacknowledged")
) -> AlertListResponse:
    """
    List alerts.
    
    Returns alerts with optional filtering for unacknowledged only.
    Read-only endpoint - does not modify data.
    """
    alerts = _generate_sample_alerts()
    
    # Apply filter
    if unacknowledged_only:
        alerts = [a for a in alerts if not a.acknowledged]
    
    unacknowledged = sum(1 for a in alerts if not a.acknowledged)
    
    return AlertListResponse(
        total=len(alerts),
        unacknowledged=unacknowledged,
        alerts=alerts[:limit]
    )


@router.get("/alerts/{alert_id}", response_model=Alert)
async def get_alert(
    alert_id: str = Path(..., description="Alert ID")
) -> Alert:
    """
    Get a specific alert by ID.
    """
    alerts = _generate_sample_alerts()
    
    for alert in alerts:
        if alert.alert_id == alert_id:
            return alert
    
    raise HTTPException(
        status_code=404,
        detail=f"Alert {alert_id} not found"
    )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str = Path(..., description="Alert ID"),
    acknowledged_by: str = Query(..., description="User acknowledging the alert")
) -> dict:
    """
    Acknowledge an alert.
    
    Marks an alert as acknowledged by a user.
    In production, this would update the database.
    """
    logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
    
    return {
        "success": True,
        "message": f"Alert {alert_id} acknowledged by {acknowledged_by}",
        "alert_id": alert_id,
        "acknowledged_by": acknowledged_by,
        "acknowledged_at": datetime.utcnow().isoformat() + "Z"
    }
