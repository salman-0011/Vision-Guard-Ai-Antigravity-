# VisionGuard AI - Test Suite

System validation tests for VisionGuard AI.

## Quick Start

```bash
# Run complete test suite (guided)
python tests/run_test_suite.py

# Or run individual tests
python tests/test_1_camera_pressure.py
python tests/test_2_slow_worker.py
python tests/test_3_ecs_lifecycle.py
python tests/test_4_crash_resume.py

# Monitor metrics during tests
python tests/system_validation.py
```

## Test Files

- `run_test_suite.py` - Orchestrates all tests
- `system_validation.py` - Metrics monitoring
- `test_1_camera_pressure.py` - Camera pressure test
- `test_2_slow_worker.py` - Slow worker test (CRITICAL)
- `test_3_ecs_lifecycle.py` - ECS lifecycle test
- `test_4_crash_resume.py` - Crash resume test
- `report_template.py` - Report template
- `README.md` - Full documentation

## Purpose

Validate existing system and expose bottlenecks.
NO architecture changes - measurement only.

See README.md for complete documentation.
