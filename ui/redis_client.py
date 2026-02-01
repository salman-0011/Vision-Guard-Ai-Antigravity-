"""
VisionGuard AI - Debug UI Redis Client

READ-ONLY Redis stream consumer.
Non-blocking, no ACK, observer mode only.
"""

import logging
import time
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
import redis

from .config import config

logger = logging.getLogger(__name__)


class RedisStreamReader:
    """
    Read-only Redis stream consumer for debug UI.
    
    Features:
    - Non-blocking XREAD
    - No stream ACK (pure observer)
    - Graceful disconnect handling
    - Connection health monitoring
    """
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._last_id = "$"  # Start from latest
        self._connected = False
        self._last_read_time: Optional[float] = None
        self._error_count = 0
    
    def connect(self) -> bool:
        """Establish connection to Redis."""
        try:
            self._client = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                password=config.redis_password or None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=2
            )
            self._client.ping()
            self._connected = True
            self._error_count = 0
            logger.info(f"Connected to Redis at {config.redis_host}:{config.redis_port}")
            return True
        except redis.ConnectionError as e:
            self._connected = False
            self._error_count += 1
            logger.warning(f"Redis connection failed: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if not self._client:
            return False
        try:
            self._client.ping()
            self._connected = True
            return True
        except:
            self._connected = False
            return False
    
    def read_events(self) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Read events from stream (non-blocking).
        
        Returns list of (event_id, event_data) tuples.
        Never acknowledges or deletes entries.
        """
        if not self._client or not self._connected:
            if not self.connect():
                return []
        
        try:
            # Non-blocking XREAD with short timeout
            result = self._client.xread(
                {config.stream_name: self._last_id},
                count=config.read_count,
                block=config.read_block_ms
            )
            
            self._last_read_time = time.time()
            
            if not result:
                return []
            
            events = []
            for stream_name, messages in result:
                for msg_id, data in messages:
                    events.append((msg_id, data))
                    self._last_id = msg_id  # Track position
            
            return events
            
        except redis.ConnectionError as e:
            self._connected = False
            self._error_count += 1
            logger.warning(f"Redis read error: {e}")
            return []
        except Exception as e:
            self._error_count += 1
            logger.error(f"Unexpected error reading stream: {e}")
            return []
    
    def get_stream_length(self) -> int:
        """Get approximate stream length."""
        if not self._client or not self._connected:
            return 0
        try:
            return self._client.xlen(config.stream_name)
        except:
            return 0
    
    def get_health(self) -> Dict[str, Any]:
        """Get reader health status."""
        return {
            "connected": self._connected,
            "last_read_time": self._last_read_time,
            "error_count": self._error_count,
            "stream_length": self.get_stream_length() if self._connected else 0,
            "last_id": self._last_id
        }
    
    def close(self) -> None:
        """Close connection gracefully."""
        if self._client:
            try:
                self._client.close()
            except:
                pass
            self._client = None
            self._connected = False


# Global reader instance (singleton for Streamlit)
_reader: Optional[RedisStreamReader] = None


def get_reader() -> RedisStreamReader:
    """Get or create the global reader instance."""
    global _reader
    if _reader is None:
        _reader = RedisStreamReader()
    return _reader
