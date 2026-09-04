"""
DepthWizard Top-Level Elevation Pipeline API.

Provides clean Python interface functions:
- process_image()
- estimate_depth()
- calibrate_depth()
- generate_dsm()
- calculate_slope()
"""

import os
import json
import time
import logging
import numpy as np
from typing import Dict, Any, Optional, Union, Tuple, List

from depthwizard.models.depth_anything import DepthAnythingPredictor
from depthwizard.geospatial.io import GeospatialIO
from depthwizard.geospatial.dsm import (
    generate_rdsm,
    generate_absolute_dsm,
    calculate_slope as calc_slope_func,
)
from depthwizard.geospatial.colormaps import apply_colormap, save_colormap_preview
from depthwizard.calibration.scale_calibration import ScaleCalibrator
from depthwizard.mesh.mesh_generator import TerrainMeshGenerator

logger = logging.getLogger("depthwizard.pipeline")

# Global singleton predictor instance cache
_GLOBAL_PREDICTOR: Dict[str, DepthAnythingPredictor] = {}


def _get_predictor(model_size: str = "base", device: Optional[str] = None) -> DepthAnythingPredictor:
    """Retrieves or initializes singleton predictor instance."""
    key = f"{model_size}_{device}"
    if key not in _GLOBAL_PREDICTOR:
        _GLOBAL_PREDICTOR[key] = DepthAnythingPredictor(model_size=model_size, device=device)
    return _GLOBAL_PREDICTOR[key]


