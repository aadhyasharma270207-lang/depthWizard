"""
DSM Generation & Grid Data API Route.
"""

import os
import uuid
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from depthwizard.pipeline import generate_dsm, calculate_slope
from depthwizard.geospatial.colormaps import save_colormap_preview

router = APIRouter()
TEMP_DIR = os.path.join(os.getcwd(), "outputs", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


class DSMRequest(BaseModel):
    session_id: str
    scale: Optional[float] = 50.0
    offset: Optional[float] = 10.0


@router.post("/generate")
def generate_dsm_endpoint(req: DSMRequest):
    """
    Generates rDSM and metric Absolute DSM from previously estimated relative depth.
    """
    npy_path = os.path.join(TEMP_DIR, f"depth_{req.session_id}.npy")
    if not os.path.exists(npy_path):
        raise HTTPException(status_code=404, detail="Session ID not found. Run /api/v1/depth/estimate first.")

    try:
        rel_depth = np.load(npy_path)

        rdsm, abs_dsm = generate_dsm(
            relative_depth=rel_depth,
            scale=req.scale,
            offset=req.offset,
        )

        slope_grid = calculate_slope(abs_dsm if abs_dsm is not None else rdsm)

        # Save arrays and colormap previews
        abs_npy_path = os.path.join(TEMP_DIR, f"dsm_{req.session_id}.npy")
        np.save(abs_npy_path, abs_dsm)

        slope_npy_path = os.path.join(TEMP_DIR, f"slope_{req.session_id}.npy")
        np.save(slope_npy_path, slope_grid)

        dsm_preview_file = os.path.join(TEMP_DIR, f"dsm_preview_{req.session_id}.png")
        save_colormap_preview(abs_dsm, dsm_preview_file, cmap_name="terrain")

        slope_preview_file = os.path.join(TEMP_DIR, f"slope_preview_{req.session_id}.png")
        save_colormap_preview(slope_grid, slope_preview_file, cmap_name="inferno")

        return {
            "status": "success",
            "session_id": req.session_id,
            "scale_used": req.scale,
            "offset_used": req.offset,
            "dsm_stats": {
                "min_elevation_m": float(np.min(abs_dsm)),
                "max_elevation_m": float(np.max(abs_dsm)),
                "mean_elevation_m": float(np.mean(abs_dsm)),
                "max_slope_deg": float(np.max(slope_grid)),
            },
            "dsm_preview_url": f"/outputs/temp/dsm_preview_{req.session_id}.png",
            "slope_preview_url": f"/outputs/temp/slope_preview_{req.session_id}.png",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DSM generation failed: {str(e)}")


@router.get("/grid-data")
def get_grid_data(session_id: str):
    """
    Returns actual 2D DSM elevation grid array, slope array, and spatial metadata for Three.js viewer.
    """
    dsm_path = os.path.join(TEMP_DIR, f"dsm_{session_id}.npy")
    slope_path = os.path.join(TEMP_DIR, f"slope_{session_id}.npy")
    depth_path = os.path.join(TEMP_DIR, f"depth_{session_id}.npy")

    if not os.path.exists(dsm_path) and not os.path.exists(depth_path):
        raise HTTPException(status_code=404, detail="Session grid data not found.")

    is_calibrated = os.path.exists(dsm_path)
    grid_arr = np.load(dsm_path if is_calibrated else depth_path).astype(np.float32)

    slope_arr = None
    if os.path.exists(slope_path):
        slope_arr = np.load(slope_path).astype(np.float32)
    else:
        slope_arr = calculate_slope(grid_arr)

    # Subsample grid for fast WebGL transmission if very large
    H, W = grid_arr.shape[:2]
    stride = max(1, max(H, W) // 256)
    grid_sub = grid_arr[::stride, ::stride]
    slope_sub = slope_arr[::stride, ::stride]

    unit = "metres" if is_calibrated else "relative_unitless"

    return {
        "status": "success",
        "session_id": session_id,
        "is_calibrated": is_calibrated,
        "unit": unit,
        "width": grid_sub.shape[1],
        "height": grid_sub.shape[0],
        "min_elevation": float(np.min(grid_sub)),
        "max_elevation": float(np.max(grid_sub)),
        "elevation_grid": grid_sub.tolist(),
        "slope_grid": slope_sub.tolist(),
        "rgb_texture_url": f"/outputs/temp/preview_{session_id}.png",
    }
