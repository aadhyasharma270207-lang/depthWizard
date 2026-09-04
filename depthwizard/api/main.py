"""
FastAPI Backend Entrypoint for DepthWizard.
Integrates image upload, Depth Anything V2 inference, DSM generation, GCP scale calibration,
3D mesh export, and SIH evaluation into a unified API.
"""

import os
import json
import uuid
import logging
from contextlib import asynccontextmanager
import numpy as np
import cv2
import torch
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any

from depthwizard.models.depth_anything import DepthAnythingPredictor
from depthwizard.geospatial.io import GeospatialIO
from depthwizard.geospatial.dsm import generate_absolute_dsm
from depthwizard.pipeline import generate_dsm, calculate_slope
from depthwizard.geospatial.colormaps import save_colormap_preview
from depthwizard.geospatial.alignment import align_rasters
from depthwizard.calibration.scale_calibration import ScaleCalibrator
from depthwizard.evaluation.sih_evaluator import SIHEvaluator
from depthwizard.mesh.mesh_generator import TerrainMeshGenerator

from depthwizard.api.routes import (
    depth_routes,
    dsm_routes,
    calibrate_routes,
    mesh_routes,
    eval_routes,
    demo_routes,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("depthwizard.api")

# Jobs storage directory
JOBS_DIR = os.path.join(os.getcwd(), "outputs", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

# In-memory jobs database
JOBS_DB: Dict[str, Dict[str, Any]] = {}


def get_predictor_instance(app_instance: FastAPI) -> DepthAnythingPredictor:
    """Lazy loader and singleton accessor for Depth Anything V2 predictor."""
    if not hasattr(app_instance.state, "predictor") or app_instance.state.predictor is None:
        model_size = os.environ.get("DEPTHWIZARD_MODEL", "base")
        logger.info(f"Initializing Depth Anything V2 ({model_size}) model singleton...")
        try:
            app_instance.state.predictor = DepthAnythingPredictor(model_size=model_size)
        except Exception:
            app_instance.state.predictor = DepthAnythingPredictor(model_size="small")
    return app_instance.state.predictor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Loads Depth Anything V2 model ONCE at server startup and reuses it across requests."""
    get_predictor_instance(app)
    yield
    logger.info("Shutting down DepthWizard server context...")


app = FastAPI(
    title="DepthWizard SIH 2026 Unified API",
    description="Single-View Height Estimation, DSM Generation & 3D Flythrough System",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for cross-origin frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount outputs directory
app.mount("/outputs", StaticFiles(directory=os.path.join(os.getcwd(), "outputs")), name="outputs")

# Mount frontend production build static assets if available
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIST), name="static")

# Include v1 Routers
app.include_router(depth_routes.router, prefix="/api/v1/depth", tags=["Depth Estimation"])
app.include_router(dsm_routes.router, prefix="/api/v1/dsm", tags=["DSM Generation"])
app.include_router(calibrate_routes.router, prefix="/api/v1/calibrate", tags=["GCP Scale Calibration"])
app.include_router(mesh_routes.router, prefix="/api/v1/mesh", tags=["3D Mesh Export"])
app.include_router(eval_routes.router, prefix="/api/v1/evaluate", tags=["Quantitative DSM Evaluation"])
app.include_router(demo_routes.router, prefix="/api/v1/demo", tags=["Demo Datasets"])


@app.get("/")
def read_root():
    """Serves built web application or API welcome page."""
    index_html = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_html):
        return FileResponse(index_html)
    return {"message": "Welcome to DepthWizard SIH 2026 API. Access UI at /app or docs at /docs"}


@app.get("/health", tags=["System"])
def health_check(request: Request):
    """System health check endpoint returning loaded model status and CUDA/CPU device."""
    predictor = get_predictor_instance(request.app)
    predictor_loaded = predictor.is_loaded
    device_str = "cuda (GPU)" if torch.cuda.is_available() else "cpu"
    return {
        "status": "healthy",
        "system": "DepthWizard SIH 2026 Backend",
        "version": "1.0.0",
        "device": device_str,
        "model_loaded": predictor_loaded,
        "model_mode": getattr(predictor, "mode", "unknown"),
        "model_size": getattr(predictor, "model_size", "base"),
    }


@app.post("/api/process", tags=["Pipeline"])
async def process_image_endpoint(
    request: Request,
    file: UploadFile = File(...),
    scale: float = Form(50.0),
    offset: float = Form(10.0),
    gcps_json: Optional[str] = Form(None),
):
    """
    Main processing endpoint:
    Upload image/GeoTIFF -> detect georeferencing -> run Depth Anything V2 -> generate rDSM/DSM -> build 3D mesh -> return job results.
    """
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    try:
        # Save input file
        ext = os.path.splitext(file.filename)[1] or ".png"
        input_path = os.path.join(job_dir, f"input{ext}")
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

        # 1. Read image & detect georeferencing
        rgb_img, meta = GeospatialIO.read_image(input_path)
        is_georeferenced = meta.get("is_georeferenced", False)

        # 2. Run Depth Anything V2 (REUSING loaded singleton predictor)
        logger.info(f"Running Depth Anything V2 inference for job {job_id}...")
        predictor = get_predictor_instance(request.app)
        rel_depth = predictor.predict(rgb_img)

        # Save relative depth
        rel_depth_path = os.path.join(job_dir, "relative_depth.npy")
        np.save(rel_depth_path, rel_depth)

        # 3. Scale Calibration
        gcp_list = None
        if gcps_json:
            try:
                gcp_list = json.loads(gcps_json)
            except Exception:
                pass

        if gcp_list and len(gcp_list) > 0:
            fitted_scale, fitted_offset, cal_meta = ScaleCalibrator.calibrate_from_gcps(
                relative_depth=rel_depth,
                gcps=gcp_list,
                transform_affine=meta.get("transform_affine"),
            )
        else:
            fitted_scale, fitted_offset = scale, offset
            cal_meta = {"calibration_mode": "manual_or_default" if not is_georeferenced else "dem_georeferenced_default"}

        # 4. Generate rDSM, Absolute DSM, and Slope
        rdsm, abs_dsm = generate_dsm(
            relative_depth=rel_depth,
            scale=fitted_scale,
            offset=fitted_offset,
            metadata=meta,
        )
        res_x, res_y = meta.get("resolution", (1.0, 1.0))
        slope_grid = calculate_slope(abs_dsm if abs_dsm is not None else rdsm, pixel_resolution=(res_x, res_y))

        # Save arrays
        dsm_npy_path = os.path.join(job_dir, "dsm.npy")
        np.save(dsm_npy_path, abs_dsm if abs_dsm is not None else rdsm)

        if is_georeferenced:
            dsm_geotiff_path = os.path.join(job_dir, "dsm.tif")
            GeospatialIO.write_geotiff(dsm_geotiff_path, abs_dsm if abs_dsm is not None else rdsm, meta)

        # Save previews
        preview_path = os.path.join(job_dir, "preview.png")
        save_colormap_preview(abs_dsm if abs_dsm is not None else rdsm, preview_path, cmap_name="terrain")

        slope_path = os.path.join(job_dir, "slope.png")
        save_colormap_preview(slope_grid, slope_path, cmap_name="inferno")

        # 5. Build 3D Terrain GLB Mesh
        mesh_obj = TerrainMeshGenerator.generate_mesh(
            elevation_grid=abs_dsm if abs_dsm is not None else rdsm,
            rgb_texture=rgb_img,
            height_exaggeration=1.0,
        )
        glb_path = os.path.join(job_dir, "mesh.glb")
        TerrainMeshGenerator.export_glb(mesh_obj, glb_path)

        # 6. Build Metadata
        unit = "metres" if is_georeferenced else "relative_unitless"
        status_msg = "Georeferenced imagery detected — metric calibration available." if is_georeferenced else "Non-georeferenced imagery detected — producing Relative DSM."

        job_metadata = {
            "job_id": job_id,
            "filename": file.filename,
            "is_georeferenced": is_georeferenced,
            "status_message": status_msg,
            "crs": meta.get("crs"),
            "resolution": list(meta.get("resolution", (1.0, 1.0))),
            "unit": unit,
            "scale_a": fitted_scale,
            "offset_b": fitted_offset,
            "calibration_info": cal_meta,
            "min_elevation": float(np.min(abs_dsm if abs_dsm is not None else rdsm)),
            "max_elevation": float(np.max(abs_dsm if abs_dsm is not None else rdsm)),
            "mean_elevation": float(np.mean(abs_dsm if abs_dsm is not None else rdsm)),
            "max_slope_deg": float(np.max(slope_grid)),
            "vertex_count": len(mesh_obj.vertices),
            "face_count": len(mesh_obj.faces),
            "device": "cuda (GPU)" if torch.cuda.is_available() else "cpu",
        }

        meta_json_path = os.path.join(job_dir, "metadata.json")
        with open(meta_json_path, "w", encoding="utf-8") as f:
            json.dump(job_metadata, f, indent=2)

        # Save to DB
        JOBS_DB[job_id] = {
            "metadata": job_metadata,
            "job_dir": job_dir,
            "rgb_img": rgb_img,
            "rel_depth": rel_depth,
            "dsm": abs_dsm if abs_dsm is not None else rdsm,
            "slope": slope_grid,
        }

        return {
            "status": "success",
            "job_id": job_id,
            "is_georeferenced": is_georeferenced,
            "status_message": status_msg,
            "unit": unit,
            "device": job_metadata["device"],
            "elevation_stats": {
                "min": job_metadata["min_elevation"],
                "max": job_metadata["max_elevation"],
                "mean": job_metadata["mean_elevation"],
                "max_slope": job_metadata["max_slope_deg"],
            },
            "urls": {
                "dsm": f"/api/jobs/{job_id}/dsm",
                "mesh": f"/api/jobs/{job_id}/mesh",
                "metadata": f"/api/jobs/{job_id}/metadata",
                "preview": f"/api/jobs/{job_id}/preview",
                "slope": f"/outputs/jobs/{job_id}/slope.png",
            },
        }

    except Exception as e:
        logger.error(f"Processing failed for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")


@app.post("/api/calibrate", tags=["Calibration"])
def calibrate_job_endpoint(
    job_id: str = Form(...),
    gcps_json: Optional[str] = Form(None),
):
    """Calibrates DSM for an existing job using provided GCP points."""
    job_dir = os.path.join(JOBS_DIR, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail=f"Job directory {job_dir} not found.")

    try:
        rel_depth_file = os.path.join(job_dir, "relative_depth.npy")
        if not os.path.exists(rel_depth_file):
            raise FileNotFoundError(f"relative_depth.npy not found in {job_dir}")

        rel_depth = np.load(rel_depth_file)
        
        gcp_list = json.loads(gcps_json) if gcps_json else []
        if not gcp_list:
            raise ValueError("No valid GCP points provided.")

        scale_a, offset_b, cal_meta = ScaleCalibrator.calibrate_from_gcps(rel_depth, gcp_list)
        abs_dsm = generate_absolute_dsm(rel_depth, scale=scale_a, offset=offset_b)

        np.save(os.path.join(job_dir, "dsm.npy"), abs_dsm)
        save_colormap_preview(abs_dsm, os.path.join(job_dir, "preview.png"), cmap_name="terrain")

        # Regenerate mesh
        rgb_img = None
        for cand in os.listdir(job_dir):
            if cand.startswith("input."):
                try:
                    img_arr, _ = GeospatialIO.read_image(os.path.join(job_dir, cand))
                    rgb_img = img_arr
                    break
                except Exception:
                    pass

        mesh_obj = TerrainMeshGenerator.generate_mesh(abs_dsm, rgb_texture=rgb_img)
        TerrainMeshGenerator.export_glb(mesh_obj, os.path.join(job_dir, "mesh.glb"))

        return {
            "status": "success",
            "job_id": job_id,
            "scale_a": scale_a,
            "offset_b": offset_b,
            "calibration_metrics": cal_meta,
            "mesh_url": f"/api/jobs/{job_id}/mesh",
        }
    except Exception as e:
        logger.error(f"Calibration failed for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calibration failed: {str(e)}")


@app.post("/api/evaluate", tags=["Evaluation"])
async def evaluate_job_endpoint(
    job_id: str = Form(...),
    gt_file: UploadFile = File(...),
):
    """Evaluates estimated DSM of a job against uploaded Ground Truth DSM/LiDAR file."""
    job_dir = os.path.join(JOBS_DIR, job_id)
    dsm_npy = os.path.join(job_dir, "dsm.npy")

    if not os.path.exists(dsm_npy):
        raise HTTPException(status_code=404, detail=f"Job {job_id} DSM array not found. Process job first.")

    try:
        est_dsm = np.load(dsm_npy)

        # Save GT file
        gt_path = os.path.join(job_dir, f"gt_{gt_file.filename}")
        contents = await gt_file.read()
        with open(gt_path, "wb") as f:
            f.write(contents)

        # Align rasters and compute SIH metrics
        aligned_est, aligned_ref, valid_mask, align_meta = align_rasters(est_dsm, gt_path)
        metrics = SIHEvaluator.compute_sih_metrics(aligned_est, aligned_ref, valid_mask)

        # Save evaluation summary
        eval_meta_path = os.path.join(job_dir, "evaluation_summary.json")
        with open(eval_meta_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        return {
            "status": "success",
            "job_id": job_id,
            "metrics": metrics,
            "alignment": align_meta,
        }
    except Exception as e:
        logger.error(f"Evaluation failed for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.get("/api/jobs/{job_id}", tags=["Jobs"])
def get_job_status(job_id: str):
    """Returns status and metadata for a specific job."""
    job_dir = os.path.join(JOBS_DIR, job_id)
    meta_path = os.path.join(job_dir, "metadata.json")

    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    return {
        "status": "success",
        "job_id": job_id,
        "metadata": meta,
        "urls": {
            "dsm": f"/api/jobs/{job_id}/dsm",
            "mesh": f"/api/jobs/{job_id}/mesh",
            "metadata": f"/api/jobs/{job_id}/metadata",
            "preview": f"/api/jobs/{job_id}/preview",
            "slope": f"/outputs/jobs/{job_id}/slope.png",
        },
    }


@app.get("/api/jobs/{job_id}/dsm", tags=["Jobs"])
def get_job_dsm(job_id: str):
    """Downloads DSM file for a job."""
    job_dir = os.path.join(JOBS_DIR, job_id)
    tif_path = os.path.join(job_dir, "dsm.tif")
    npy_path = os.path.join(job_dir, "dsm.npy")

    if os.path.exists(tif_path):
        return FileResponse(tif_path, filename=f"{job_id}_dsm.tif", media_type="image/tiff")
    elif os.path.exists(npy_path):
        return FileResponse(npy_path, filename=f"{job_id}_dsm.npy", media_type="application/octet-stream")
    else:
        raise HTTPException(status_code=404, detail=f"DSM file for job {job_id} not found.")


@app.get("/api/jobs/{job_id}/mesh", tags=["Jobs"])
def get_job_mesh(job_id: str):
    """Downloads 3D GLB binary mesh file for a job."""
    glb_path = os.path.join(JOBS_DIR, job_id, "mesh.glb")
    if not os.path.exists(glb_path):
        raise HTTPException(status_code=404, detail=f"3D mesh for job {job_id} not found.")
    return FileResponse(glb_path, filename=f"{job_id}_terrain.glb", media_type="model/gltf-binary")


@app.get("/api/jobs/{job_id}/preview", tags=["Jobs"])
def get_job_preview(job_id: str):
    """Returns elevation heatmap preview PNG file."""
    preview_path = os.path.join(JOBS_DIR, job_id, "preview.png")
    if not os.path.exists(preview_path):
        raise HTTPException(status_code=404, detail=f"Preview for job {job_id} not found.")
    return FileResponse(preview_path, media_type="image/png")


@app.get("/api/jobs/{job_id}/metadata", tags=["Jobs"])
def get_job_metadata_file(job_id: str):
    """Downloads job metadata JSON file."""
    meta_path = os.path.join(JOBS_DIR, job_id, "metadata.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail=f"Metadata for job {job_id} not found.")
    return FileResponse(meta_path, filename=f"{job_id}_metadata.json", media_type="application/json")


@app.get("/api/jobs/{job_id}/grid", tags=["Jobs"])
def get_job_elevation_grid(job_id: str, max_size: int = 256):
    """Returns numerical elevation grid array for direct 3D BufferGeometry construction."""
    job_dir = os.path.join(JOBS_DIR, job_id)
    npy_path = os.path.join(job_dir, "dsm.npy")
    if not os.path.exists(npy_path):
        npy_path = os.path.join(job_dir, "relative_depth.npy")
    if not os.path.exists(npy_path):
        raise HTTPException(status_code=404, detail=f"Elevation grid for job {job_id} not found.")

    try:
        grid = np.load(npy_path)
        if len(grid.shape) == 3:
            grid = grid[:, :, 0]

        H, W = grid.shape[:2]
        stride = max(1, max(H, W) // max_size)
        sub_grid = grid[::stride, ::stride].astype(np.float32)
        sub_grid = np.nan_to_num(sub_grid, nan=0.0, posinf=1.0, neginf=0.0)

        meta_path = os.path.join(job_dir, "metadata.json")
        unit = "relative"
        is_georeferenced = False
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                unit = meta.get("unit", "relative")
                is_georeferenced = meta.get("is_georeferenced", False)

        return {
            "status": "success",
            "job_id": job_id,
            "raw_width": W,
            "raw_height": H,
            "grid_width": sub_grid.shape[1],
            "grid_height": sub_grid.shape[0],
            "subsample_stride": stride,
            "unit": unit,
            "is_georeferenced": is_georeferenced,
            "min_elevation": float(np.min(sub_grid)),
            "max_elevation": float(np.max(sub_grid)),
            "mean_elevation": float(np.mean(sub_grid)),
            "elevations": sub_grid.tolist(),
        }
    except Exception as e:
        logger.error(f"Failed to load grid for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Grid extraction failed: {str(e)}")


@app.get("/{full_path:path}")
def catch_all_spa(full_path: str):
    """Fallback SPA router for frontend navigation routes."""
    if full_path.startswith(("api/", "health", "docs", "openapi.json", "outputs/", "static/", "assets/")):
        raise HTTPException(status_code=404, detail="API resource not found")
    index_html = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_html):
        return FileResponse(index_html)
    raise HTTPException(status_code=404, detail="Frontend dist not found")
