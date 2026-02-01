"""
VisionGuard AI - Debug UI Configuration

Environment-based configuration for Streamlit debug interface.
READ-ONLY access, no ECS coupling.
"""

import os
from dataclasses import dataclass


@dataclass
class UIConfig:
    """Configuration for Debug UI."""
    
    # Redis connection (READ-ONLY)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    # Stream settings
    stream_name: str = "vg:ai:results"
    read_count: int = 50
    read_block_ms: int = 500
    
    # UI settings
    refresh_interval_sec: float = 1.5
    max_cached_events: int = 100
    max_cached_frames: int = 50
    
    # Display
    page_title: str = "VisionGuard AI - Debug UI"
    page_icon: str = "🛡️"
    
    @classmethod
    def from_env(cls) -> "UIConfig":
        """Load configuration from environment variables."""
        return cls(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            redis_password=os.getenv("REDIS_PASSWORD", ""),
            stream_name=os.getenv("VG_STREAM_NAME", "vg:ai:results"),
            read_count=int(os.getenv("VG_READ_COUNT", "50")),
            read_block_ms=int(os.getenv("VG_READ_BLOCK_MS", "500")),
            refresh_interval_sec=float(os.getenv("VG_REFRESH_SEC", "1.5")),
            max_cached_events=int(os.getenv("VG_MAX_EVENTS", "100")),
            max_cached_frames=int(os.getenv("VG_MAX_FRAMES", "50")),
        )


# Global config instance
config = UIConfig.from_env()
