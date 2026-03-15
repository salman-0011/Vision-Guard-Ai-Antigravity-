"""
VisionGuard AI - Events & Alerts API Routes

Read-only endpoints for classified events and alerts.
GET /events - Query events from database
GET /events/{id} - Get single event by UUID
GET /alerts - List alerts from database
GET /alerts/{id} - Get single alert with event metadata
"""

import sys
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.models.events import (
    DBEvent, DBEventListResponse,
    DBAlert, DBAlertListResponse
)
from app.services.db_reader import get_db_reader
from app.utils.logging import get_logger
from alerts.repository import AlertRepository
from alerts.config import AlertConfig

router = APIRouter(tags=["Events & Alerts"])
logger = get_logger(__name__)

_alert_repo = None

def get_alert_repo() -> AlertRepository:
    global _alert_repo
    if _alert_repo is None:
        _alert_repo = AlertRepository(AlertConfig())
    return _alert_repo


@router.get("/events", response_model=DBEventListResponse)
async def list_events(
    limit: int = Query(default=50, ge=1, le=100, description="Max events to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    camera_id: Optional[str] = Query(default=None, description="Filter by camera"),
    event_type: Optional[str] = Query(default=None, description="Filter by event type"),
    severity: Optional[str] = Query(default=None, description="Filter by severity")
) -> DBEventListResponse:
    reader = get_db_reader()
    
    result = reader.list_events(
        limit=limit,
        offset=offset,
        camera_id=camera_id,
        event_type=event_type,
        severity=severity
    )
    
    events = [DBEvent(**e) for e in result["events"]]
    
    return DBEventListResponse(
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        events=events
    )


@router.get("/events/stats", response_model=dict)
async def get_event_stats() -> dict:
    reader = get_db_reader()
    return reader.get_stats()


@router.get("/events/{event_id}", response_model=DBEvent)
async def get_event(
    event_id: str = Path(..., description="Event UUID")
) -> DBEvent:
    reader = get_db_reader()
    
    event = reader.get_event(event_id)
    
    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Event {event_id} not found"
        )
    
    return DBEvent(**event)


@router.get("/alerts", response_model=DBAlertListResponse)
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=100, description="Max alerts to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    camera_id: Optional[str] = Query(default=None, description="Filter by camera")
) -> DBAlertListResponse:
    repo = get_alert_repo()
    
    result = repo.list_alerts(
        limit=limit,
        offset=offset,
        status=status,
        severity=severity,
        camera_id=camera_id
    )
    
    alerts = [DBAlert(**a) for a in result["alerts"]]
    
    return DBAlertListResponse(
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        alerts=alerts
    )


@router.get("/alerts/{alert_id}", response_model=DBAlert)
async def get_alert(
    alert_id: str = Path(..., description="Alert UUID")
) -> DBAlert:
    repo = get_alert_repo()
    
    alert = repo.get_alert_with_event(alert_id)
    
    if alert is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alert {alert_id} not found"
        )
    
    return DBAlert(**alert)
