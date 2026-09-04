# SIH 2026 Official Rubric Alignment

This document maps DepthWizard features directly against the two official SIH 2026 evaluation areas.

---

## Evaluation Area 1: DSM Estimation - Accuracy and Validation (50%)

| Requirement | Implementation Detail | Status |
|---|---|---|
| **Pretrained Model Backbone** | Depth Anything V2 Base default (`depth-anything/Depth-Anything-V2-Base-hf`), Small fallback (`Depth-Anything-V2-Small-hf`). No training from scratch. | **PASS** |
| **Geospatial Processing** | PNG/JPG & GeoTIFF support via Rasterio. Auto-detects georeferencing, preserves CRS, transform, resolution, and nodata. | **PASS** |
| **Tiled Inference** | Overlapping tile window inference with Hann cosine blending for large satellite tiles without detail loss. | **PASS** |
| **SRTM / GCP Scale Calibration** | Fits linear model \(Z = a \cdot D + b\) using RANSAC / Huber regression from GCP CSV or reference DEM. | **PASS** |
| **RMSE Metric** | Exact non-hardcoded Root Mean Square Error calculation against reference rasters. | **PASS** |
| **MAE Metric** | Exact non-hardcoded Mean Absolute Error calculation against reference rasters. | **PASS** |
| **Pearson Correlation (\(r\))** | Exact non-hardcoded Pearson correlation coefficient calculation. | **PASS** |
| **Raster Alignment & Reprojection** | Auto-reprojects rasters, matches extent, and compares ONLY valid overlapping pixels. | **PASS** |
| **Scene Breakdown** | Evaluates accuracy across `Urban`, `Sparse`, `Hilly`, and `Forested` scene categories. | **PASS** |
| **Artifact Exports** | Generates `evaluation.json`, `evaluation.csv`, `error_map.png`, `scatter_plot.png`, `evaluation_report.md`. | **PASS** |

---

## Evaluation Area 2: Visualization - Rendering Quality and User Experience (50%)

| Requirement | Implementation Detail | Status |
|---|---|---|
| **RGB-to-Terrain Projection** | Projects input RGB photo onto 3D terrain surface mesh vertices derived from actual DSM elevation grid. | **PASS** |
| **Visual Fidelity & Shading** | Three.js WebGL rendering with smooth normals, directional lighting, shadows, and fog. | **PASS** |
| **First-Person 3D Flythrough** | Smooth WASD flight controls + mouse look / PointerLock API. | **PASS** |
| **Multi-Camera Modes** | Orbit trackball, WASD Drone flythrough, Top-Down ortho view, and Cinematic Auto-Pilot. | **PASS** |
| **Height Inspection** | Interactive mouse raycast HUD inspecting exact spatial coordinates \((X, Y)\) and metric height (metres or rDSM). | **PASS** |
| **Slope Analysis** | Sobel spatial gradient slope calculation (degrees) with heatmaps and inspectable slope HUD. | **PASS** |
| **Exaggeration & Wireframe** | Dynamic vertical exaggeration slider (0.1x to 5.0x) and wireframe mode toggle. | **PASS** |
| **Cross-Section Profiling** | Click 2 points on 3D terrain to render elevation slice curve on Canvas graph. | **PASS** |
| **Legend & Scale Indicator** | Min/max elevation gradient colorbar legend and 3D spatial scale distance bar. | **PASS** |
| **Standalone One-Command Launch** | `python demo.py` launches unified FastAPI + Three.js application on `http://127.0.0.1:8000`. | **PASS** |
