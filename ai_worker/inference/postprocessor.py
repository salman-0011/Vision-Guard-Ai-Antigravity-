"""
VisionGuard AI - Result Postprocessor

Decodes model output and applies confidence thresholding.
Model-specific logic for extracting detections.
"""

import numpy as np
import logging
from typing import Optional, Dict


class Postprocessor:
    """
    Result postprocessor for ONNX model outputs.
    
    Decodes model output, applies confidence threshold, extracts bounding boxes.
    NO tracking, NO temporal logic, NO decision making.
    """
    
    def __init__(self, confidence_threshold: float = 0.75):
        """
        Initialize postprocessor.
        
        Args:
            confidence_threshold: Minimum confidence for valid detections
        """
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            f"Postprocessor initialized",
            extra={"confidence_threshold": confidence_threshold}
        )
    
    def postprocess(self, output: np.ndarray) -> Optional[Dict]:
        """
        Postprocess model output.
        
        This is a generic implementation for object detection models.
        Adapt based on specific model output format.
        
        Args:
            output: Raw model output
            
        Returns:
            Dictionary with confidence and bbox, or None if below threshold
        """
        try:
            # Generic object detection output format:
            # output shape: (1, num_detections, 5+num_classes)
            # where each detection is [x1, y1, x2, y2, confidence, class_scores...]
            
            if output.ndim == 3:
                # Get first detection (highest confidence usually)
                detection = output[0, 0]
                
                # Extract confidence (assuming index 4)
                confidence = float(detection[4])
                
                # Normalize if model outputs percentage scale (0–100)
                if confidence > 1.0:
                    confidence = confidence / 100.0
                
                # Enforce invariant: confidence must be 0–1
                if not (0.0 <= confidence <= 1.0):
                    raise ValueError(
                        f"[CONFIDENCE SCALE ERROR] Invalid confidence value: {confidence}"
                    )
                
                self.logger.debug(
                    "Worker confidence normalized",
                    extra={"confidence": round(confidence, 4)}
                )
                
                # Check threshold
                if confidence < self.confidence_threshold:
                    self.logger.debug(
                        f"Detection below threshold",
                        extra={
                            "confidence": round(confidence, 4),
                            "threshold": self.confidence_threshold
                        }
                    )
                    return None
                
                # Extract bounding box [x1, y1, x2, y2]
                bbox = detection[:4].tolist()
                
                result = {
                    "confidence": confidence,
                    "bbox": bbox
                }
                
                self.logger.debug(
                    f"Detection postprocessed",
                    extra={
                        "confidence": round(confidence, 4),
                        "bbox": bbox
                    }
                )
                
                return result
                
            elif output.ndim == 2:
                # Classification output: (1, num_classes)
                # Get max confidence
                confidence = float(np.max(output))
                
                # Normalize if model outputs percentage scale (0–100)
                if confidence > 1.0:
                    confidence = confidence / 100.0
                
                # Enforce invariant: confidence must be 0–1
                if not (0.0 <= confidence <= 1.0):
                    raise ValueError(
                        f"[CONFIDENCE SCALE ERROR] Invalid confidence value: {confidence}"
                    )
                
                self.logger.debug(
                    "Worker confidence normalized",
                    extra={"confidence": round(confidence, 4)}
                )
                
                if confidence < self.confidence_threshold:
                    self.logger.debug(
                        f"Classification below threshold",
                        extra={
                            "confidence": round(confidence, 4),
                            "threshold": self.confidence_threshold
                        }
                    )
                    return None
                
                result = {
                    "confidence": confidence,
                    "bbox": None  # No bbox for classification
                }
                
                self.logger.debug(
                    f"Classification postprocessed",
                    extra={"confidence": round(confidence, 4)}
                )
                
                return result
            
            else:
                self.logger.warning(
                    f"Unexpected output shape",
                    extra={"output_shape": output.shape}
                )
                return None
                
        except Exception as e:
            self.logger.error(
                f"Postprocessing failed: {e}",
                extra={"error": str(e), "output_shape": output.shape}
            )
            return None
