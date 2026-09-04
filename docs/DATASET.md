# GAMUS Benchmark Dataset Integration

The **GAMUS (Geometry-aware Multi-modal Semantic Segmentation)** benchmark is a standard remote sensing dataset containing co-registered optical RGB imagery and normalized Digital Surface Models (nDSM/DSM).

---

## Dataset Schema

A GAMUS dataset directory must contain an optical RGB image and a corresponding true elevation raster (nDSM/DSM), linked via a metadata manifest:

```
gamus_dataset/
├── metadata.csv                       # Manifest mapping images to DSMs and scene types
├── images/                            # Optical RGB photos or GeoTIFF tiles
│   ├── urban_01.png
│   ├── sparse_01.png
│   ├── hilly_01.png
│   └── forested_01.png
└── dsm/                               # Ground truth elevation grids (.tif or .npy)
    ├── urban_01_dsm.npy
    ├── sparse_01_dsm.npy
    ├── hilly_01_dsm.npy
    └── forested_01_dsm.npy
```

---

## Manifest Format (`metadata.csv`)

| Column Name | Type | Description |
|---|---|---|
| `image_path` | `str` | Relative path to optical RGB image file |
| `dsm_path` | `str` | Relative path to reference ground truth DSM file |
| `scene_type` | `str` | Scene category: `Urban`, `Sparse`, `Hilly`, or `Forested` |
| `crs` | `str` | Coordinate Reference System (e.g., `EPSG:4326`, `EPSG:3857`) |
| `resolution_m` | `float` | Spatial pixel resolution in meters |

---

## Train / Validation Splitting

The `GAMUSDataset` class (`depthwizard/datasets/gamus.py`) performs deterministic pseudo-random splitting:
```python
from depthwizard.datasets import GAMUSDataset

# Load 80% Training Split
train_ds = GAMUSDataset(data_dir="demo_data/gamus", split="train", val_ratio=0.2)

# Load 20% Validation Split
val_ds = GAMUSDataset(data_dir="demo_data/gamus", split="val", val_ratio=0.2)
```

---

## Synthetic Benchmark Generator

If no external dataset path is provided, DepthWizard automatically invokes `create_sample_gamus_dataset()` to synthesize a benchmark dataset containing all 4 scene types (`Urban`, `Sparse`, `Hilly`, `Forested`) with true elevation grids, enabling instant testing out of the box!
