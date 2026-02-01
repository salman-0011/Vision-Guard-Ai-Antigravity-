# VisionGuard AI - Load Testing Module

## Overview

This module provides load testing and stress testing capabilities for the VisionGuard AI system. It simulates camera workloads to validate system stability under various conditions.

## Quick Start

```bash
# Run normal load test
python -m load_testing.runner --scenario normal

# Run all scenarios
python -m load_testing.runner --scenario all

# Run burst test
python -m load_testing.runner --scenario burst
```

## Test Scenarios

| Scenario | Cameras | FPS | Duration | Purpose |
|----------|---------|-----|----------|---------|
| **Normal** | 5 | 5 | 5 min | Baseline stability |
| **Burst** | 3 | 50 spike | 2 min | TTL eviction, memory leaks |
| **Slow** | 3 | 5 | 3 min | Backpressure handling |
| **Redis** | 3 | 5 | 2 min | Recovery from failures |

## Architecture

```
load_testing/
├── camera_simulator.py   # Fake frame generator
├── metrics_collector.py  # Redis monitoring
├── scenarios.py          # Test definitions
└── runner.py             # Test orchestration
```

## Pass/Fail Criteria

Each scenario has thresholds:
- **max_queue_size**: Queue must not grow beyond this
- **min_redis_uptime_pct**: Redis must be available this % of time

## Example Output

```
[2026-01-30 12:00:00] Starting scenario: Normal Load
[2026-01-30 12:00:10] [10s] Queue: 45, Stream: 120, FPS: 4.8
...
============================================================
SCENARIO COMPLETE: Normal Load
Result: PASS
Peak Queue: 287
Redis Uptime: 100.0%
Avg FPS: 4.6
============================================================
```

## Prerequisites

- Redis running on localhost:6379
- Python 3.8+
- No additional dependencies (uses stdlib + redis)
