# VisionGuard AI - Setup Guide

## Virtual Environment Setup

This project uses a Python virtual environment to manage dependencies.

### ✅ Already Completed

The virtual environment has been created and all dependencies installed:

```bash
# Virtual environment location
./venv/

# Installed packages:
- pydantic 2.12.5
- redis 7.1.0
- numpy 2.4.1
- opencv-python 4.13.0.90
- onnxruntime 1.23.2
- python-dotenv 1.2.1
- pytest 9.0.2
- pytest-cov 7.0.0
```

---

## How to Use the Virtual Environment

### Activate the Virtual Environment

**Every time** you work on this project, activate the virtual environment first:

```bash
# From project root directory
source venv/bin/activate
```

You'll see `(venv)` in your terminal prompt when activated.

### Run Python Scripts

With the virtual environment activated, use `python` or `python3` directly:

```bash
# Run tests
python tests/test_1_camera_pressure.py

# Run test suite
python tests/run_test_suite.py

# Run system validation
python tests/system_validation.py
```

### Deactivate When Done

```bash
deactivate
```

---

## Quick Start Commands

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Verify installation
python -c "import pydantic, redis, numpy, cv2, onnxruntime; print('✅ All packages installed!')"

# 3. Run test suite
python tests/run_test_suite.py

# 4. Deactivate when done
deactivate
```

---

## Installing Additional Packages

If you need to install more packages:

```bash
# Activate venv first
source venv/bin/activate

# Install package
pip install package-name

# Or add to requirements.txt and run:
pip install -r requirements.txt
```

---

## Project Structure

```
Vision Guard Ai ( Anti gravity)/
├── venv/                    # Virtual environment (DO NOT commit to git)
├── requirements.txt         # Project dependencies
├── camera_capture/          # Camera module
├── ai_worker/              # AI inference workers
├── event_classification/   # Event classification service
└── tests/                  # System validation tests
```

---

## Troubleshooting

### "No module named 'pydantic'" error

Make sure virtual environment is activated:
```bash
source venv/bin/activate
```

### Permission errors

The virtual environment is local to this project - no sudo needed.

### Reinstall packages

```bash
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

---

## Next Steps

1. **Activate virtual environment**: `source venv/bin/activate`
2. **Verify Redis is running**: `redis-cli ping` (should return PONG)
3. **Run tests**: `python tests/run_test_suite.py`

---

## Important Notes

- ✅ Virtual environment is **already created and configured**
- ✅ All dependencies are **already installed**
- ⚠️ **Always activate** the venv before running Python scripts
- ⚠️ Add `venv/` to `.gitignore` (don't commit it)

---

Ready to test! Activate the virtual environment and run the test suite.
