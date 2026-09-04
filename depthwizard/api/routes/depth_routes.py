"""
Depth Estimation API Route.
"""

import os
import base64
import uuid
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from depthwizard.pipeline import estimate_depth
from depthwizard.geospatial.colormaps import apply_colormap

router = APIRouter()
TEMP_DIR = os.path.join(os.getcwd(), "outputs", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


@router.post("/estimate")
async def estimate_depth_endpoint(
    file: UploadFile = File(...),
    model_size: str = Form("base"),
):
    """
    Estimates unitless relative depth map for uploaded image or GeoTIFF file.
    Returns relative depth statistics and base64 encoded colormap preview image.
    """
    try:
        temp_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1] or ".png"
        file_path = os.path.join(TEMP_DIR, f"input_{temp_id}{ext}")

        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        # Estimate depth
        rel_depth, metadata = estimate_depth(file_path, model_size=model_size)

        # Generate colormap preview
        colored_rgb = apply_colormap(rel_depth, cmap_name="terrain")
        bgr = cv2.cvtColor(colored_rgb, cv2.COLOR_RGB2BGR)

        preview_file = os.path.join(TEMP_DIR, f"preview_{temp_id}.png")
        cv2.imwrite(preview_file, bgr)

        # Save relative depth array as .npy for downstream routes
        npy_path = os.path.join(TEMP_DIR, f"depth_{temp_id}.npy")
        np.save(npy_path, rel_depth)

        # Convert preview to base64
        _, buffer = cv2.imencode(".png", bgr)
        b64_str = base64.b64encode(buffer).decode("utf-8")

        return {
            "status": "success",
            "session_id": temp_id,
            "metadata": metadata,
            "relative_depth_stats": {
                "min": float(rel_depth.min()),
                "max": float(rel_depth.max()),
                "mean": float(rel_depth.mean()),
                "shape": list(rel_depth.shape),
                "unit": "unitless_relative",
            },
            "preview_base64": f"data:image/png;base64,{b64_str}",
            "preview_url": f"/outputs/temp/preview_{temp_id}.png",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Depth estimation failed: {str(e)}")
