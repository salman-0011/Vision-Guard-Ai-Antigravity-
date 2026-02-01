"""
VisionGuard AI - AI Worker Entry Point

Standalone entry point for Docker container.
"""

import sys
import os
import signal
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_worker import start_worker, stop_worker, WorkerConfig

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for AI worker."""
    logger.info("Starting AI Worker...")
    
    # Load config from environment
    config = WorkerConfig(
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        model_type=os.getenv("WORKER_MODEL_TYPE", "weapon"),
    )
    
    # Setup signal handlers
    def shutdown(signum, frame):
        logger.info("Received shutdown signal, stopping worker...")
        stop_worker()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    try:
        # Start worker
        start_worker(config)
        
        # Keep running
        logger.info(f"AI Worker ({config.model_type}) running. Press Ctrl+C to stop.")
        signal.pause()
        
    except Exception as e:
        logger.error(f"AI Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
