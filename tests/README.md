# VisionGuard AI - Simple Testing Guide

## 🎯 Quick Start

Test your VisionGuard AI system in **3 simple steps** (8 minutes total).

---

## Prerequisites

1. **Virtual environment activated**:
   ```bash
   source venv/bin/activate
   ```

2. **Redis running**:
   ```bash
   redis-cli ping  # Should return PONG
   ```

3. **RTSP stream available** (for full test):
   ```bash
   # In a separate terminal
   ffmpeg -re -stream_loop -1 -i test_video.mp4 -c copy -f rtsp rtsp://localhost:8554/test
   ```

---

## Test 1: Environment Check (30 seconds)

**Purpose**: Verify all dependencies are installed

```bash
python3 tests/system_check.py
```

**Expected**: All green checkmarks ✅

---

## Test 2: Camera → Redis (2 minutes)

**Purpose**: Verify camera captures frames and pushes to Redis

```bash
# Check queue size before
redis-cli LLEN vg:medium

# Run camera for 30 seconds
timeout 30 python3 -c "
import sys, time
sys.path.insert(0, '.')
from camera_capture import start_cameras, CaptureConfig

config = CaptureConfig(cameras=[{
    'camera_id': 'test',
    'rtsp_url': 'rtsp://localhost:8554/test',
    'fps': 5
}])

manager = start_cameras(config)
time.sleep(30)
manager.stop_all()
"

# Check queue size after
redis-cli LLEN vg:medium
```

**Expected**: Queue size increased (frames were captured)

---

## Test 3: Full Pipeline (5 minutes)

**Purpose**: Verify complete system works end-to-end

```bash
python3 simple_test.py
```

**What it does**:
1. Starts camera capture
2. Starts AI worker with ONNX model
3. Starts event classification service
4. Runs all components for 5 minutes
5. Stops everything cleanly

**Expected**: All components start and run without errors

---

## ✅ Success Criteria

Your system is working if:

1. ✅ **Test 1 passes** - All imports work
2. ✅ **Test 2 shows** - Redis queue grows (frames captured)
3. ✅ **Test 3 runs** - All components start without errors

**That's it!**

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'pydantic'"
**Solution**: Activate virtual environment
```bash
source venv/bin/activate
```

### "Connection refused" (Redis)
**Solution**: Start Redis
```bash
sudo systemctl start redis
```

### "Connection refused" (RTSP)
**Solution**: Start RTSP stream first
```bash
ffmpeg -re -stream_loop -1 -i test_video.mp4 -c copy -f rtsp rtsp://localhost:8554/test
```

---

## 📁 Test Files

- `tests/system_check.py` - Environment check (Test 1)
- `simple_test.py` - Full pipeline test (Test 3)

---

## 🎯 What Each Test Validates

| Test | Validates | Time |
|------|-----------|------|
| 1. Environment Check | Dependencies installed, modules importable | 30s |
| 2. Camera → Redis | Camera captures frames, Redis queues work | 2min |
| 3. Full Pipeline | Complete system integration | 5min |

**Total: ~8 minutes to fully validate your system**

---

## 📊 Next Steps

After all tests pass:
- ✅ System is validated and working
- ✅ Ready for development
- ✅ Ready for production deployment

---

**Need help?** Check `SETUP.md` for environment setup or `TESTING_STATUS.md` for current status.
