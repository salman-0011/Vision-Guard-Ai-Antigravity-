"""
VisionGuard AI - Event Classification Service Configuration

Type-safe configuration for single-instance ECS.
"""

from typing import Optional
from pydantic import BaseModel, Field, validator


class ECSConfig(BaseModel):
    """
    Configuration for Event Classification Service.
    
    ECS is a single-instance, CPU-only, deterministic classification brain.
    """
    
    # Redis configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    redis_db: int = Field(default=0, ge=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password (optional)")
    
    # Stream configuration
    input_stream: str = Field(
        default="vg:ai:results",
        description="Redis stream to consume AI results from"
    )
    read_block_ms: int = Field(
        default=1000,
        ge=100,
        description="XREAD block timeout in milliseconds"
    )
    read_count: int = Field(
        default=100,
        ge=1,
        description="Max messages to read per XREAD call"
    )
    resume_from_latest: bool = Field(
        default=False,
        description="On restart: True = start from latest, False = resume from last ID"
    )
    
    # Frame buffer configuration (v2: widened for real inference latency)
    correlation_window_ms: int = Field(
        default=2000,
        ge=300,
        le=10000,
        description="Correlation window for multi-model results (v2: 2000ms for 3-6s latency)"
    )
    hard_ttl_seconds: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        description="Hard TTL for frames (v2: 15s to survive p95 inference)"
    )
    
    # Classification thresholds (tuned for actual model output range: 0.33-0.59 normalized)
    weapon_confidence_threshold: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Min confidence for weapon detection (immediate classification)"
    )
    fire_confidence_threshold: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Min confidence for fire detection"
    )
    fire_min_detections: int = Field(
        default=3,
        ge=1,
        description="Min fire detections in persistence window (v2: camera-level)"
    )
    fire_persistence_window_sec: float = Field(
        default=8.0,
        ge=1.0,
        le=60.0,
        description="Sliding window for fire persistence (seconds)"
    )
    fall_confidence_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Min confidence for fall detection"
    )
    
    # V2: Camera history
    camera_history_window_sec: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="How long to keep camera detection history"
    )
    
    # V2: Event cooldown (deduplication)
    weapon_cooldown_seconds: float = Field(
        default=30.0,
        ge=0.0,
        le=300.0,
        description="Suppress duplicate weapon events for this duration"
    )
    fire_cooldown_seconds: float = Field(
        default=60.0,
        ge=0.0,
        le=300.0,
        description="Suppress duplicate fire events for this duration"
    )
    fall_cooldown_seconds: float = Field(
        default=30.0,
        ge=0.0,
        le=300.0,
        description="Suppress duplicate fall events for this duration"
    )
    
    # Output configuration (all outputs are async, non-blocking)
    enable_alerts: bool = Field(default=True, description="Enable alert dispatching")
    alert_webhook_url: Optional[str] = Field(
        default=None, 
        description="Webhook URL for alerts (None = log only)"
    )
    alert_timeout_sec: float = Field(default=5.0, ge=1.0, le=30.0, description="Webhook timeout")
    
    enable_database: bool = Field(default=True, description="Enable database writing")
    database_path: str = Field(
        default=None,
        description="SQLite database path (defaults to VG_DB_PATH env or /data/visionguard/events.db)"
    )
    database_batch_size: int = Field(default=10, ge=1, le=100, description="Events per batch write")
    model_version: str = Field(default="1.0.0", description="Model version for DB records")
    
    enable_frontend: bool = Field(default=True, description="Enable frontend publishing")
    frontend_queue_size: int = Field(default=1000, ge=100, le=10000, description="Max events in frontend queue")
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format (json/text)")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @validator('log_format')
    def validate_log_format(cls, v):
        if v not in ['json', 'text']:
            raise ValueError('log_format must be "json" or "text"')
        return v
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        extra = 'forbid'
