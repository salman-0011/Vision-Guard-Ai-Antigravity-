"""
VisionGuard AI - Load Test Scenarios

Pre-defined test scenarios for system validation.
Each scenario tests specific system behaviors.
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class ScenarioType(str, Enum):
    """Types of load test scenarios."""
    NORMAL = "normal"           # Baseline stability
    BURST = "burst"             # Sudden load spike
    SLOW_CONSUMER = "slow"      # Simulated slow AI workers
    REDIS_FAILURE = "redis"     # Redis interruption recovery


@dataclass
class ScenarioConfig:
    """Configuration for a test scenario."""
    name: str
    scenario_type: ScenarioType
    description: str
    
    # Camera configuration
    num_cameras: int
    base_fps: float
    motion_probability: float
    
    # Duration
    duration_seconds: int
    warmup_seconds: int = 10
    
    # Burst settings (for BURST scenario)
    burst_start_sec: int = 30
    burst_duration_sec: int = 10
    burst_multiplier: float = 10.0
    
    # Thresholds for pass/fail
    max_queue_size: int = 1000
    min_redis_uptime_pct: float = 95.0


# Pre-defined scenarios
SCENARIO_NORMAL = ScenarioConfig(
    name="Normal Load",
    scenario_type=ScenarioType.NORMAL,
    description="Baseline stability test with moderate load",
    num_cameras=5,
    base_fps=5.0,
    motion_probability=0.3,
    duration_seconds=300,  # 5 minutes
    warmup_seconds=10,
    max_queue_size=500,
    min_redis_uptime_pct=99.0
)

SCENARIO_BURST = ScenarioConfig(
    name="Burst Storm",
    scenario_type=ScenarioType.BURST,
    description="Sudden 10x frame rate spike to test TTL eviction",
    num_cameras=3,
    base_fps=5.0,
    motion_probability=0.5,
    duration_seconds=120,  # 2 minutes
    warmup_seconds=10,
    burst_start_sec=30,
    burst_duration_sec=10,
    burst_multiplier=10.0,
    max_queue_size=2000,
    min_redis_uptime_pct=95.0
)

SCENARIO_SLOW_CONSUMER = ScenarioConfig(
    name="Slow AI Workers",
    scenario_type=ScenarioType.SLOW_CONSUMER,
    description="Simulates backpressure from slow AI processing",
    num_cameras=3,
    base_fps=5.0,
    motion_probability=0.4,
    duration_seconds=180,  # 3 minutes
    warmup_seconds=10,
    max_queue_size=1500,
    min_redis_uptime_pct=98.0
)

SCENARIO_REDIS_FAILURE = ScenarioConfig(
    name="Redis Interruption",
    scenario_type=ScenarioType.REDIS_FAILURE,
    description="Tests recovery from temporary Redis unavailability",
    num_cameras=3,
    base_fps=5.0,
    motion_probability=0.3,
    duration_seconds=120,  # 2 minutes
    warmup_seconds=10,
    max_queue_size=500,
    min_redis_uptime_pct=80.0  # Lower due to intentional interruption
)


ALL_SCENARIOS = [
    SCENARIO_NORMAL,
    SCENARIO_BURST,
    SCENARIO_SLOW_CONSUMER,
    SCENARIO_REDIS_FAILURE
]


def get_scenario(name: str) -> Optional[ScenarioConfig]:
    """Get scenario by name."""
    for s in ALL_SCENARIOS:
        if s.name.lower() == name.lower() or s.scenario_type.value == name.lower():
            return s
    return None


def list_scenarios() -> List[str]:
    """List all available scenario names."""
    return [s.name for s in ALL_SCENARIOS]
