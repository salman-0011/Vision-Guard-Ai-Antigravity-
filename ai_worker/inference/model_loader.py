"""
VisionGuard AI - ONNX Model Loader

Loads ONNX model once at startup with CPU-only execution.
Thread tuning for optimal CPU performance.
"""

import onnxruntime as ort
import logging
from typing import List, Tuple


class ModelLoader:
    """
    ONNX model loader with CPU-only execution.
    
    Loads model once and keeps it resident in memory.
    Configures thread tuning for optimal CPU performance.
    """
    
    def __init__(
        self,
        model_path: str,
        intra_op_num_threads: int = 4,
        inter_op_num_threads: int = 2
    ):
        """
        Initialize and load ONNX model.
        
        Args:
            model_path: Path to .onnx model file
            intra_op_num_threads: Intra-op parallelism threads
            inter_op_num_threads: Inter-op parallelism threads
            
        Note: Total threads should not exceed CPU cores / worker_count
        """
        self.model_path = model_path
        self.logger = logging.getLogger(__name__)
        
        # Configure session options
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = intra_op_num_threads
        sess_options.inter_op_num_threads = inter_op_num_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # Load model with CPU provider ONLY
        try:
            self.session = ort.InferenceSession(
                model_path,
                sess_options=sess_options,
                providers=['CPUExecutionProvider']
            )
            
            # Get model metadata
            self.input_name = self.session.get_inputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape
            self.output_names = [output.name for output in self.session.get_outputs()]
            
            self.logger.info(
                f"Loaded ONNX model successfully",
                extra={
                    "model_path": model_path,
                    "input_name": self.input_name,
                    "input_shape": self.input_shape,
                    "output_names": self.output_names,
                    "intra_op_threads": intra_op_num_threads,
                    "inter_op_threads": inter_op_num_threads,
                    "providers": self.session.get_providers()
                }
            )
            
        except Exception as e:
            self.logger.error(
                f"Failed to load ONNX model: {e}",
                extra={"model_path": model_path, "error": str(e)}
            )
            raise
    
    def get_input_shape(self) -> Tuple:
        """
        Get model input shape.
        
        Returns:
            Input shape tuple (e.g., (1, 3, 640, 640))
        """
        return tuple(self.input_shape)
    
    def get_session(self) -> ort.InferenceSession:
        """
        Get ONNX inference session.
        
        Returns:
            ONNX Runtime inference session
        """
        return self.session
