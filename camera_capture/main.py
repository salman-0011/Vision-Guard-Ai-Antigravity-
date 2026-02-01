"""
VisionGuard AI - Camera Capture Entry Point

Standalone entry point for Docker container.
"""

import sys
import os
import signal
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camera_capture import start_cameras, stop_cameras, CaptureConfig

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for camera capture service."""
    logger.info("Starting Camera Capture Service...")
    
    # Load config from environment
    config = CaptureConfig(
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
    )
    
    # Load camera config file
    config_path = os.getenv("CAMERA_CONFIG_PATH", "/app/cameras.json")
    
    # Setup signal handlers
    def shutdown(signum, frame):
        logger.info("Received shutdown signal, stopping cameras...")
        stop_cameras()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    try:
        # Start cameras
        start_cameras(config)
        
        # Keep running
        logger.info("Camera Capture Service running. Press Ctrl+C to stop.")
        signal.pause()
        
    except Exception as e:
        logger.error(f"Camera Capture failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
