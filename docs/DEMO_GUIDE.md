# DepthWizard Hackathon Demonstration Guide

This guide provides step-by-step instructions for hackathon judges and reviewers to run and evaluate DepthWizard.

---

## 1. Quick Launch (One-Command)

Run the single launcher command:
```bash
python demo.py
```
*Output:*
```
=================================================================
           DEPTHWIZARD SIH 2026 INTEGRATED SYSTEM                
=================================================================
🚀 Launching DepthWizard Application Server...
🌐 Web Application & API available at:  http://127.0.0.1:8000
📖 Interactive API Documentation at:     http://127.0.0.1:8000/docs
=================================================================
```
Open **`http://127.0.0.1:8000`** in your web browser.

---

## 2. Interactive Web Application Walkthrough

### Step A: 3D Flythrough & Analysis Tab
1. Click **🚀 Quick Demo** in the top header bar.
2. The prepackaged urban building dataset will load into the Three.js 3D viewport.
3. **Camera Controls**:
   - Change camera mode dropdown to **WASD Drone Flythrough**. Use `W, A, S, D` keys to fly through 3D buildings. Use `Q` (up) and `E` (down) for altitude.
   - Switch to **Top-Down Ortho View** or **Cinematic Auto-Pilot**.
4. **Height Inspection**: Hover mouse over 3D terrain to read real-time \((X, Y, \text{Elevation})\) and Slope in degrees on the HUD panel.
5. **Vertical Exaggeration**: Adjust slider from 0.1x to 5.0x to amplify elevation relief.
6. **Cross-Section Profiling**: Click two points on the 3D terrain to draw a slice line vector.

### Step B: Depth & DSM Studio Tab
1. Select an RGB photo (`.png`/`.jpg`) or GeoTIFF file.
2. Select Depth Anything V2 Encoder (`Base` default or `Small` fallback).
3. Click **⚡ Process & Generate 3D Terrain**.
4. Inspect side-by-side output previews: RGB Input, rDSM, Metric DSM (Terrain colormap), and Slope gradient heatmap.

### Step C: GCP Calibration Tab
1. Input Ground Control Points \((x, y, Z_{true})\).
2. Click **🎯 Fit RANSAC Scale & Offset**.
3. View fitted linear equation \(Z = a \cdot D + b\) and RANSAC inlier count.

### Step D: Accuracy Metrics Tab
1. Upload Ground Truth DSM or LiDAR reference raster.
2. View quantitative SIH evaluation metrics: RMSE, MAE, Pearson \(r\), and cross-section height profile curve comparison.

---

## 3. Command-Line Benchmark Execution

### A. Run CLI Processing Demo
```bash
python demo.py --cli
```

### B. Run Automated Pytest Suite
```bash
pytest tests/ -v
```

### C. Run GAMUS Domain Adaptation Training
```bash
python scripts/train.py --epochs 1
```

### D. Run SIH Evaluation Pipeline
```bash
python scripts/evaluate.py
```
*Generates evaluation reports and graphics in `outputs/sih_evaluation/`.*
