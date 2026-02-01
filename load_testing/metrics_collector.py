"""
VisionGuard AI - Metrics Collector

Collects system metrics during load testing.
Monitors Redis, ECS, and overall system health.
"""

import time
import redis
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
import threading

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """Point-in-time system metrics."""
    timestamp: float
    
    # Redis metrics
    redis_connected: bool = False
    redis_queue_critical: int = 0
    redis_queue_high: int = 0
    redis_queue_medium: int = 0
    redis_stream_length: int = 0
    
    # Throughput metrics
    frames_per_second: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """
    Collects and aggregates system metrics during load tests.
    
    Runs in a background thread, sampling metrics at regular intervals.
    """
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        sample_interval_sec: float = 1.0
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.sample_interval = sample_interval_sec
        
        self._client: Optional[redis.Redis] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Metrics history
        self.snapshots: List[MetricsSnapshot] = []
        self.max_snapshots = 3600  # 1 hour at 1/sec
        
        # Running stats
        self._last_stream_length = 0
        self._last_sample_time = 0
    
    def start(self) -> bool:
        """Start metrics collection in background thread."""
        try:
            self._client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self._client.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
        
        self._running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
        
        logger.info("Metrics collector started")
        return True
    
    def stop(self) -> None:
        """Stop metrics collection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._client:
            self._client.close()
        logger.info("Metrics collector stopped")
    
    def _collection_loop(self) -> None:
        """Background collection loop."""
        while self._running:
            try:
                snapshot = self._collect_snapshot()
                self.snapshots.append(snapshot)
                
                # Trim history if too long
                if len(self.snapshots) > self.max_snapshots:
                    self.snapshots = self.snapshots[-self.max_snapshots:]
                    
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
            
            time.sleep(self.sample_interval)
    
    def _collect_snapshot(self) -> MetricsSnapshot:
        """Collect a single metrics snapshot."""
        now = time.time()
        snapshot = MetricsSnapshot(timestamp=now)
        
        try:
            # Check Redis connection
            self._client.ping()
            snapshot.redis_connected = True
            
            # Queue lengths
            snapshot.redis_queue_critical = self._client.llen("vg:critical")
            snapshot.redis_queue_high = self._client.llen("vg:high")
            snapshot.redis_queue_medium = self._client.llen("vg:medium")
            
            # Stream length
            try:
                snapshot.redis_stream_length = self._client.xlen("vg:ai:results")
            except:
                snapshot.redis_stream_length = 0
            
            # Calculate throughput
            if self._last_sample_time > 0:
                elapsed = now - self._last_sample_time
                stream_delta = snapshot.redis_stream_length - self._last_stream_length
                if elapsed > 0:
                    snapshot.frames_per_second = round(stream_delta / elapsed, 2)
            
            self._last_stream_length = snapshot.redis_stream_length
            self._last_sample_time = now
            
        except redis.ConnectionError:
            snapshot.redis_connected = False
        except Exception as e:
            logger.warning(f"Snapshot collection error: {e}")
        
        return snapshot
    
    def get_latest(self) -> Optional[MetricsSnapshot]:
        """Get most recent snapshot."""
        if self.snapshots:
            return self.snapshots[-1]
        return None
    
    def get_summary(self, last_n_seconds: int = 60) -> Dict[str, Any]:
        """
        Get aggregated summary of recent metrics.
        
        Args:
            last_n_seconds: Time window for aggregation
            
        Returns:
            Dictionary with min/max/avg statistics
        """
        cutoff = time.time() - last_n_seconds
        recent = [s for s in self.snapshots if s.timestamp >= cutoff]
        
        if not recent:
            return {"error": "No recent data"}
        
        return {
            "sample_count": len(recent),
            "time_window_sec": last_n_seconds,
            "redis_connected_pct": round(
                100 * sum(1 for s in recent if s.redis_connected) / len(recent), 1
            ),
            "queue_critical": {
                "min": min(s.redis_queue_critical for s in recent),
                "max": max(s.redis_queue_critical for s in recent),
                "avg": round(sum(s.redis_queue_critical for s in recent) / len(recent), 1)
            },
            "queue_high": {
                "min": min(s.redis_queue_high for s in recent),
                "max": max(s.redis_queue_high for s in recent),
                "avg": round(sum(s.redis_queue_high for s in recent) / len(recent), 1)
            },
            "queue_medium": {
                "min": min(s.redis_queue_medium for s in recent),
                "max": max(s.redis_queue_medium for s in recent),
                "avg": round(sum(s.redis_queue_medium for s in recent) / len(recent), 1)
            },
            "stream_length": {
                "min": min(s.redis_stream_length for s in recent),
                "max": max(s.redis_stream_length for s in recent),
                "final": recent[-1].redis_stream_length if recent else 0
            },
            "throughput_fps": {
                "min": min(s.frames_per_second for s in recent),
                "max": max(s.frames_per_second for s in recent),
                "avg": round(sum(s.frames_per_second for s in recent) / len(recent), 2)
            }
        }
    
    def check_stability(self, max_queue_growth: int = 1000) -> Dict[str, Any]:
        """
        Check if system is stable (queues not growing unbounded).
        
        Args:
            max_queue_growth: Maximum acceptable queue size
            
        Returns:
            Stability assessment
        """
        latest = self.get_latest()
        if not latest:
            return {"stable": False, "reason": "No metrics available"}
        
        total_queued = (
            latest.redis_queue_critical +
            latest.redis_queue_high +
            latest.redis_queue_medium
        )
        
        issues = []
        
        if not latest.redis_connected:
            issues.append("Redis disconnected")
        
        if total_queued > max_queue_growth:
            issues.append(f"Queue size {total_queued} exceeds threshold {max_queue_growth}")
        
        return {
            "stable": len(issues) == 0,
            "total_queued": total_queued,
            "stream_length": latest.redis_stream_length,
            "issues": issues
        }
