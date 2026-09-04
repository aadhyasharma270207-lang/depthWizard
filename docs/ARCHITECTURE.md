# DepthWizard System Architecture

DepthWizard is an integrated end-to-end solution for single-view height estimation, metric Digital Surface Model (DSM) generation, GCP scale calibration, raster reprojection, quantitative evaluation, and interactive 3D flythrough visualization.

---

## High-Level Architecture Diagram

```
  +----------------------+          +--------------------------+
  |  Optical RGB Photo / |  ----->  |  Rasterio Geospatial IO  |
  |     GeoTIFF Tile     |          | (CRS & Transform Detect) |
  +----------------------+          +--------------------------+
                                                 |
                                                 v
                                    +--------------------------+
                                    |  Depth Anything V2 Engine|
                                    | (Base / Small Encoders)  |
                                    +--------------------------+
                                                 |
                                                 v
                                    +--------------------------+
                                    | Unitless Relative Depth  |
                                    |      Map (rDSM [0-1])    |
                                    +--------------------------+
                                                 |
                                                 v
                                    +--------------------------+
                                    |  SRTM / GCP Scale & Shift|
                                    |   Calibration (Z=aD+b)   |
                                    +--------------------------+
                                                 |
                                                 v
                                    +--------------------------+
                                    |  Georeferenced Metric    |
                                    |   Absolute DSM (GeoTIFF) |
                                    +--------------------------+
                                       /         |          \
                                      /          |           \
                                     v           v            v
            +---------------------------+  +----------+  +----------------------+
            | Trimesh 3D Terrain Builder|  | Slope Map|  | Raster Reprojection  |
            |     (Binary .GLB Mesh)    |  | (Sobel)  |  | & SIH Metrics Engine |
            +---------------------------+  +----------+  +----------------------+
                         |                                          |
                         v                                          v
            +---------------------------+                +----------------------+
            |  Three.js Web UI Viewer   |                | SIH Evaluation Report|
            |   (WASD Drone Flythrough) |                | (RMSE, MAE, Pearson r|
            +---------------------------+                |  per scene category) |
                                                         +----------------------+
```

---

## Core Modules & Responsibilities

1. **`depthwizard.models.depth_anything`**:
   - Manages Depth Anything V2 models (`base` as default, `small` as fallback).
   - Tiled inference engine (`predict_tiled`): splits large satellite tiles (>1024px) into overlapping windows with Hann cosine blending to prevent resizing artifacts.

2. **`depthwizard.geospatial.io` & `alignment`**:
   - `GeospatialIO`: Reads PNG/JPG and GeoTIFF files using Rasterio, extracting spatial CRS (`EPSG:4326`, `EPSG:3857`), Affine transformation matrices, bounds, and `nodata` values.
   - `align_rasters`: Compares estimated DSM against reference ground truth rasters. Handles CRS verification, spatial reprojection via Rasterio, bilinear resampling, and `nodata` masking.

3. **`depthwizard.calibration.scale_calibration`**:
   - `ScaleCalibrator`: Calibrates relative unitless depth \(D\) to metric elevation \(Z = a \cdot D + b\) using Ground Control Points (GCPs) or reference SRTM DEM grids via RANSAC and Huber robust regression.

4. **`depthwizard.evaluation.sih_evaluator`**:
   - `SIHEvaluator`: Computes non-hardcoded quantitative metrics (RMSE, MAE, Pearson correlation \(r\)) and scene-type accuracy breakdowns (`Urban`, `Sparse`, `Hilly`, `Forested`). Exports `evaluation.json`, `evaluation.csv`, `error_map.png`, `scatter_plot.png`, and `evaluation_report.md`.

5. **`depthwizard.mesh.mesh_generator`**:
   - `TerrainMeshGenerator`: Converts 2D DSM elevation grid + RGB texture overlay into 3D triangular surface meshes and exports binary `.GLB` or `.OBJ` models for Three.js.

6. **`depthwizard.api.main`**:
   - FastAPI server with lifespan singleton model loading, static mounts, and endpoints (`/health`, `/api/process`, `/api/calibrate`, `/api/evaluate`, `/api/jobs/{job_id}`).
