"""
VisionGuard AI - Full Pipeline Test with Test Video

Runs the complete pipeline locally:
1. Reads test video
2. Simulates motion detection
3. Pushes frames to Redis queue
4. Simulates AI inference results
5. Publishes to vg:ai:results stream (for Debug UI)

This allows testing the Debug UI with realistic data from the test video.

Usage:
    python scripts/run_pipeline_test.py
"""

import cv2
import redis
import time
import json
import base64
import random
import os
import sys
import signal
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("pipeline_test")


class VideoPipelineSimulator:
    """
    Simulates the full VisionGuard AI pipeline using test video.
    
    Reads frames from video, simulates AI detection, 
    and publishes results to Redis stream for Debug UI.
    """
    
    def __init__(self, video_path: str, redis_host: str = "localhost", redis_port: int = 6379):
        self.video_path = video_path
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.running = False
        self.frame_count = 0
        
        # Detection simulation parameters
        self.event_types = ["weapon", "fire", "person", "fall"]
        self.event_weights = [0.15, 0.10, 0.60, 0.15]  # Person most common
        
    def start(self, fps: float = 5.0, detection_chance: float = 0.3):
        """
        Start the pipeline simulation.
        
        Args:
            fps: Frames per second to process
            detection_chance: Probability of "detecting" something per frame
        """
        if not os.path.exists(self.video_path):
            logger.error(f"Video not found: {self.video_path}")
            return
        
        # Test Redis connection
        try:
            self.redis_client.ping()
            logger.info("✅ Redis connected")
        except redis.ConnectionError:
            logger.error("❌ Redis not available!")
            return
        
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            logger.error("Failed to open video")
            return
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"📹 Video loaded: {total_frames} frames @ {video_fps} FPS")
        logger.info(f"🚀 Starting pipeline simulation at {fps} FPS...")
        logger.info(f"   Detection chance: {detection_chance*100:.0f}%")
        logger.info("   Events will appear in Debug UI (http://localhost:8501)")
        logger.info("")
        logger.info("Press Ctrl+C to stop")
        
        self.running = True
        frame_delay = 1.0 / fps
        events_published = 0
        
        try:
            while self.running:
                ret, frame = cap.read()
                
                if not ret:
                    # Loop video
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                self.frame_count += 1
                
                # Simulate detection
                if random.random() < detection_chance:
                    # Simulate AI inference
                    event = self._simulate_detection(frame)
                    
                    # Publish to Redis stream
                    self._publish_event(event)
                    events_published += 1
                    
                    # Log detections
                    logger.info(
                        f"🎯 Event {events_published}: {event['event_type']} "
                        f"({event['confidence']:.1%}) - cam_{event['camera_id']}"
                    )
                
                # Rate limit
                time.sleep(frame_delay)
                
        except KeyboardInterrupt:
            logger.info("\nStopping pipeline...")
        finally:
            cap.release()
            self.running = False
            logger.info(f"✅ Pipeline stopped. {events_published} events published.")
    
    def _simulate_detection(self, frame) -> dict:
        """Simulate AI detection on a frame."""
        # Random event type
        event_type = random.choices(self.event_types, weights=self.event_weights)[0]
        
        # Priority based on type
        priorities = {
            "weapon": "CRITICAL",
            "fire": "CRITICAL", 
            "fall": "HIGH",
            "person": "MEDIUM"
        }
        
        # Confidence based on type
        if event_type in ["weapon", "fire"]:
            confidence = random.uniform(0.85, 0.98)
        else:
            confidence = random.uniform(0.70, 0.95)
        
        # Simulate bounding box
        h, w = frame.shape[:2]
        x1 = random.randint(50, w // 2)
        y1 = random.randint(50, h // 2)
        x2 = x1 + random.randint(100, 200)
        y2 = y1 + random.randint(100, 200)
        bbox = [x1, y1, x2, y2]
        
        # Encode frame thumbnail as base64
        thumbnail = cv2.resize(frame, (320, 180))
        _, buffer = cv2.imencode('.jpg', thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "camera_id": f"test_{random.randint(1, 3):02d}",
            "frame_id": f"frame_{self.frame_count}",
            "event_type": event_type,
            "priority": priorities.get(event_type, "MEDIUM"),
            "confidence": confidence,
            "bbox": json.dumps(bbox),
            "timestamp": str(time.time()),
            "inference_latency_ms": random.uniform(20, 80),
            "model_type": event_type,
            "frame": frame_base64
        }
    
    def _publish_event(self, event: dict):
        """Publish event to Redis stream."""
        try:
            # Convert all values to strings for Redis
            event_str = {k: str(v) if not isinstance(v, str) else v for k, v in event.items()}
            self.redis_client.xadd("vg:ai:results", event_str, maxlen=1000)
        except Exception as e:
            logger.error(f"Failed to publish: {e}")
    
    def stop(self):
        """Stop the pipeline."""
        self.running = False


def main():
    # Find video file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    video_path = os.path.join(project_root, "test-video.mp4")
    
    if not os.path.exists(video_path):
        video_path = "test-video.mp4"
    
    if not os.path.exists(video_path):
        logger.error("test-video.mp4 not found!")
        sys.exit(1)
    
    # Create and run simulator
    simulator = VideoPipelineSimulator(video_path)
    
    # Handle signals
    def shutdown(sig, frame):
        simulator.stop()
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # Run pipeline
    simulator.start(fps=5.0, detection_chance=0.2)


if __name__ == "__main__":
    main()
