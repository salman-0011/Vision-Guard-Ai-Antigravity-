"""
VisionGuard AI - Debug UI (Streamlit)

🛡️ READ-ONLY DEBUG INTERFACE

This is a TEMPORARY debug tool for observing VisionGuard AI.
- READ-ONLY access to Redis stream
- No writes, no ACKs, no modifications
- UI crash has ZERO impact on core services

Usage:
    streamlit run ui/app.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import time
import json
import urllib.request
import urllib.error
from datetime import datetime
from collections import deque
from typing import Dict, Any, Optional

from ui.config import config
from ui.redis_client import get_reader
from ui.event_parser import parse_event, format_metadata_json, ParsedEvent
from ui.image_renderer import render_event_frame, create_placeholder_image


# ============================================================
# Page Configuration
# ============================================================
st.set_page_config(
    page_title=config.page_title,
    page_icon=config.page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# Session State Initialization
# ============================================================
if "events" not in st.session_state:
    st.session_state.events = deque(maxlen=config.max_cached_events)
if "selected_event" not in st.session_state:
    st.session_state.selected_event = None
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
if "initial_load_done" not in st.session_state:
    st.session_state.initial_load_done = False


# ============================================================
# Custom CSS
# ============================================================
st.markdown("""
<style>
    /* Event timeline styling */
    .event-card {
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        cursor: pointer;
    }
    .event-critical { background-color: rgba(255, 68, 68, 0.2); border-left: 4px solid #FF4444; }
    .event-high { background-color: rgba(255, 136, 0, 0.2); border-left: 4px solid #FF8800; }
    .event-medium { background-color: rgba(255, 187, 0, 0.2); border-left: 4px solid #FFBB00; }
    .event-low { background-color: rgba(68, 170, 68, 0.2); border-left: 4px solid #44AA44; }
    
    /* Health indicator */
    .health-good { color: #44AA44; }
    .health-bad { color: #FF4444; }
    
    /* Compact metrics */
    .stMetric { padding: 5px !important; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Helper Functions
# ============================================================
def fetch_new_events():
    """Fetch new events from Redis stream."""
    reader = get_reader()
    raw_events = reader.read_events()
    
    for event_id, data in raw_events:
        parsed = parse_event(event_id, data)
        st.session_state.events.appendleft(parsed)
    
    st.session_state.last_refresh = time.time()
    return len(raw_events)


def get_health_status() -> Dict[str, Any]:
    """Get system health indicators."""
    reader = get_reader()
    health = reader.get_health()
    
    # Calculate time since last event
    if st.session_state.events:
        last_event_time = st.session_state.events[0].timestamp
    else:
        last_event_time = "No events"
    
    return {
        "redis_connected": health["connected"],
        "stream_length": health["stream_length"],
        "last_event": last_event_time,
        "events_cached": len(st.session_state.events),
        "last_refresh": datetime.fromtimestamp(st.session_state.last_refresh).strftime("%H:%M:%S")
    }


def get_db_event_count() -> Optional[int]:
    """Fetch total events count from backend DB stats endpoint."""
    base_url = config.backend_base_url.rstrip("/")
    url = f"{base_url}/events/stats"

    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.load(response)
        total = payload.get("total_events")
        return int(total) if total is not None else None
    except Exception:
        return None


def get_pipeline_metrics() -> Dict[str, Any]:
    """Get pipeline metrics for frame lifecycle tracking."""
    reader = get_reader()
    queue_lengths = reader.get_queue_lengths()
    total_queue = sum(queue_lengths.values())

    return {
        "task_queue": queue_lengths.get("vg:critical", 0),
        "queue_length": total_queue,
        "db_events": get_db_event_count()
    }


def render_event_row(event: ParsedEvent, index: int):
    """Render a single event row in the timeline."""
    priority_class = f"event-{event.priority.lower()}"
    
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1.5, 1.5])
    
    with col1:
        st.markdown(f"**{event.display_time}**")
    with col2:
        st.markdown(f"`{event.camera_id}`")
    with col3:
        st.markdown(f"**{event.event_type}**")
    with col4:
        color = event.severity_color
        st.markdown(f"<span style='color:{color};font-weight:bold'>{event.priority}</span>", 
                    unsafe_allow_html=True)
    with col5:
        st.markdown(f"{event.confidence:.1%}")
    
    return st.button("View", key=f"view_{index}_{event.event_id}", type="secondary")


# ============================================================
# Main Layout
# ============================================================
def main():
    # ========== INITIAL LOAD ==========
    # Fetch events on first page load
    if not st.session_state.initial_load_done:
        st.session_state.initial_load_done = True
        fetch_new_events()
    
    # Header
    st.title("🛡️ VisionGuard AI - Debug UI")
    st.caption("READ-ONLY • Temporary Debug Interface • Observes vg:ai:results stream")

    # Pipeline metrics
    st.subheader("📊 Pipeline Debug - Frame Flow")
    pipeline = get_pipeline_metrics()
    metric_cols = st.columns(4)
    metric_cols[0].metric("Task Queue", pipeline["task_queue"])
    metric_cols[1].metric("Queue Length", pipeline["queue_length"])
    metric_cols[2].metric("Cached Events", len(st.session_state.events))
    metric_cols[3].metric(
        "Events in DB",
        pipeline["db_events"] if pipeline["db_events"] is not None else "N/A"
    )
    
    # --------------------------------------------------------
    # Sidebar - Health & Controls
    # --------------------------------------------------------
    with st.sidebar:
        st.header("⚙️ System Health")
        st.caption("UI build: maintenance controls enabled")
        
        health = get_health_status()
        
        # Redis status
        if health["redis_connected"]:
            st.success("🟢 Redis Connected")
        else:
            st.error("🔴 Redis Disconnected")
        
        # Metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Stream Length", health["stream_length"])
        with col2:
            st.metric("Cached Events", health["events_cached"])
        
        st.caption(f"Last refresh: {health['last_refresh']}")
        
        st.divider()
        
        # Manual refresh
        if st.button("🔄 Refresh Now", use_container_width=True):
            count = fetch_new_events()
            st.toast(f"Fetched {count} new events")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        refresh_rate = st.slider("Refresh interval (sec)", 1.0, 5.0, config.refresh_interval_sec)

        st.divider()

        st.subheader("🧹 Maintenance")
        confirm_clear = st.checkbox("Confirm clear", value=False)
        if st.button("Clear stream + queues + UI cache", use_container_width=True):
            if not confirm_clear:
                st.warning("Enable 'Confirm clear' to proceed.")
            else:
                reader = get_reader()
                removed = reader.clear_stream_and_queues(
                    queues=["vg:critical", "vg:high", "vg:medium"]
                )
                st.session_state.events.clear()
                st.session_state.selected_event = None
                st.session_state.last_refresh = time.time()
                st.session_state.initial_load_done = True
                st.toast(f"Cleared {removed} Redis keys and UI cache")
        
        st.divider()
        st.caption("🔒 Observer mode")
        st.caption("Only the maintenance button clears Redis keys")
    
    # --------------------------------------------------------
    # Main Content - Two Column Layout
    # --------------------------------------------------------
    col_timeline, col_detail = st.columns([1, 1])
    
    # --------------------------------------------------------
    # Left Column - Event Timeline
    # --------------------------------------------------------
    with col_timeline:
        st.subheader("📋 Live Event Timeline")
        
        # Column headers
        header_cols = st.columns([2, 2, 2, 1.5, 1.5])
        with header_cols[0]:
            st.markdown("**Time**")
        with header_cols[1]:
            st.markdown("**Camera**")
        with header_cols[2]:
            st.markdown("**Event**")
        with header_cols[3]:
            st.markdown("**Priority**")
        with header_cols[4]:
            st.markdown("**Confidence**")
        
        st.divider()
        
        # Event list
        if not st.session_state.events:
            st.info("No events yet. Waiting for data from vg:ai:results stream...")
        else:
            for i, event in enumerate(list(st.session_state.events)[:50]):
                if render_event_row(event, i):
                    st.session_state.selected_event = event
    
    # --------------------------------------------------------
    # Right Column - Event Detail
    # --------------------------------------------------------
    with col_detail:
        st.subheader("🔍 Event Details")
        
        event = st.session_state.selected_event
        
        if event is None:
            st.info("Click 'View' on an event to see details")
        else:
            # Frame viewer
            st.markdown("**Frame Snapshot**")
            
            frame_img = render_event_frame(
                event.frame_data,
                event.bbox,
                event.event_type,
                event.confidence
            )
            
            if frame_img:
                st.image(frame_img, use_container_width=True)
            else:
                placeholder = create_placeholder_image(message="Frame Not Available")
                st.image(placeholder, use_container_width=True)
                st.caption("Frame data not included in stream message")
            
            st.divider()
            
            # Metadata
            st.markdown("**Event Metadata**")
            
            # Quick stats
            stat_cols = st.columns(3)
            with stat_cols[0]:
                st.metric("Confidence", f"{event.confidence:.1%}")
            with stat_cols[1]:
                st.metric("Latency", f"{event.inference_latency_ms:.0f}ms")
            with stat_cols[2]:
                st.metric("Model", event.model_type)
            
            # Full JSON
            with st.expander("📄 Full Metadata JSON", expanded=False):
                st.code(format_metadata_json(event), language="json")
            
            # Bounding box info
            if event.bbox:
                with st.expander("📦 Bounding Box", expanded=False):
                    st.json({"bbox": event.bbox})
    
    # --------------------------------------------------------
    # Auto-refresh Logic
    # --------------------------------------------------------
    if auto_refresh:
        time.sleep(refresh_rate)
        fetch_new_events()
        st.rerun()


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    main()
