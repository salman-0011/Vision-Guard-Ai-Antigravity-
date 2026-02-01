"""
VisionGuard AI - ECS Entry Point

Standalone entry point for Docker container.
SINGLETON - Only one instance allowed.
"""

import sys
import os
import signal
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_classification import start_ecs, stop_ecs, ECSConfig

logging.basicConfig(
    level=os.getenv("ECS_LOG_LEVEL", "INFO"),
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for ECS."""
    logger.info("Starting Event Classification Service (SINGLETON)...")
    
    # Load config from environment
    config = ECSConfig(
        redis_host=os.getenv("ECS_REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("ECS_REDIS_PORT", "6379")),
        database_path=os.getenv("ECS_DATABASE_PATH", "/data/events.db"),
    )
    
    # Setup signal handlers
    def shutdown(signum, frame):
        logger.info("Received shutdown signal, stopping ECS...")
        stop_ecs()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    try:
        # Start ECS
        start_ecs(config)
        
        # Keep running
        logger.info("ECS running. Press Ctrl+C to stop.")
        signal.pause()
        
    except Exception as e:
        logger.error(f"ECS failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
