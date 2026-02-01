"""
VisionGuard AI - Database Writer

Production SQLite-based event persistence.
Async batched writes, non-blocking.
"""

import logging
import sqlite3
import threading
import queue
import json
import os
from typing import Optional, List
from datetime import datetime

from ..classification.event_models import Event


class DatabaseWriter:
    """
    Production database writer for classified events.
    
    Features:
    - SQLite for lightweight persistence
    - Async writes via background thread
    - Batched inserts for efficiency
    - Failure never blocks ECS
    - Config-driven enable/disable
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        camera_id TEXT NOT NULL,
        frame_id TEXT,
        timestamp TEXT NOT NULL,
        confidence REAL,
        model_type TEXT,
        bbox TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);
    CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
    CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
    """
    
    def __init__(
        self,
        enabled: bool = True,
        db_path: str = "./events.db",
        batch_size: int = 10,
        flush_interval_sec: float = 5.0,
        max_queue_size: int = 5000
    ):
        """
        Initialize database writer.
        
        Args:
            enabled: Whether writing is enabled
            db_path: Path to SQLite database file
            batch_size: Number of events to batch before writing
            flush_interval_sec: Max time before forcing a write
            max_queue_size: Max pending events before dropping
        """
        self.logger = logging.getLogger(__name__)
        self.enabled = enabled
        self.db_path = db_path
        self.batch_size = batch_size
        self.flush_interval = flush_interval_sec
        
        # Write queue
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Statistics
        self.events_written = 0
        self.events_dropped = 0
        self.write_failures = 0
        self.batches_written = 0
        
        if self.enabled:
            self._init_db()
            self._start_worker()
        
        self.logger.info(
            f"Database writer initialized",
            extra={"enabled": enabled, "db_path": db_path}
        )
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            conn = sqlite3.connect(self.db_path)
            conn.executescript(self.SCHEMA)
            conn.close()
            self.logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Database init failed: {e}")
    
    def _start_worker(self) -> None:
        """Start background write worker."""
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="DatabaseWriterWorker",
            daemon=True
        )
        self._thread.start()
    
    def _worker_loop(self) -> None:
        """Background worker that batches and writes events."""
        batch: List[Event] = []
        last_flush = datetime.now()
        
        while self._running:
            try:
                # Get event with timeout
                try:
                    event = self._queue.get(timeout=0.5)
                    batch.append(event)
                    self._queue.task_done()
                except queue.Empty:
                    pass
                
                # Check if we should flush
                elapsed = (datetime.now() - last_flush).total_seconds()
                should_flush = (
                    len(batch) >= self.batch_size or
                    (len(batch) > 0 and elapsed >= self.flush_interval)
                )
                
                if should_flush:
                    self._write_batch(batch)
                    batch = []
                    last_flush = datetime.now()
                    
            except Exception as e:
                self.logger.error(f"Worker error: {e}")
        
        # Final flush on shutdown
        if batch:
            self._write_batch(batch)
    
    def _write_batch(self, batch: List[Event]) -> None:
        """Write a batch of events to database."""
        if not batch:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for event in batch:
                try:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO events 
                        (event_id, event_type, severity, camera_id, frame_id,
                         timestamp, confidence, model_type, bbox, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event.event_id,
                            event.event_type,
                            event.severity,
                            event.camera_id,
                            getattr(event, 'frame_id', None),
                            event.timestamp,
                            event.confidence,
                            event.model_type,
                            json.dumps(getattr(event, 'bbox', None)),
                            datetime.utcnow().isoformat() + "Z"
                        )
                    )
                    self.events_written += 1
                except sqlite3.Error as e:
                    self.write_failures += 1
                    self.logger.warning(
                        f"Event write failed: {e}",
                        extra={"event_id": event.event_id}
                    )
            
            conn.commit()
            conn.close()
            self.batches_written += 1
            
            self.logger.debug(
                f"Wrote batch of {len(batch)} events",
                extra={"batch_size": len(batch)}
            )
            
        except Exception as e:
            self.write_failures += len(batch)
            self.logger.error(f"Batch write failed: {e}")
    
    def write(self, event: Event) -> None:
        """
        Queue event for async database write.
        
        Non-blocking, fails independently.
        
        Args:
            event: Classified event
        """
        if not self.enabled:
            return
        
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self.events_dropped += 1
            self.logger.warning(
                f"Write queue full, dropping event",
                extra={"event_id": event.event_id}
            )
    
    def shutdown(self) -> None:
        """Gracefully stop the writer, flushing pending events."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self.logger.info("Database writer shutdown")
    
    def get_stats(self) -> dict:
        """Get writer statistics."""
        return {
            "enabled": self.enabled,
            "events_written": self.events_written,
            "events_dropped": self.events_dropped,
            "write_failures": self.write_failures,
            "batches_written": self.batches_written,
            "queue_size": self._queue.qsize()
        }
