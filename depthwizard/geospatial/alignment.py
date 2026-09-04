"""
Raster Alignment & Reprojection Engine.
Verifies CRS matching, performs spatial reprojection, resamples pixel grids,
and masks nodata pixels to ensure comparison on valid overlapping regions.
"""

import logging
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.crs import CRS
from rasterio.transform import Affine
from typing import Tuple, Dict, Any, Optional, Union

logger = logging.getLogger("depthwizard.geospatial.alignment")


def align_rasters(
    estimated_dsm: Union[str, np.ndarray],
    reference_dsm: Union[str, np.ndarray],
    est_metadata: Optional[Dict[str, Any]] = None,
    ref_metadata: Optional[Dict[str, Any]] = None,
    nodata_val: float = -9999.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Verifies CRS, reprojects rasters if necessary, aligns spatial resolution and extent,
    and returns matching arrays comparing ONLY valid overlapping pixels.

    Args:
        estimated_dsm: str file path OR float32 np.ndarray
        reference_dsm: str file path OR float32 np.ndarray
        est_metadata: optional dict containing CRS/transform for estimated array
        ref_metadata: optional dict containing CRS/transform for reference array
        nodata_val: float nodata value

    Returns:
        Tuple[
            aligned_est (np.ndarray float32),
            aligned_ref (np.ndarray float32),
            valid_mask (np.ndarray bool),
            alignment_meta (dict)
        ]
    """
    # 1. Load files if paths provided
    if isinstance(estimated_dsm, str):
        if estimated_dsm.endswith(".npy"):
            est_arr = np.load(estimated_dsm).astype(np.float32)
            est_meta = est_metadata or {}
        else:
            from depthwizard.geospatial.io import GeospatialIO
            est_arr, est_meta = GeospatialIO.read_image(estimated_dsm)
            if est_arr.ndim == 3:
                est_arr = est_arr[:, :, 0].astype(np.float32)
            else:
                est_arr = est_arr.astype(np.float32)
    else:
        est_arr = estimated_dsm.astype(np.float32)
        est_meta = est_metadata or {}

    if isinstance(reference_dsm, str):
        if reference_dsm.endswith(".npy"):
            ref_arr = np.load(reference_dsm).astype(np.float32)
            ref_meta = ref_metadata or {}
        else:
            from depthwizard.geospatial.io import GeospatialIO
            ref_arr, ref_meta = GeospatialIO.read_image(reference_dsm)
            if ref_arr.ndim == 3:
                ref_arr = ref_arr[:, :, 0].astype(np.float32)
            else:
                ref_arr = ref_arr.astype(np.float32)
    else:
        ref_arr = reference_dsm.astype(np.float32)
        ref_meta = ref_metadata or {}

    # Check if spatial metadata is present
    est_crs_str = est_meta.get("crs")
    ref_crs_str = ref_meta.get("crs")
    is_georeferenced = (est_crs_str is not None) and (ref_crs_str is not None)

    aligned_est = est_arr.copy()
    aligned_ref = ref_arr.copy()
    reprojected = False

    # 2. Perform Reprojection if CRS mismatch
    if is_georeferenced and est_crs_str != ref_crs_str:
        logger.info(f"CRS Mismatch detected: Estimated ({est_crs_str}) vs Reference ({ref_crs_str}). Reprojecting...")
        try:
            src_crs = CRS.from_string(est_crs_str)
            dst_crs = CRS.from_string(ref_crs_str)
            src_transform = est_meta.get("transform_affine") or Affine.identity()
            dst_transform = ref_meta.get("transform_affine") or Affine.identity()

            target_shape = ref_arr.shape
            reprojected_est = np.full(target_shape, nodata_val, dtype=np.float32)

            reproject(
                source=est_arr,
                destination=reprojected_est,
                src_transform=src_transform,
                src_crs=src_crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
                src_nodata=nodata_val,
                dst_nodata=nodata_val,
            )

            aligned_est = reprojected_est
            reprojected = True
        except Exception as e:
            logger.warning(f"Spatial reprojection failed: {e}. Falling back to array shape alignment.")

    # 3. Shape / Resolution Resampling if shapes still differ
    if aligned_est.shape != aligned_ref.shape:
        import cv2
        logger.info(f"Resampling raster shapes: {aligned_est.shape} -> {aligned_ref.shape}")
        aligned_est = cv2.resize(aligned_est, (aligned_ref.shape[1], aligned_ref.shape[0]), interpolation=cv2.INTER_LINEAR)

    # 4. Construct Nodata Mask (Compare ONLY valid overlapping pixels)
    valid_mask = (
        (aligned_ref != nodata_val)
        & (aligned_est != nodata_val)
        & ~np.isnan(aligned_ref)
        & ~np.isnan(aligned_est)
        & ~np.isinf(aligned_ref)
        & ~np.isinf(aligned_est)
    )

    alignment_meta = {
        "is_georeferenced": is_georeferenced,
        "est_crs": est_crs_str,
        "ref_crs": ref_crs_str,
        "reprojected": reprojected,
        "aligned_shape": list(aligned_ref.shape),
        "valid_pixel_count": int(valid_mask.sum()),
        "total_pixel_count": int(valid_mask.size),
        "overlap_percentage": float(valid_mask.sum() / valid_mask.size * 100.0),
    }

    logger.info(f"Raster alignment complete. Valid overlapping pixels: {valid_mask.sum()} / {valid_mask.size} ({alignment_meta['overlap_percentage']:.1f}%)")
    return aligned_est, aligned_ref, valid_mask, alignment_meta
