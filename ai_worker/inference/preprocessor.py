"""
VisionGuard AI - Frame Preprocessor

CPU-only frame preprocessing for ONNX inference.
Minimal copies, model-specific normalization.
"""

import cv2
import numpy as np
import logging
from typing import Tuple, List


class Preprocessor:
    """
    Frame preprocessor for ONNX models.
    
    CPU-only operations using NumPy and OpenCV.
    Resize, normalize, and format for model input.
    """
    
    def __init__(
        self,
        target_size: Tuple[int, int] = (640, 640),
        normalize_mean: List[float] = [0.485, 0.456, 0.406],
        normalize_std: List[float] = [0.229, 0.224, 0.225]
    ):
        """
        Initialize preprocessor.
        
        Args:
            target_size: Target size (width, height) for model input
            normalize_mean: Normalization mean (RGB)
            normalize_std: Normalization std (RGB)
        """
        self.target_size = target_size
        self.normalize_mean = np.array(normalize_mean, dtype=np.float32).reshape(1, 1, 3)
        self.normalize_std = np.array(normalize_std, dtype=np.float32).reshape(1, 1, 3)
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            f"Preprocessor initialized",
            extra={
                "target_size": target_size,
                "normalize_mean": normalize_mean,
                "normalize_std": normalize_std
            }
        )
    
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess frame for ONNX inference.
        
        Steps:
        1. Resize to target size
        2. Convert BGR to RGB
        3. Normalize to [0, 1]
        4. Apply mean/std normalization
        5. Transpose to (C, H, W)
        6. Add batch dimension
        
        Args:
            frame: Input frame (BGR, uint8)
            
        Returns:
            Preprocessed tensor (1, C, H, W) float32
        """
        try:
            # Resize
            if frame.shape[:2] != (self.target_size[1], self.target_size[0]):
                resized = cv2.resize(frame, self.target_size, interpolation=cv2.INTER_LINEAR)
            else:
                resized = frame
            
            # Convert BGR to RGB
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            
            # Normalize to [0, 1]
            normalized = rgb.astype(np.float32) / 255.0
            
            # Apply mean/std normalization
            normalized = (normalized - self.normalize_mean) / self.normalize_std
            
            # Transpose to (C, H, W)
            transposed = np.transpose(normalized, (2, 0, 1))
            
            # Add batch dimension (1, C, H, W)
            batched = np.expand_dims(transposed, axis=0)
            
            return batched.astype(np.float32)
            
        except Exception as e:
            self.logger.error(
                f"Preprocessing failed: {e}",
                extra={"error": str(e), "frame_shape": frame.shape}
            )
            raise
