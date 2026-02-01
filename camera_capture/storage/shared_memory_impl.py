"""
VisionGuard AI - Shared Memory Implementation

Concrete implementation using multiprocessing.shared_memory.
Thread-safe and multi-process safe.
"""

import numpy as np
from multiprocessing import shared_memory, Lock
from typing import Optional, Dict
import uuid
import struct
import logging
from .shared_memory_interface import SharedMemoryInterface


class SharedMemoryImpl(SharedMemoryInterface):
    """
    Shared memory implementation using multiprocessing.shared_memory.
    
    Frame format in shared memory:
    [4 bytes: height][4 bytes: width][4 bytes: channels][4 bytes: dtype][frame data]
    """
    
    def __init__(self, max_frame_size_mb: int = 10):
        """
        Initialize shared memory manager.
        
        Args:
            max_frame_size_mb: Maximum size per frame in MB
        """
        self.max_frame_size_bytes = max_frame_size_mb * 1024 * 1024
        self._blocks: Dict[str, shared_memory.SharedMemory] = {}
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)
        
        # Dtype mapping for serialization
        self._dtype_map = {
            np.uint8: 0,
            np.float32: 1,
            np.float64: 2,
        }
        self._dtype_reverse_map = {v: k for k, v in self._dtype_map.items()}
    
    def write_frame(self, frame: np.ndarray) -> str:
        """
        Write frame to shared memory.
        
        Returns:
            Unique key (UUID-based)
            
        Raises:
            MemoryError: If frame is too large or memory allocation fails
        """
        # Validate frame
        if not isinstance(frame, np.ndarray):
            raise ValueError("Frame must be a NumPy array")
        
        if frame.dtype.type not in self._dtype_map:
            raise ValueError(f"Unsupported dtype: {frame.dtype}. Supported: {list(self._dtype_map.keys())}")
        
        # Calculate required size
        header_size = 16  # 4 ints: height, width, channels, dtype
        frame_size = frame.nbytes
        total_size = header_size + frame_size
        
        if total_size > self.max_frame_size_bytes:
            raise MemoryError(
                f"Frame size ({total_size} bytes) exceeds maximum "
                f"({self.max_frame_size_bytes} bytes). Skipping frame."
            )
        
        # Generate unique key
        key = str(uuid.uuid4())
        
        try:
            # Create shared memory block
            shm = shared_memory.SharedMemory(create=True, size=total_size, name=key)
            
            # Write header
            height, width = frame.shape[:2]
            channels = frame.shape[2] if len(frame.shape) == 3 else 1
            dtype_code = self._dtype_map[frame.dtype.type]
            
            header = struct.pack('IIII', height, width, channels, dtype_code)
            shm.buf[:header_size] = header
            
            # Write frame data
            shm.buf[header_size:total_size] = frame.tobytes()
            
            # Store reference
            with self._lock:
                self._blocks[key] = shm
            
            self._logger.debug(
                f"Wrote frame to shared memory",
                extra={"shared_memory_key": key, "size_bytes": total_size}
            )
            
            return key
            
        except Exception as e:
            self._logger.error(
                f"Failed to write frame to shared memory: {e}",
                extra={"error": str(e)}
            )
            # Cleanup on failure
            try:
                if 'shm' in locals():
                    shm.close()
                    shm.unlink()
            except:
                pass
            raise MemoryError(f"Failed to allocate shared memory: {e}")
    
    def read_frame(self, key: str) -> Optional[np.ndarray]:
        """
        Read frame from shared memory.
        
        Used by AI workers (not camera module).
        """
        try:
            # Access existing shared memory block
            shm = shared_memory.SharedMemory(name=key)
            
            # Read header
            header_size = 16
            header = struct.unpack('IIII', bytes(shm.buf[:header_size]))
            height, width, channels, dtype_code = header
            
            # Validate dtype
            if dtype_code not in self._dtype_reverse_map:
                raise ValueError(f"Invalid dtype code: {dtype_code}")
            
            dtype = self._dtype_reverse_map[dtype_code]
            
            # Read frame data
            frame_size = height * width * channels * np.dtype(dtype).itemsize
            frame_bytes = bytes(shm.buf[header_size:header_size + frame_size])
            
            # Reconstruct frame
            if channels == 1:
                frame = np.frombuffer(frame_bytes, dtype=dtype).reshape(height, width)
            else:
                frame = np.frombuffer(frame_bytes, dtype=dtype).reshape(height, width, channels)
            
            shm.close()  # Don't unlink - other processes may need it
            
            self._logger.debug(
                f"Read frame from shared memory",
                extra={"shared_memory_key": key, "shape": frame.shape}
            )
            
            return frame
            
        except FileNotFoundError:
            self._logger.warning(
                f"Shared memory key not found: {key}",
                extra={"shared_memory_key": key}
            )
            return None
        except Exception as e:
            self._logger.error(
                f"Failed to read frame from shared memory: {e}",
                extra={"shared_memory_key": key, "error": str(e)}
            )
            return None
    
    def cleanup(self, key: str) -> None:
        """
        Release shared memory block.
        
        Safe to call multiple times.
        """
        with self._lock:
            if key in self._blocks:
                try:
                    shm = self._blocks.pop(key)
                    shm.close()
                    shm.unlink()
                    
                    self._logger.debug(
                        f"Cleaned up shared memory block",
                        extra={"shared_memory_key": key}
                    )
                except Exception as e:
                    self._logger.warning(
                        f"Error during cleanup: {e}",
                        extra={"shared_memory_key": key, "error": str(e)}
                    )
    
    def get_stats(self) -> dict:
        """Get shared memory statistics."""
        with self._lock:
            total_blocks = len(self._blocks)
            # Approximate memory usage
            memory_used = sum(
                shm.size for shm in self._blocks.values()
            ) / (1024 * 1024)  # Convert to MB
            
            return {
                "total_blocks": total_blocks,
                "active_blocks": total_blocks,
                "memory_used_mb": round(memory_used, 2)
            }
    
    def cleanup_all(self) -> None:
        """Cleanup all shared memory blocks. Called on shutdown."""
        with self._lock:
            keys = list(self._blocks.keys())
        
        for key in keys:
            self.cleanup(key)
        
        self._logger.info("Cleaned up all shared memory blocks")
