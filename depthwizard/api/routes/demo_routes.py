"""
Demo Datasets API Route for Instant Web UI Testing.
Generates and serves synthetic urban building & mountain terrain demo files.
"""

import os
import uuid
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from depthwizard.pipeline import process_image
from depthwizard.geospatial.colormaps import apply_colormap

router = APIRouter()
DEMO_DIR = os.path.join(os.getcwd(), "demo_data")
OUTPUT_DIR = os.path.join(os.getcwd(), "outputs", "demo")
TEMP_DIR = os.path.join(os.getcwd(), "outputs", "temp")
os.makedirs(DEMO_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


def ensure_demo_dataset():
    """Generates synthetic urban and mountain benchmark demo images + GT DSMs if not present."""
    urban_img_path = os.path.join(DEMO_DIR, "urban_buildings.png")
    mountain_img_path = os.path.join(DEMO_DIR, "mountain_terrain.png")
    gt_dsm_path = os.path.join(DEMO_DIR, "urban_gt_dsm.npy")

    if not os.path.exists(urban_img_path) or not os.path.exists(gt_dsm_path):
        H, W = 512, 512
        img = np.full((H, W, 3), 120, dtype=np.uint8)
        gt_dsm = np.full((H, W), 15.0, dtype=np.float32)

        # Draw 1st building
        cv2.rectangle(img, (80, 80), (220, 240), (180, 70, 70), -1)
        gt_dsm[80:240, 80:220] = 45.0

        # Draw 2nd building
        cv2.rectangle(img, (280, 100), (420, 380), (70, 140, 200), -1)
        gt_dsm[100:380, 280:420] = 68.0

        # Draw central tower
        cv2.circle(img, (256, 400), 50, (60, 190, 100), -1)
        y, x = np.ogrid[:H, :W]
        dist_from_center = np.sqrt((x - 256) ** 2 + (y - 400) ** 2)
        gt_dsm[dist_from_center <= 50] = 85.0

        # Add roads/texture noise
        cv2.rectangle(img, (230, 0), (270, 512), (40, 40, 40), -1)

        cv2.imwrite(urban_img_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        np.save(gt_dsm_path, gt_dsm)

    if not os.path.exists(mountain_img_path):
        H, W = 512, 512
        x = np.linspace(-3, 3, W)
        y = np.linspace(-3, 3, H)
        xx, yy = np.meshgrid(x, y)
        z = np.sin(xx) * np.cos(yy) * 100.0 + 200.0
        z_norm = ((z - z.min()) / (z.max() - z.min()) * 255).astype(np.uint8)
        bgr = cv2.applyColorMap(z_norm, cv2.COLORMAP_VIRIDIS)
        cv2.imwrite(mountain_img_path, bgr)


@router.get("/list")
def list_demo_datasets():
    """Lists available prepackaged demo datasets."""
    ensure_demo_dataset()
    return {
        "datasets": [
            {
                "id": "urban_buildings",
                "name": "Urban City Center (Buildings & Towers)",
                "type": "RGB Image",
                "description": "Synthetic multi-building urban scene with ground control points and true height data.",
            },
            {
                "id": "mountain_terrain",
                "name": "Alpine Mountain Ridge",
                "type": "RGB Image",
                "description": "Dynamic terrain elevation grid with steep slopes and valleys.",
            },
        ]
    }


@router.post("/run")
def run_demo_dataset(dataset_id: str = Query("urban_buildings")):
    """
    Executes the full DepthWizard pipeline on a prepackaged demo dataset.
    Returns preview images, metric statistics, and 3D GLB model URL.
    """
    ensure_demo_dataset()

    file_name = "urban_buildings.png" if dataset_id == "urban_buildings" else "mountain_terrain.png"
    input_file = os.path.join(DEMO_DIR, file_name)

    session_id = f"demo_{uuid.uuid4().hex[:8]}"
    out_dir = os.path.join(OUTPUT_DIR, session_id)

    # Sample GCPs for urban buildings demo
    gcps = None
    if dataset_id == "urban_buildings":
        gcps = [
            {"x": 150, "y": 150, "z": 45.0},
            {"x": 350, "y": 240, "z": 68.0},
            {"x": 256, "y": 400, "z": 85.0},
            {"x": 30, "y": 30, "z": 15.0},
        ]

    summary = process_image(
        input_path=input_file,
        output_dir=out_dir,
        gcps=gcps,
        model_size="base",
        export_mesh=True,
    )

    # Copy files to temp directory for static serving
    dsm_npy = os.path.join(out_dir, f"{os.path.splitext(file_name)[0]}_absolute_DSM.npy")
    if os.path.exists(dsm_npy):
        import shutil

        shutil.copy(dsm_npy, os.path.join(TEMP_DIR, f"dsm_{session_id}.npy"))

    preview_name = f"{os.path.splitext(file_name)[0]}_elevation_preview.png"
    glb_name = f"{os.path.splitext(file_name)[0]}_3d_mesh.glb"
    slope_name = f"{os.path.splitext(file_name)[0]}_slope_map.png"

    return {
        "status": "success",
        "session_id": session_id,
        "dataset_id": dataset_id,
        "summary": summary,
        "preview_url": f"/outputs/demo/{session_id}/{preview_name}",
        "slope_url": f"/outputs/demo/{session_id}/{slope_name}",
        "mesh_glb_url": f"/outputs/demo/{session_id}/{glb_name}",
    }
