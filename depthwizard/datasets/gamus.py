"""
GAMUS Remote Sensing Benchmark Dataset Loader.
Supports RGB & nDSM/DSM image pairs, metadata manifests, scene classification (Urban, Sparse, Hilly, Forested),
and PyTorch Train/Val splitting.
"""

import os
import csv
import json
import logging
import numpy as np
import cv2
import torch
from torch.utils.data import Dataset
from typing import Tuple, List, Dict, Any, Optional

logger = logging.getLogger("depthwizard.datasets.gamus")

SCENE_TYPES = ["Urban", "Sparse", "Hilly", "Forested"]


class GAMUSDataset(Dataset):
    """
    PyTorch Dataset loader for the GAMUS Remote Sensing benchmark.
    Pairs RGB optical images with ground truth Digital Surface Models (DSM/nDSM).
    """

    def __init__(
        self,
        data_dir: str,
        split: str = "train",
        val_ratio: float = 0.2,
        seed: int = 42,
        transform: Optional[Any] = None,
    ):
        self.data_dir = data_dir
        self.split = split
        self.transform = transform
        self.samples = []

        if not os.path.exists(data_dir):
            logger.info(f"Directory {data_dir} not found. Generating synthetic GAMUS sample dataset...")
            create_sample_gamus_dataset(data_dir)

        self._load_manifest(seed, val_ratio)

    def _load_manifest(self, seed: int, val_ratio: float):
        """Scans dataset directory and manifest for paired samples."""
        manifest_csv = os.path.join(self.data_dir, "metadata.csv")
        manifest_json = os.path.join(self.data_dir, "manifest.json")

        all_samples = []

        if os.path.exists(manifest_csv):
            with open(manifest_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_lower = {k.strip().lower(): v.strip() for k, v in row.items()}
                    img_p = os.path.join(self.data_dir, r_lower.get("image_path", ""))
                    dsm_p = os.path.join(self.data_dir, r_lower.get("dsm_path", ""))
                    scene = r_lower.get("scene_type", "Urban")
                    if scene not in SCENE_TYPES:
                        scene = "Urban"
                    if os.path.exists(img_p) and os.path.exists(dsm_p):
                        all_samples.append({"image": img_p, "dsm": dsm_p, "scene_type": scene})
        elif os.path.exists(manifest_json):
            with open(manifest_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("samples", []):
                    img_p = os.path.join(self.data_dir, item.get("image_path", ""))
                    dsm_p = os.path.join(self.data_dir, item.get("dsm_path", ""))
                    scene = item.get("scene_type", "Urban")
                    if os.path.exists(img_p) and os.path.exists(dsm_p):
                        all_samples.append({"image": img_p, "dsm": dsm_p, "scene_type": scene})
        else:
            # Automatic directory scanning fallback
            img_dir = os.path.join(self.data_dir, "images")
            dsm_dir = os.path.join(self.data_dir, "dsm")

            if os.path.exists(img_dir) and os.path.exists(dsm_dir):
                for fname in sorted(os.listdir(img_dir)):
                    base = os.path.splitext(fname)[0]
                    img_p = os.path.join(img_dir, fname)

                    # Look for corresponding DSM file
                    dsm_candidate = None
                    for ext in [".tif", ".tiff", ".npy", ".png"]:
                        cand = os.path.join(dsm_dir, f"{base}{ext}")
                        if os.path.exists(cand):
                            dsm_candidate = cand
                            break

                    if dsm_candidate:
                        # Infer scene type from filename or default to Urban
                        scene = "Urban"
                        for st in SCENE_TYPES:
                            if st.lower() in fname.lower():
                                scene = st
                                break
                        all_samples.append({"image": img_p, "dsm": dsm_candidate, "scene_type": scene})

        if not all_samples:
            raise FileNotFoundError(f"No valid paired samples found in GAMUS dataset directory: {self.data_dir}")

        # Deterministic Train / Val splitting
        np.random.seed(seed)
        indices = np.random.permutation(len(all_samples))
        val_count = int(len(all_samples) * val_ratio)

        if self.split == "val":
            selected_idx = indices[:val_count]
        else:
            selected_idx = indices[val_count:]

        self.samples = [all_samples[i] for i in selected_idx]
        logger.info(f"Loaded GAMUS {self.split} split with {len(self.samples)} samples (Total: {len(all_samples)}).")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        sample_info = self.samples[idx]
        img_path = sample_info["image"]
        dsm_path = sample_info["dsm"]

        # Read RGB image
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            raise ValueError(f"Failed to read image: {img_path}")
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Read DSM raster / array
        if dsm_path.endswith(".npy"):
            dsm = np.load(dsm_path).astype(np.float32)
        else:
            from depthwizard.geospatial.io import GeospatialIO

            dsm_arr, _ = GeospatialIO.read_image(dsm_path)
            if dsm_arr.ndim == 3:
                dsm = dsm_arr[:, :, 0].astype(np.float32)
            else:
                dsm = dsm_arr.astype(np.float32)

        # Convert to Tensors
        rgb_tensor = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0  # (3, H, W)
        dsm_tensor = torch.from_numpy(dsm).unsqueeze(0).float()  # (1, H, W)

        return {
            "image": rgb_tensor,
            "dsm": dsm_tensor,
            "scene_type": sample_info["scene_type"],
            "image_path": img_path,
            "dsm_path": dsm_path,
        }


def create_sample_gamus_dataset(data_dir: str):
    """
    Creates a synthetic sample GAMUS benchmark dataset containing all 4 scene types
    (Urban, Sparse, Hilly, Forested) with true elevation grids and metadata CSV.
    """
    img_dir = os.path.join(data_dir, "images")
    dsm_dir = os.path.join(data_dir, "dsm")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(dsm_dir, exist_ok=True)

    manifest_rows = []
    scenes = [
        ("urban_01", "Urban", 50.0, 120.0),
        ("sparse_01", "Sparse", 10.0, 40.0),
        ("hilly_01", "Hilly", 150.0, 450.0),
        ("forested_01", "Forested", 25.0, 65.0),
    ]

    H, W = 256, 256
    x = np.linspace(-2, 2, W)
    y = np.linspace(-2, 2, H)
    xx, yy = np.meshgrid(x, y)

    for name, scene_type, min_h, max_h in scenes:
        img_name = f"{name}.png"
        dsm_name = f"{name}_dsm.npy"

        # Generate scene elevation pattern
        if scene_type == "Urban":
            z = np.full((H, W), min_h, dtype=np.float32)
            z[40:120, 40:120] = max_h
            z[140:220, 140:220] = max_h * 0.8
        elif scene_type == "Hilly":
            z = (np.sin(xx * 2) * np.cos(yy * 2) + 1.5) * (max_h - min_h) / 3.0 + min_h
        elif scene_type == "Forested":
            noise = np.random.uniform(-5.0, 5.0, (H, W)).astype(np.float32)
            z = np.full((H, W), (min_h + max_h) / 2.0, dtype=np.float32) + noise
        else:  # Sparse
            z = np.full((H, W), min_h, dtype=np.float32)
            z[100:150, 100:150] = max_h

        # Generate RGB synthetic representation
        z_norm = ((z - z.min()) / (z.max() - z.min() + 1e-6) * 255).astype(np.uint8)
        bgr = cv2.applyColorMap(z_norm, cv2.COLORMAP_VIRIDIS)

        img_path = os.path.join(img_dir, img_name)
        dsm_path = os.path.join(dsm_dir, dsm_name)

        cv2.imwrite(img_path, bgr)
        np.save(dsm_path, z)

        manifest_rows.append({
            "image_path": os.path.relpath(img_path, data_dir),
            "dsm_path": os.path.relpath(dsm_path, data_dir),
            "scene_type": scene_type,
            "crs": "EPSG:4326",
            "resolution_m": 1.0,
        })

    # Save metadata.csv
    csv_path = os.path.join(data_dir, "metadata.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "dsm_path", "scene_type", "crs", "resolution_m"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    logger.info(f"Synthetic GAMUS dataset created successfully in {data_dir}")
