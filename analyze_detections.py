#!/usr/bin/env python3
"""
Analyze detections in results stream by model type.
"""

import redis
import json

r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)

# Get all entries from results stream
entries = r.xrange('vg:ai:results', count=1000)

# Analyze by model type
models = {}
for entry_id, data in entries:
    model = data.get('model', 'unknown')
    if model not in models:
        models[model] = {'count': 0, 'confidences': []}
    models[model]['count'] += 1
    models[model]['confidences'].append(float(data.get('confidence', 0)))

print("\n" + "="*70)
print("DETECTION SUMMARY BY MODEL TYPE")
print("="*70)

for model, info in sorted(models.items()):
    confidences = info['confidences']
    count = info['count']
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    min_conf = min(confidences) if confidences else 0
    max_conf = max(confidences) if confidences else 0
    
    print(f"\n{model.upper():10s}:")
    print(f"  Count:      {count:4d} detections")
    print(f"  Confidence: min={min_conf:.3f}, avg={avg_conf:.3f}, max={max_conf:.3f}")

print("\n" + "="*70)
print(f"TOTAL: {len(entries)} detections in stream")
print("="*70 + "\n")
