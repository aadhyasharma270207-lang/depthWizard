"""
Quantitative Evaluation API Route.
"""

import os
import uuid
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from depthwizard.evaluation.dsm_evaluation import DSMEvaluator
from depthwizard.geospatial.io import GeospatialIO

router = APIRouter()
TEMP_DIR = os.path.join(os.getcwd(), "outputs", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


@router.post("/compare")
async def evaluate_dsm_endpoint(
    session_id: str = Form(...),
    gt_dsm_file: UploadFile = File(...),
):
    """
    Evaluates estimated DSM against uploaded Ground Truth DSM GeoTIFF or numpy array.
    Returns RMSE, MAE, AbsRel, Delta<1.25 metrics, and cross-section slice points.
    """
    est_dsm_path = os.path.join(TEMP_DIR, f"dsm_{session_id}.npy")
    if not os.path.exists(est_dsm_path):
        raise HTTPException(status_code=404, detail="Estimated DSM session not found. Generate DSM first.")

    try:
        est_dsm = np.load(est_dsm_path)

        temp_gt_path = os.path.join(TEMP_DIR, f"gt_{session_id}_{gt_dsm_file.filename}")
        contents = await gt_dsm_file.read()
        with open(temp_gt_path, "wb") as f:
            f.write(contents)

        if temp_gt_path.endswith((".tif", ".tiff", ".png", ".jpg")):
            gt_img, meta = GeospatialIO.read_image(temp_gt_path)
            if gt_img.ndim == 3:
                gt_dsm = gt_img[:, :, 0].astype(np.float32)
            else:
                gt_dsm = gt_img.astype(np.float32)
        else:
            gt_dsm = np.load(temp_gt_path).astype(np.float32)

        # Resize GT if necessary to match shape
        if gt_dsm.shape != est_dsm.shape:
            import cv2

            gt_dsm = cv2.resize(gt_dsm, (est_dsm.shape[1], est_dsm.shape[0]), interpolation=cv2.INTER_LINEAR)

        # Compute accuracy metrics
        metrics = DSMEvaluator.evaluate(est_dsm, gt_dsm)

        # Generate cross-section height profile along center slice
        H, W = est_dsm.shape[:2]
        profile = DSMEvaluator.extract_height_profile(
            estimated_dsm=est_dsm,
            ground_truth_dsm=gt_dsm,
            p1=(0, H // 2),
            p2=(W - 1, H // 2),
            num_samples=100,
        )

        return {
            "status": "success",
            "session_id": session_id,
            "metrics": metrics,
            "profile_slice": profile,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")
