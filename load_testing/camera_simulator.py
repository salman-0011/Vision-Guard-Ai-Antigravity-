"""
VisionGuard AI - Camera Simulator

Simulates camera frame generation for load testing.
Does NOT require real RTSP streams - generates synthetic frames.
"""

import time
import random
import numpy as np
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from multiprocessing import Process, Event
import logging
import redis

logger = logging.getLogger(__name__)


@dataclass
class SimulatorConfig:
    """Configuration for camera simulator."""
    camera_id: str
    fps: float = 5.0
    width: int = 640
    height: int = 480
    motion_probability: float = 0.3  # 30% of frames have motion
    burst_mode: bool = False
    burst_multiplier: float = 10.0
    burst_duration_sec: float = 5.0


class CameraSimulator:
    """
    Simulates a camera for load testing.
    
    Generates fake frames and pushes to Redis,
    without touching shared memory (pure load test).
    
    This allows testing:
    - Redis queue throughput
    - ECS processing capacity
    - System stability under load
    """
    
    def __init__(
        self,
        config: SimulatorConfig,
        redis_host: str = "localhost",
        redis_port: int = 6379
    ):
        self.config = config
        self.redis_host = redis_host
        self.redis_port = redis_port
        
        # Process control
        self.process: Optional[Process] = None
        self.stop_event = Event()
        
        # Statistics
        self.frames_generated = 0
        self.frames_with_motion = 0
        self.errors = 0
    
    def start(self) -> bool:
        """Start simulator process."""
        self.stop_event.clear()
        self.process = Process(
            target=self._run,
            name=f"CameraSimulator-{self.config.camera_id}",
            daemon=False
        )
        self.process.start()
        return self.process.is_alive()
    
    def stop(self, timeout: float = 5.0) -> None:
        """Stop simulator process."""
        if not self.process:
            return
        
        self.stop_event.set()
        self.process.join(timeout=timeout)
        
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=1.0)
    
    def is_alive(self) -> bool:
        """Check if simulator is running."""
        return self.process is not None and self.process.is_alive()
    
    def _run(self) -> None:
        """Main simulator loop (runs in subprocess)."""
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(f"simulator.{self.config.camera_id}")
        
        try:
            # Connect to Redis
            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True
            )
            client.ping()
            logger.info(f"Simulator {self.config.camera_id} connected to Redis")
            
            frame_interval = 1.0 / self.config.fps
            frame_count = 0
            burst_start = None
            
            while not self.stop_event.is_set():
                loop_start = time.time()
                
                # Handle burst mode
                current_fps = self.config.fps
                if self.config.burst_mode:
                    if burst_start is None:
                        burst_start = time.time()
                    
                    if time.time() - burst_start < self.config.burst_duration_sec:
                        current_fps = self.config.fps * self.config.burst_multiplier
                    else:
                        # Burst ended, back to normal
                        current_fps = self.config.fps
                
                frame_interval = 1.0 / current_fps
                
                # Simulate motion detection
                has_motion = random.random() < self.config.motion_probability
                
                if has_motion:
                    # Generate frame metadata (no actual frame data in pure load test)
                    frame_id = f"{self.config.camera_id}_{int(time.time() * 1000000)}"
                    
                    task_msg = {
                        "camera_id": self.config.camera_id,
                        "frame_id": frame_id,
                        "shared_memory_key": f"sim_{frame_id}",  # Fake key
                        "timestamp": str(time.time()),
                        "width": str(self.config.width),
                        "height": str(self.config.height),
                        "simulated": "true"
                    }
                    
                    try:
                        # Push to Redis queue (medium priority)
                        client.lpush("vg:medium", str(task_msg))
                        self.frames_with_motion += 1
                    except Exception as e:
                        logger.error(f"Redis push failed: {e}")
                        self.errors += 1
                
                frame_count += 1
                self.frames_generated = frame_count
                
                # Log progress every 100 frames
                if frame_count % 100 == 0:
                    logger.info(
                        f"Simulator {self.config.camera_id}: "
                        f"{frame_count} frames, {self.frames_with_motion} with motion"
                    )
                
                # Maintain frame rate
                elapsed = time.time() - loop_start
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except Exception as e:
            logger.error(f"Simulator {self.config.camera_id} error: {e}")
            self.errors += 1
        finally:
            logger.info(f"Simulator {self.config.camera_id} stopped")


class MultiCameraSimulator:
    """
    Manages multiple camera simulators for load testing.
    """
    
    def __init__(
        self,
        num_cameras: int = 3,
        base_fps: float = 5.0,
        motion_probability: float = 0.3,
        redis_host: str = "localhost",
        redis_port: int = 6379
    ):
        self.num_cameras = num_cameras
        self.base_fps = base_fps
        self.motion_probability = motion_probability
        self.redis_host = redis_host
        self.redis_port = redis_port
        
        self.simulators: Dict[str, CameraSimulator] = {}
    
    def start_all(self) -> int:
        """Start all simulators. Returns number started."""
        started = 0
        for i in range(self.num_cameras):
            camera_id = f"sim_cam_{i:03d}"
            config = SimulatorConfig(
                camera_id=camera_id,
                fps=self.base_fps,
                motion_probability=self.motion_probability
            )
            
            sim = CameraSimulator(
                config=config,
                redis_host=self.redis_host,
                redis_port=self.redis_port
            )
            
            if sim.start():
                self.simulators[camera_id] = sim
                started += 1
                logger.info(f"Started simulator: {camera_id}")
            else:
                logger.error(f"Failed to start simulator: {camera_id}")
        
        return started
    
    def stop_all(self) -> None:
        """Stop all simulators."""
        for camera_id, sim in self.simulators.items():
            logger.info(f"Stopping simulator: {camera_id}")
            sim.stop()
        self.simulators.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get stats from all simulators."""
        return {
            "total": len(self.simulators),
            "running": sum(1 for s in self.simulators.values() if s.is_alive())
        }
    
    def enable_burst_mode(self, duration_sec: float = 5.0) -> None:
        """Enable burst mode on all simulators."""
        for sim in self.simulators.values():
            sim.config.burst_mode = True
            sim.config.burst_duration_sec = duration_sec
    
    def disable_burst_mode(self) -> None:
        """Disable burst mode on all simulators."""
        for sim in self.simulators.values():
            sim.config.burst_mode = False
