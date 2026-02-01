"""
VisionGuard AI - Event Classification Service

Single-instance, CPU-only, deterministic classification brain.
Sole authority for event classification, frame correlation, and shared memory cleanup.
"""

import logging
import time
from multiprocessing import Process, Event as ProcessEvent
from typing import Optional

from ..config import ECSConfig
from ..buffer.frame_buffer import FrameBuffer
from ..buffer.frame_state import AIResult
from ..classification.rule_engine import RuleEngine
from ..redis_client.stream_consumer import StreamConsumer
from ..cleanup.cleanup_manager import CleanupManager
from ..output.alert_dispatcher import AlertDispatcher
from ..output.database_writer import DatabaseWriter
from ..output.frontend_publisher import FrontendPublisher


class ECSService:
    """
    Event Classification Service (ECS).
    
    Single-instance, deterministic classification brain.
    
    Main loop:
    1. Consume AI results from Redis stream
    2. Add to frame buffer
    3. Check if ready for classification (correlation window or weapon short-circuit)
    4. Apply deterministic classification rules
    5. Dispatch outputs (async, non-blocking)
    6. Cleanup shared memory (AUTHORITATIVE)
    7. Remove from buffer
    8. Handle expired frames (TTL-based)
    """
    
    def __init__(self, config: ECSConfig):
        """
        Initialize ECS.
        
        Args:
            config: ECS configuration
        """
        self.config = config
        
        # Process control
        self.process: Optional[Process] = None
        self.stop_event = ProcessEvent()
        
        # Components (initialized in process)
        self.logger: Optional[logging.Logger] = None
        self.frame_buffer: Optional[FrameBuffer] = None
        self.rule_engine: Optional[RuleEngine] = None
        self.stream_consumer: Optional[StreamConsumer] = None
        self.cleanup_manager: Optional[CleanupManager] = None
        self.alert_dispatcher: Optional[AlertDispatcher] = None
        self.database_writer: Optional[DatabaseWriter] = None
        self.frontend_publisher: Optional[FrontendPublisher] = None
    
    def start(self) -> bool:
        """
        Start ECS process.
        
        Returns:
            True if process started successfully
        """
        self.stop_event.clear()
        
        self.process = Process(
            target=self._run,
            name="ECS-Service",
            daemon=False
        )
        self.process.start()
        
        return self.process.is_alive()
    
    def stop(self, timeout: float = 10.0) -> None:
        """
        Stop ECS process gracefully.
        
        Args:
            timeout: Maximum time to wait for process to stop
        """
        if not self.process:
            return
        
        # Signal process to stop
        self.stop_event.set()
        
        # Wait for process to finish
        self.process.join(timeout=timeout)
        
        # Force terminate if still alive
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=2.0)
        
        # Force kill if still alive
        if self.process.is_alive():
            self.process.kill()
            self.process.join()
    
    def is_alive(self) -> bool:
        """Check if process is alive."""
        return self.process is not None and self.process.is_alive()
    
    def _run(self) -> None:
        """
        Main process loop (runs in separate process).
        
        This is the entry point for the ECS process.
        """
        # Setup logging for this process
        self.logger = logging.getLogger("event_classification")
        self.logger.setLevel(getattr(logging, self.config.log_level))
        
        handler = logging.StreamHandler()
        if self.config.log_format == "json":
            # TODO: Use JSON formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        self.logger.info("ECS starting (SINGLE INSTANCE)")
        
        try:
            # Initialize components
            if not self._initialize():
                self.logger.error("Failed to initialize ECS")
                return
            
            # Main classification loop
            self._classification_loop()
            
        except Exception as e:
            self.logger.error(
                f"Fatal error in ECS: {e}",
                extra={"error": str(e)}
            )
        finally:
            # Cleanup
            self._shutdown()
    
    def _initialize(self) -> bool:
        """
        Initialize all components.
        
        Returns:
            True if initialization successful
        """
        try:
            # Initialize frame buffer
            self.frame_buffer = FrameBuffer()
            
            # Initialize rule engine
            self.rule_engine = RuleEngine(self.config)
            
            # Initialize Redis stream consumer
            self.stream_consumer = StreamConsumer(
                stream_name=self.config.input_stream,
                redis_host=self.config.redis_host,
                redis_port=self.config.redis_port,
                redis_db=self.config.redis_db,
                redis_password=self.config.redis_password,
                block_ms=self.config.read_block_ms,
                count=self.config.read_count
            )
            
            # REFINEMENT: Set start ID based on config
            if self.config.resume_from_latest:
                self.stream_consumer.set_start_id("$")  # Start from latest
            else:
                # TODO: Load last processed ID from persistent storage
                self.stream_consumer.set_start_id("$")
            
            # Initialize cleanup manager (AUTHORITATIVE)
            self.cleanup_manager = CleanupManager()
            
            # Initialize output dispatchers
            if self.config.enable_alerts:
                self.alert_dispatcher = AlertDispatcher()
            
            if self.config.enable_database:
                self.database_writer = DatabaseWriter()
            
            if self.config.enable_frontend:
                self.frontend_publisher = FrontendPublisher()
            
            self.logger.info("ECS initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(
                f"Initialization failed: {e}",
                extra={"error": str(e)}
            )
            return False
    
    def _classification_loop(self) -> None:
        """Main classification loop."""
        self.logger.info("Starting classification loop")
        
        while not self.stop_event.is_set():
            try:
                # 1. Consume messages from Redis stream
                messages = self.stream_consumer.consume()
                
                for msg in messages:
                    # 2. Add result to frame buffer
                    ai_result = AIResult(
                        model_type=msg.model_type,
                        confidence=msg.confidence,
                        timestamp=msg.timestamp,
                        bbox=msg.bbox
                    )
                    
                    frame_state = self.frame_buffer.add_result(
                        frame_id=msg.frame_id,
                        camera_id=msg.camera_id,
                        shared_memory_key=msg.shared_memory_key,
                        model_type=msg.model_type,
                        result=ai_result
                    )
                    
                    # 3. Check if ready for classification
                    # REFINEMENT: Weapon short-circuits correlation window
                    should_classify = False
                    
                    if self.rule_engine.should_classify_immediately(frame_state):
                        # Weapon detected - classify immediately
                        should_classify = True
                        self.logger.debug(
                            f"Weapon detected - immediate classification",
                            extra={"frame_id": msg.frame_id}
                        )
                    elif frame_state.get_age_ms() >= self.config.correlation_window_ms:
                        # Correlation window elapsed
                        should_classify = True
                        self.logger.debug(
                            f"Correlation window elapsed - classifying",
                            extra={
                                "frame_id": msg.frame_id,
                                "age_ms": frame_state.get_age_ms()
                            }
                        )
                    
                    if should_classify:
                        # 4. Classify
                        event = self.rule_engine.classify(frame_state)
                        
                        if event:
                            # 5. Dispatch outputs (async, non-blocking)
                            if self.alert_dispatcher:
                                self.alert_dispatcher.dispatch(event)
                            
                            if self.database_writer:
                                self.database_writer.write(event)
                            
                            if self.frontend_publisher:
                                self.frontend_publisher.publish(event)
                        
                        # 6. Cleanup shared memory (AUTHORITATIVE)
                        self.cleanup_manager.cleanup_frame(frame_state.shared_memory_key)
                        
                        # 7. Remove from buffer
                        self.frame_buffer.remove_frame(msg.frame_id)
                
                # 8. Handle expired frames
                expired_frames = self.frame_buffer.get_expired_frames(
                    self.config.hard_ttl_seconds
                )
                
                for frame_state in expired_frames:
                    self.logger.warning(
                        f"Frame expired (TTL)",
                        extra={
                            "frame_id": frame_state.frame_id,
                            "age_ms": frame_state.get_age_ms()
                        }
                    )
                    
                    # Cleanup even if not classified
                    self.cleanup_manager.cleanup_frame(frame_state.shared_memory_key)
                    
                    # Remove from buffer
                    self.frame_buffer.remove_frame(frame_state.frame_id)
                
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                self.logger.error(
                    f"Error in classification loop: {e}",
                    extra={"error": str(e)}
                )
                # Continue processing
                time.sleep(0.1)
        
        self.logger.info("Classification loop ended")
    
    def _shutdown(self) -> None:
        """Cleanup resources."""
        self.logger.info("Shutting down ECS")
        
        # Close Redis connection
        if self.stream_consumer:
            self.stream_consumer.close()
        
        # Log final statistics
        if self.frame_buffer:
            self.logger.info(
                "Frame buffer stats",
                extra=self.frame_buffer.get_stats()
            )
        
        if self.rule_engine:
            self.logger.info(
                "Rule engine stats",
                extra=self.rule_engine.get_stats()
            )
        
        if self.stream_consumer:
            self.logger.info(
                "Stream consumer stats",
                extra=self.stream_consumer.get_stats()
            )
        
        if self.cleanup_manager:
            self.logger.info(
                "Cleanup manager stats",
                extra=self.cleanup_manager.get_stats()
            )
        
        if self.alert_dispatcher:
            self.logger.info(
                "Alert dispatcher stats",
                extra=self.alert_dispatcher.get_stats()
            )
        
        if self.database_writer:
            self.logger.info(
                "Database writer stats",
                extra=self.database_writer.get_stats()
            )
        
        if self.frontend_publisher:
            self.logger.info(
                "Frontend publisher stats",
                extra=self.frontend_publisher.get_stats()
            )
        
        self.logger.info("ECS shutdown complete")
