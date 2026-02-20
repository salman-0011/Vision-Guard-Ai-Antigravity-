#!/usr/bin/env python3
"""
Analyze ONNX model architecture and output characteristics.
Helps understand why confidence scores are low.
"""

import onnxruntime as ort
import numpy as np
import os

model_path = "/home/salman/data/vision guard ai/Vision Guard Ai ( Anti gravity) /models/fire_detection.onnx"

print("\n" + "="*80)
print("ONNX MODEL ANALYSIS - Fire Detection")
print("="*80)

# Load model
try:
    session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
except Exception as e:
    print(f"Error loading model: {e}")
    exit(1)

# Get model info
print("\n📋 MODEL INPUTS")
print("-"*80)
for input_obj in session.get_inputs():
    print(f"  Name: {input_obj.name}")
    print(f"  Shape: {input_obj.shape}")
    print(f"  Type: {input_obj.type}")

print("\n📋 MODEL OUTPUTS")
print("-"*80)
for output_obj in session.get_outputs():
    print(f"  Name: {output_obj.name}")
    print(f"  Shape: {output_obj.shape}")
    print(f"  Type: {output_obj.type}")

# Try a dummy inference to see output format
print("\n🧪 DUMMY INFERENCE TEST")
print("-"*80)

input_name = session.get_inputs()[0].name
input_shape = session.get_inputs()[0].shape

# Create dummy input matching expected shape
# Most models expect (batch, channels, height, width)
dummy_input = np.random.randn(1, 3, 640, 640).astype(np.float32)
print(f"  Dummy input shape: {dummy_input.shape}")
print(f"  Dummy input dtype: {dummy_input.dtype}")

try:
    output = session.run(None, {input_name: dummy_input})
    print(f"\n  ✓ Inference successful!")
    print(f"  Number of outputs: {len(output)}")
    
    for i, out in enumerate(output):
        print(f"\n  Output {i}:")
        print(f"    Shape: {out.shape}")
        print(f"    Dtype: {out.dtype}")
        print(f"    Min value: {out.min():.6f}")
        print(f"    Max value: {out.max():.6f}")
        print(f"    Mean value: {out.mean():.6f}")
        
        # Show a sample of values
        flat = out.flatten()
        print(f"    Sample values: {flat[:10]}")
        
        # Check if this looks like confidence scores
        if 0.0 <= out.min() and out.max() <= 1.0:
            print(f"    → LIKELY confidence scores (0-1 range) ✓")
            print(f"    → Value 0.3-0.35 would be reasonable for real detections")
        elif 0.0 <= out.min() and out.max() <= 100.0:
            print(f"    → LIKELY percentage scores (0-100 range)")
        elif out.min() < 0:
            print(f"    → UNUSUAL: Negative values (may be logits or features)")
        
except Exception as e:
    print(f"  ✗ Inference failed: {e}")

print("\n" + "="*80)
print("\n💡 ANALYSIS")
print("-"*80)
print("""
Confidence scores of 0.28-0.35 indicate one of:

1. ✓ GOOD: Model is outputting calibrated probabilities
   - Values 0.3-0.4 on real fire can be normal
   - Think of it as "30-35% confidence in fire detection"
   - May still represent accurate detections if trained properly

2. ⚠️ MODEL QUALITY: Model was trained on limited data
   - Underfitting: Model not confident on any input
   - Need more training data or different training approach

3. ⚠️ INPUT MISMATCH: Model trained on different input
   - Resolution mismatch (trained on 1080p, receiving 480p)
   - Color space mismatch (trained on RGB, receiving BGR)
   - Lighting/quality: Model trained on clear video, receiving compressed stream

4. ⚠️ ARCHITECTURE: Model designed for regression, not classification
   - True/false not binary, but confidence in specific fire region

TEST: If real fires show 0.3-0.35 and non-fires show 0.0-0.1,
      the model IS working - threshold just needs to be lowered to ~0.25
""")

print("\nRECOMMENDATION:")
print("-"*80)
print("""
1. Check if your IP Webcam fire video has ACTUAL flames
   - Does it show clear, visible fire?
   - What quality is it (resolution, compression)?

2. Set threshold to 0.20-0.30 to catch these detections

3. Test with non-fire video:
   - If it stays below 0.20: Model is working well ✓
   - If it goes above 0.30: Model has high false positive rate ✗

4. Sample detections visually:
   - Save detected frames with bounding boxes
   - Verify they actually show fire in those regions
""")

print("="*80 + "\n")
