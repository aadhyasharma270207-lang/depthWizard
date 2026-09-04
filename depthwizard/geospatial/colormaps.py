"""
Elevation colormap generators for heatmap preview rendering.
Supports Terrain, Viridis, Inferno, Plasma, and Magma palettes.
"""

import numpy as np
import cv2
from PIL import Image
from typing import Optional, Tuple


COLORMAP_MAPPING = {
    "terrain": cv2.COLORMAP_TURBO,
    "viridis": cv2.COLORMAP_VIRIDIS,
    "inferno": cv2.COLORMAP_INFERNO,
    "plasma": cv2.COLORMAP_PLASMA,
    "magma": cv2.COLORMAP_MAGMA,
    "jet": cv2.COLORMAP_JET,
}


def apply_colormap(
    elevation_grid: np.ndarray,
    cmap_name: str = "terrain",
    nodata_mask: Optional[np.ndarray] = None,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> np.ndarray:
    """
    Applies a colormap to a float32 elevation or depth array.

    Args:
        elevation_grid: np.ndarray shape (H, W) float32 array
        cmap_name: str ('terrain', 'viridis', 'inferno', 'plasma', 'magma')
        nodata_mask: np.ndarray shape (H, W) bool array (True for valid, False for nodata)
        min_val: float custom minimum for scale range
        max_val: float custom maximum for scale range

    Returns:
        np.ndarray shape (H, W, 3) uint8 RGB array
    """
    cmap_code = COLORMAP_MAPPING.get(cmap_name.lower(), cv2.COLORMAP_TURBO)
    grid = elevation_grid.copy().astype(np.float32)

    if nodata_mask is not None:
        valid_data = grid[nodata_mask]
    else:
        valid_mask = ~np.isnan(grid) & ~np.isinf(grid)
        valid_data = grid[valid_mask]
        nodata_mask = valid_mask

    if valid_data.size == 0:
        return np.zeros((*grid.shape, 3), dtype=np.uint8)

    v_min = min_val if min_val is not None else float(valid_data.min())
    v_max = max_val if max_val is not None else float(valid_data.max())

    if v_max > v_min:
        norm_grid = np.clip((grid - v_min) / (v_max - v_min) * 255.0, 0, 255).astype(np.uint8)
    else:
        norm_grid = np.zeros_like(grid, dtype=np.uint8)

    # OpenCV applyColorMap expects BGR uint8 image
    bgr_colormap = cv2.applyColorMap(norm_grid, cmap_code)
    rgb_colormap = cv2.cvtColor(bgr_colormap, cv2.COLOR_BGR2RGB)

    # Mask out nodata values with dark grey / black
    if nodata_mask is not None:
        rgb_colormap[~nodata_mask] = [20, 24, 33]

    return rgb_colormap


def save_colormap_preview(
    elevation_grid: np.ndarray,
    output_path: str,
    cmap_name: str = "terrain",
    nodata_mask: Optional[np.ndarray] = None,
) -> str:
    """Saves colormap preview image to disk."""
    rgb = apply_colormap(elevation_grid, cmap_name=cmap_name, nodata_mask=nodata_mask)
    pil_img = Image.fromarray(rgb)
    pil_img.save(output_path)
    return output_path
