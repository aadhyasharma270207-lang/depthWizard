"""
Digital Surface Model (DSM) & Relative DSM (rDSM) generation & processing engine.
Includes slope calculation, nodata handling, and metric elevation mapping.
"""

import logging
import numpy as np
import cv2
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("depthwizard.geospatial.dsm")


def generate_rdsm(
    relative_depth: np.ndarray,
    nodata_mask: Optional[np.ndarray] = None,
    percentile_scale: bool = True,
) -> np.ndarray:
    """
    Generates a Relative Digital Surface Model (rDSM) from monocular depth estimation.

    Args:
        relative_depth: np.ndarray float32 relative depth map [0, 1]
        nodata_mask: np.ndarray bool array (True for valid pixels, False for nodata)
        percentile_scale: bool whether to scale using 1st and 99th percentiles for contrast enhancement

    Returns:
        np.ndarray float32 rDSM normalized relative height [0.0, 1.0] (UNITLESS)
    """
    rdsm = relative_depth.copy().astype(np.float32)

    if nodata_mask is None:
        nodata_mask = ~np.isnan(rdsm) & ~np.isinf(rdsm)

    valid_vals = rdsm[nodata_mask]
    if valid_vals.size == 0:
        return rdsm

    if percentile_scale and valid_vals.size > 10:
        p_low = np.percentile(valid_vals, 1)
        p_high = np.percentile(valid_vals, 99)
        if p_high > p_low:
            rdsm[nodata_mask] = np.clip((rdsm[nodata_mask] - p_low) / (p_high - p_low), 0.0, 1.0)
    else:
        min_v = valid_vals.min()
        max_v = valid_vals.max()
        if max_v > min_v:
            rdsm[nodata_mask] = (rdsm[nodata_mask] - min_v) / (max_v - min_v)

    rdsm[~nodata_mask] = 0.0
    return rdsm.astype(np.float32)


def generate_absolute_dsm(
    relative_depth: np.ndarray,
    scale: float,
    offset: float,
    nodata_mask: Optional[np.ndarray] = None,
    nodata_val: float = -9999.0,
) -> np.ndarray:
    """
    Computes metric Absolute DSM using robust linear scale calibration: Z = scale * D + offset.

    Args:
        relative_depth: np.ndarray float32 relative depth map [0, 1]
        scale: float metric scale factor (a)
        offset: float metric offset shift in meters (b)
        nodata_mask: np.ndarray bool array (True for valid pixels)
        nodata_val: float value to assign to invalid pixels

    Returns:
        np.ndarray float32 absolute DSM elevation grid in meters.
    """
    dsm = (scale * relative_depth.astype(np.float32)) + offset

    if nodata_mask is not None:
        dsm[~nodata_mask] = nodata_val
    else:
        invalid_mask = np.isnan(dsm) | np.isinf(dsm)
        dsm[invalid_mask] = nodata_val

    return dsm.astype(np.float32)


def calculate_slope(
    elevation_grid: np.ndarray,
    pixel_size_x: float = 1.0,
    pixel_size_y: float = 1.0,
    nodata_mask: Optional[np.ndarray] = None,
    in_degrees: bool = True,
) -> np.ndarray:
    """
    Calculates surface slope map from elevation grid using Horn's method / spatial gradients.

    Args:
        elevation_grid: np.ndarray float32 elevation grid (m)
        pixel_size_x: float pixel resolution in X (meters)
        pixel_size_y: float pixel resolution in Y (meters)
        nodata_mask: np.ndarray bool array
        in_degrees: bool return slope in degrees if True, else radians

    Returns:
        np.ndarray float32 slope map (degrees or radians).
    """
    grid = elevation_grid.astype(np.float32)

    # Compute spatial gradients dZ/dx and dZ/dy
    dz_dx = cv2.Sobel(grid, cv2.CV_32F, 1, 0, ksize=3) / (8.0 * pixel_size_x)
    dz_dy = cv2.Sobel(grid, cv2.CV_32F, 0, 1, ksize=3) / (8.0 * pixel_size_y)

    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))

    if in_degrees:
        slope = np.degrees(slope_rad)
    else:
        slope = slope_rad

    if nodata_mask is not None:
        slope[~nodata_mask] = 0.0

    return slope.astype(np.float32)
