"""
GCP Scale Calibration API Route.
"""

import os
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional

from depthwizard.pipeline import calibrate_depth
from depthwizard.calibration.scale_calibration import ScaleCalibrator

router = APIRouter()
TEMP_DIR = os.path.join(os.getcwd(), "outputs", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


class GCPPoint(BaseModel):
    x: float
    y: float
    z: float


class CalibrationJSONRequest(BaseModel):
    session_id: str
    gcps: List[GCPPoint]


@router.post("/gcp-points")
def calibrate_gcp_points_endpoint(req: CalibrationJSONRequest):
    """
    Calibrates scale (a) and shift (b) from JSON list of GCP points: [{'x', 'y', 'z'}].
    """
    npy_path = os.path.join(TEMP_DIR, f"depth_{req.session_id}.npy")
    if not os.path.exists(npy_path):
        raise HTTPException(status_code=404, detail="Session ID not found. Run /api/v1/depth/estimate first.")

    try:
        rel_depth = np.load(npy_path)
        gcp_dicts = [{"x": p.x, "y": p.y, "z": p.z} for p in req.gcps]

        scale_a, offset_b, cal_meta = calibrate_depth(
            relative_depth=rel_depth,
            gcps=gcp_dicts,
        )

        return {
            "status": "success",
            "session_id": req.session_id,
            "scale_a": scale_a,
            "offset_b": offset_b,
            "calibration_metrics": cal_meta,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GCP calibration failed: {str(e)}")


@router.post("/gcp-csv")
async def calibrate_gcp_csv_endpoint(
    session_id: str = Form(...),
    csv_file: UploadFile = File(...),
):
    """
    Calibrates scale (a) and shift (b) from an uploaded GCP CSV file.
    """
    npy_path = os.path.join(TEMP_DIR, f"depth_{session_id}.npy")
    if not os.path.exists(npy_path):
        raise HTTPException(status_code=404, detail="Session ID not found.")

    try:
        temp_csv = os.path.join(TEMP_DIR, f"gcp_{session_id}.csv")
        contents = await csv_file.read()
        with open(temp_csv, "wb") as f:
            f.write(contents)

        rel_depth = np.load(npy_path)
        scale_a, offset_b, cal_meta = calibrate_depth(
            relative_depth=rel_depth,
            gcps=temp_csv,
        )

        return {
            "status": "success",
            "session_id": session_id,
            "scale_a": scale_a,
            "offset_b": offset_b,
            "calibration_metrics": cal_meta,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV calibration failed: {str(e)}")
