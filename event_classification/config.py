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
        default=True,
        description="On restart: True = start from latest, False = resume from last ID"
    )
    
    # Frame buffer configuration
    correlation_window_ms: int = Field(
        default=400,
        ge=300,
        le=500,
        description="Correlation window for multi-model results (300-500ms)"
    )
    hard_ttl_seconds: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Hard TTL for frames (absolute max)"
    )
    
    # Classification thresholds
    weapon_confidence_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Min confidence for weapon detection (immediate classification)"
    )
    fire_confidence_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Min confidence for fire detection"
    )
    fire_min_frames: int = Field(
        default=2,
        ge=1,
        description="Min frames required for fire persistence"
    )
    fall_confidence_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Min confidence for fall detection"
    )
    
    # Output configuration (all outputs are async, non-blocking)
    enable_alerts: bool = Field(default=True, description="Enable alert dispatching")
    alert_webhook_url: Optional[str] = Field(
        default=None, 
        description="Webhook URL for alerts (None = log only)"
    )
    alert_timeout_sec: float = Field(default=5.0, ge=1.0, le=30.0, description="Webhook timeout")
    
    enable_database: bool = Field(default=True, description="Enable database writing")
    database_path: str = Field(default="./events.db", description="SQLite database path")
    database_batch_size: int = Field(default=10, ge=1, le=100, description="Events per batch write")
    
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
