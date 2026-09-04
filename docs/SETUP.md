# DepthWizard Installation & Setup Guide

This guide describes how to install dependencies, run tests, and start the DepthWizard application.

---

## System Requirements

- **Operating System**: Windows / Linux / macOS
- **Python**: 3.10 / 3.11 / 3.13
- **Node.js**: v18+ (for building Vite web app)
- **Hardware**: CUDA GPU (optional, auto-detected) or CPU

---

## 1. Environment Setup

### Clone Repository
```bash
git clone https://github.com/aadhyasharma270207-lang/depthWizard.git
cd depthWizard
```

### Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Build Frontend Production Assets (Optional if already built)
```bash
cd frontend
npm install
npx vite build
cd ..
```

---

## 2. Running DepthWizard

### One-Command Judge Launch (Recommended)
```bash
python demo.py
```
- Open browser to **`http://127.0.0.1:8000`**
- Interactive API documentation at **`http://127.0.0.1:8000/docs`**

### Run End-to-End CLI Benchmark
```bash
python demo.py --cli
```

### Run Automated Pytest Suite
```bash
pytest tests/ -v
```

### Run Domain Adaptation Fine-Tuning
```bash
python scripts/train.py --data-dir demo_data/gamus --epochs 3
```

### Run SIH Evaluation Pipeline
```bash
python scripts/evaluate.py --data-dir demo_data/gamus --output-dir outputs/sih_evaluation
```
