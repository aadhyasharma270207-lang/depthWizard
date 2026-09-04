# SIH 2026 Quantitative Evaluation Protocol

This document details the mathematical metric definitions, spatial raster alignment procedures, and evaluation artifact generation used in DepthWizard.

---

## Required SIH Metrics

### 1. Root Mean Square Error (RMSE)
Measures the square root of average squared vertical differences between estimated heights \(H_{est}\) and ground truth heights \(H_{gt}\) in meters:
\[ \text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (H_{est, i} - H_{gt, i})^2} \]

### 2. Mean Absolute Error (MAE)
Measures average absolute height error magnitude in meters:
\[ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |H_{est, i} - H_{gt, i}| \]

### 3. Pearson Correlation Coefficient (\(r\))
Measures linear correlation between estimated elevation grid and ground truth elevation grid:
\[ r = \frac{\sum_{i=1}^{N} (H_{est, i} - \bar{H}_{est})(H_{gt, i} - \bar{H}_{gt})}{\sqrt{\sum_{i=1}^{N} (H_{est, i} - \bar{H}_{est})^2 \sum_{i=1}^{N} (H_{gt, i} - \bar{H}_{gt})^2}} \]

---

## Spatial Alignment & Raster Verification Protocol

Before computing evaluation metrics, `align_rasters()` (`depthwizard/geospatial/alignment.py`) executes:
1. **CRS Verification**: Compares Coordinate Reference Systems (`EPSG:4326` vs `EPSG:3857`).
2. **Reprojection**: If CRS differs, reprojects estimated DSM to reference CRS using Rasterio `reproject` & `Resampling.bilinear`.
3. **Extent Clipping**: Crops both rasters to their bounding box intersection and resamples pixel grid shapes.
4. **Nodata Masking**: Filters out `nodata` pixels (e.g. `-9999.0` or `NaN`) in both grids so evaluation is performed **ONLY on valid overlapping pixels**.

---

## Scene Category Accuracy Breakdown

Accuracy metrics are calculated overall and broken down across 4 scene types:
- **`Urban`**: High-density building clusters, vertical structures, towers.
- **`Sparse`**: Flat ground, open plains, isolated buildings.
- **`Hilly`**: Rolling terrain, mountain slopes, elevation gradients.
- **`Forested`**: Canopy vegetation, tree cover height variation.

---

## Exported Evaluation Artifacts

Running `python scripts/evaluate.py` generates the following files in `outputs/sih_evaluation/`:
- **`evaluation.json`**: Structured JSON report with overall and per-scene metrics.
- **`evaluation.csv`**: Detailed CSV breakdown per tile/image sample.
- **`error_map.png`**: Spatial error heatmap showing pixel-wise vertical difference \(|H_{est} - H_{gt}|\).
- **`scatter_plot.png`**: Scatter plot of reference elevation vs estimated elevation with 1:1 reference line.
- **`evaluation_report.md`**: Complete Markdown summary report.

---

## Handling Missing Reference Data

If no reference ground truth DSM/LiDAR raster is provided, DepthWizard does **NOT** invent fake scores. It cleanly displays:
> **"Reference DSM/LiDAR required for quantitative evaluation."**