def estimate_depth(
    image_input: Union[str, np.ndarray],
    model_size: str = "base",
    device: Optional[str] = None,
    tile_size: int = 512,
    tile_overlap: int = 128,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Estimates unitless relative depth map for an RGB image array or file path.

    Args:
        image_input: str path to image/GeoTIFF OR np.ndarray shape (H, W, 3) uint8 RGB
        model_size: str 'base' (default) or 'small' (fallback)
        device: optional PyTorch device ('cuda', 'cpu')
        tile_size: int window size for tiled inference on large images
        tile_overlap: int window overlap for smooth tiled blending

    Returns:
        Tuple[relative_depth (float32 [0.0, 1.0]), metadata (dict)]
        NOTE: relative depth is UNITLESS, not metric elevation (metres).
    """
    start_time = time.time()

    if isinstance(image_input, str):
        rgb_img, metadata = GeospatialIO.read_image(image_input)
    elif isinstance(image_input, np.ndarray):
        rgb_img = image_input
        H, W = rgb_img.shape[:2]
        metadata = {
            "is_georeferenced": False,
            "crs": None,
            "transform": None,
            "resolution": (1.0, 1.0),
            "nodata": None,
            "width": W,
            "height": H,
            "original_shape": (H, W),
        }
    else:
        raise TypeError("image_input must be a file path string or numpy array.")

    predictor = _get_predictor(model_size=model_size, device=device)
    rel_depth = predictor.predict(rgb_img, tile_size=tile_size, tile_overlap=tile_overlap)

    proc_time = float(time.time() - start_time)
    metadata["inference_time_sec"] = proc_time
    metadata["model_used"] = f"Depth Anything V2 ({predictor.model_size})"
    metadata["depth_unit"] = "unitless_relative"

    return rel_depth.astype(np.float32), metadata


def calibrate_depth(
    relative_depth: np.ndarray,
    gcps: Optional[Union[List[Dict[str, float]], str]] = None,
    reference_dem: Optional[np.ndarray] = None,
    transform_affine: Optional[Any] = None,
    default_scale: float = 50.0,
    default_offset: float = 10.0,
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Calibrates unitless relative depth (D) to metric height (Z = a * D + b)
    using Ground Control Points (CSV/List) or a reference DEM / SRTM grid.

    Returns:
        Tuple[scale (a), offset (b), calibration_metadata (dict)]
    """
    if gcps is not None:
        return ScaleCalibrator.calibrate_from_gcps(
            relative_depth=relative_depth,
            gcps=gcps,
            transform_affine=transform_affine,
        )
    elif reference_dem is not None:
        return ScaleCalibrator.calibrate_from_dem(
            relative_depth=relative_depth,
            reference_dem=reference_dem,
        )
    else:
        logger.info(f"No GCPs or reference DEM provided. Using fallback scale={default_scale}, offset={default_offset}")
        metrics = {
            "scale_a": float(default_scale),
            "offset_b": float(default_offset),
            "calibration_mode": "uncalibrated_default",
            "warning": "Relative depth scaled using default parameters. Output is approximate.",
        }
        return float(default_scale), float(default_offset), metrics


def generate_dsm(
    relative_depth: np.ndarray,
    scale: Optional[float] = None,
    offset: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    nodata_val: float = -9999.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates Relative DSM (rDSM) and optional metric Absolute DSM.

    Args:
        relative_depth: float32 relative depth map [0, 1]
        scale: float metric scale factor (a)
        offset: float metric offset shift in meters (b)
        metadata: optional geospatial metadata dict
        nodata_val: float nodata value

    Returns:
        Tuple[rDSM (float32 unitless), absolute_DSM (float32 meters or None)]
    """
    nodata_mask = None
    if metadata and metadata.get("nodata") is not None:
        nd = metadata["nodata"]
        nodata_mask = relative_depth != nd

    rdsm = generate_rdsm(relative_depth, nodata_mask=nodata_mask)

    if scale is not None and offset is not None:
        abs_dsm = generate_absolute_dsm(
            relative_depth=relative_depth,
            scale=scale,
            offset=offset,
            nodata_mask=nodata_mask,
            nodata_val=nodata_val,
        )
    else:
        abs_dsm = None

    return rdsm, abs_dsm


def calculate_slope(
    elevation_grid: np.ndarray,
    pixel_resolution: Tuple[float, float] = (1.0, 1.0),
    in_degrees: bool = True,
) -> np.ndarray:
    """
    Calculates surface slope map from elevation grid.

    Returns:
        np.ndarray float32 slope map (degrees or radians).
    """
    res_x, res_y = pixel_resolution
    return calc_slope_func(
        elevation_grid=elevation_grid,
        pixel_size_x=res_x,
        pixel_size_y=res_y,
        in_degrees=in_degrees,
    )


def process_image(
    input_path: str,
    output_dir: str,
    gcps: Optional[Union[List[Dict[str, float]], str]] = None,
    reference_dem: Optional[np.ndarray] = None,
    model_size: str = "base",
    export_mesh: bool = True,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Complete DepthWizard end-to-end elevation processing pipeline.

    Executes:
    1. Georeference auto-detection & RGB reading.
    2. Depth Anything V2 monocular relative depth estimation.
    3. rDSM (Relative DSM) computation.
    4. GCP / SRTM / DEM metric scale calibration (Z = a*D + b).
    5. Metric Absolute DSM computation & GeoTIFF export (preserving CRS/transform).
    6. Slope map calculation.
    7. Elevation preview rendering (Terrain colormap).
    8. 3D GLB mesh generation.
    9. Export metadata JSON summary.

    Returns:
        Dict containing output file paths, metadata, scale/offset parameters, and statistics.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    # 1. Read input image & spatial metadata
    rgb_image, geo_meta = GeospatialIO.read_image(input_path)

    # 2. Depth Anything V2 relative depth estimation
    rel_depth, depth_meta = estimate_depth(
        image_input=rgb_image,
        model_size=model_size,
        device=device,
    )

    # Merge metadata
    full_meta = {**geo_meta, **depth_meta}

    # 3. Calibration
    is_georeferenced = full_meta["is_georeferenced"]
    affine_trans = full_meta.get("transform_affine")

    if gcps is not None or reference_dem is not None:
        scale_a, offset_b, cal_meta = calibrate_depth(
            relative_depth=rel_depth,
            gcps=gcps,
            reference_dem=reference_dem,
            transform_affine=affine_trans,
        )
    else:
        # Default metric approximation
        scale_a, offset_b, cal_meta = calibrate_depth(
            relative_depth=rel_depth,
            default_scale=50.0,
            default_offset=10.0,
        )

    # 4. Generate rDSM and Absolute DSM
    rdsm, abs_dsm = generate_dsm(
        relative_depth=rel_depth,
        scale=scale_a,
        offset=offset_b,
        metadata=full_meta,
    )

    # 5. Calculate Slope
    res_x, res_y = full_meta.get("resolution", (1.0, 1.0))
    slope_grid = calculate_slope(
        elevation_grid=abs_dsm if abs_dsm is not None else rdsm,
        pixel_resolution=(res_x, res_y),
    )

    # 6. Export Files
    outputs = {}

    # (a) Export rDSM array/GeoTIFF
    rdsm_path = os.path.join(output_dir, f"{base_name}_rDSM.tif" if is_georeferenced else f"{base_name}_rDSM.npy")
    if is_georeferenced:
        GeospatialIO.write_geotiff(rdsm_path, rdsm, full_meta)
    else:
        np.save(rdsm_path, rdsm)
    outputs["rdsm_path"] = rdsm_path

    # (b) Export Absolute DSM GeoTIFF
    dsm_path = os.path.join(output_dir, f"{base_name}_absolute_DSM.tif" if is_georeferenced else f"{base_name}_absolute_DSM.npy")
    if is_georeferenced:
        GeospatialIO.write_geotiff(dsm_path, abs_dsm, full_meta)
    else:
        np.save(dsm_path, abs_dsm)
    outputs["absolute_dsm_path"] = dsm_path

    # (c) Export Elevation Colormap Preview (PNG)
    preview_path = os.path.join(output_dir, f"{base_name}_elevation_preview.png")
    save_colormap_preview(abs_dsm if abs_dsm is not None else rdsm, preview_path, cmap_name="terrain")
    outputs["elevation_preview_path"] = preview_path

    # (d) Export Slope Map (PNG)
    slope_preview_path = os.path.join(output_dir, f"{base_name}_slope_map.png")
    save_colormap_preview(slope_grid, slope_preview_path, cmap_name="inferno")
    outputs["slope_preview_path"] = slope_preview_path

    # (e) Export 3D GLB Mesh
    if export_mesh:
        mesh_obj = TerrainMeshGenerator.generate_mesh(
            elevation_grid=abs_dsm if abs_dsm is not None else rdsm,
            rgb_texture=rgb_image,
            height_exaggeration=1.0,
        )
        glb_path = os.path.join(output_dir, f"{base_name}_3d_mesh.glb")
        TerrainMeshGenerator.export_glb(mesh_obj, glb_path)
        outputs["mesh_glb_path"] = glb_path

    # (f) Metadata JSON
    summary = {
        "input_path": input_path,
        "is_georeferenced": is_georeferenced,
        "crs": full_meta.get("crs"),
        "resolution": list(full_meta.get("resolution", (1.0, 1.0))),
        "width": full_meta.get("width"),
        "height": full_meta.get("height"),
        "scale_a": scale_a,
        "offset_b": offset_b,
        "calibration_info": cal_meta,
        "min_elevation_m": float(np.min(abs_dsm)) if abs_dsm is not None else 0.0,
        "max_elevation_m": float(np.max(abs_dsm)) if abs_dsm is not None else 1.0,
        "mean_elevation_m": float(np.mean(abs_dsm)) if abs_dsm is not None else 0.5,
        "max_slope_deg": float(np.max(slope_grid)),
        "outputs": outputs,
    }

    json_path = os.path.join(output_dir, f"{base_name}_metadata.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    outputs["metadata_json_path"] = json_path

    summary["outputs"] = outputs
    return summary
