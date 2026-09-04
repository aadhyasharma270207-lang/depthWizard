"""
Geospatial IO module built on Rasterio & OpenCV.
Handles RGB images (PNG/JPG) and GeoTIFFs with spatial metadata (CRS, transform, bounds, nodata).
"""

import os
import json
import logging
import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS
import cv2
from PIL import Image
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("depthwizard.geospatial.io")


class GeospatialIO:
    """
    Image and GeoTIFF loader/writer that preserves CRS, transform, resolution, and nodata values.
    """

    @staticmethod
    def read_image(file_path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reads an image (GeoTIFF, PNG, JPG) and returns (rgb_array, spatial_metadata).

        Returns:
            rgb_array: np.ndarray shape (H, W, 3) uint8 RGB array
            metadata: dict containing:
                - is_georeferenced (bool)
                - crs (str or None)
                - transform (Affine tuple or None)
                - bounds (tuple or None)
                - resolution (tuple or None)
                - nodata (float/int or None)
                - original_shape (tuple)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext in [".tif", ".tiff", ".geotiff"]:
            return GeospatialIO._read_geotiff(file_path)
        else:
            return GeospatialIO._read_standard_image(file_path)

    @staticmethod
    def _read_geotiff(file_path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reads GeoTIFF using Rasterio."""
        with rasterio.open(file_path) as src:
            is_georeferenced = src.crs is not None and src.transform != Affine.identity()

            metadata = {
                "is_georeferenced": is_georeferenced,
                "crs": src.crs.to_string() if src.crs else None,
                "transform": src.transform.to_gdal() if src.transform else None,
                "transform_affine": src.transform,
                "bounds": tuple(src.bounds) if src.bounds else None,
                "resolution": src.res,
                "nodata": src.nodata,
                "count": src.count,
                "width": src.width,
                "height": src.height,
                "original_shape": (src.height, src.width),
                "driver": src.driver,
            }

            # Read image data
            count = src.count
            if count >= 3:
                # Read first 3 bands as RGB
                r = src.read(1)
                g = src.read(2)
                b = src.read(3)
                img = np.dstack([r, g, b])
            elif count == 1:
                # Single band (grayscale or elevation), convert to 3-channel RGB
                band = src.read(1)
                img = np.dstack([band, band, band])
            else:
                band = src.read(1)
                img = np.dstack([band, band, band])

            # Convert img to uint8 RGB if needed
            if img.dtype != np.uint8:
                valid_mask = img != (src.nodata if src.nodata is not None else -9999)
                if valid_mask.any():
                    min_val = img[valid_mask].min()
                    max_val = img[valid_mask].max()
                    if max_val > min_val:
                        img_norm = np.zeros_like(img, dtype=np.float32)
                        img_norm[valid_mask] = (img[valid_mask] - min_val) / (max_val - min_val) * 255.0
                        img = img_norm.astype(np.uint8)
                    else:
                        img = np.zeros_like(img, dtype=np.uint8)
                else:
                    img = np.zeros_like(img, dtype=np.uint8)

            return img, metadata

    @staticmethod
    def _read_standard_image(file_path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reads standard image file (PNG, JPG, BMP)."""
        pil_img = Image.open(file_path).convert("RGB")
        img = np.array(pil_img, dtype=np.uint8)
        H, W = img.shape[:2]

        metadata = {
            "is_georeferenced": False,
            "crs": None,
            "transform": None,
            "transform_affine": None,
            "bounds": None,
            "resolution": (1.0, 1.0),
            "nodata": None,
            "count": 3,
            "width": W,
            "height": H,
            "original_shape": (H, W),
            "driver": "PNG/JPEG",
        }

        return img, metadata

    @staticmethod
    def write_geotiff(
        output_path: str,
        data_array: np.ndarray,
        metadata: Dict[str, Any],
        nodata: Optional[float] = -9999.0,
        dtype: np.dtype = np.float32,
    ) -> str:
        """
        Writes a float32 DSM array to a GeoTIFF file, preserving CRS, transform, and resolution.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        H, W = data_array.shape[:2]

        crs_val = metadata.get("crs")
        if crs_val and isinstance(crs_val, str):
            crs = CRS.from_string(crs_val)
        else:
            crs = None

        transform_affine = metadata.get("transform_affine")
        if transform_affine is None and metadata.get("transform") is not None:
            gdal_trans = metadata.get("transform")
            transform_affine = Affine.from_gdal(*gdal_trans)
        elif transform_affine is None:
            # Default pixel identity transform
            transform_affine = Affine(1.0, 0.0, 0.0, 0.0, -1.0, float(H))

        out_array = data_array.astype(dtype)

        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=H,
            width=W,
            count=1,
            dtype=dtype,
            crs=crs,
            transform=transform_affine,
            nodata=nodata,
        ) as dst:
            dst.write(out_array, 1)

        logger.info(f"Successfully exported GeoTIFF to {output_path}")
        return output_path
