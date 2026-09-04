"""
Scale and offset calibration module for converting relative depth maps to metric elevation.
Supports Ground Control Point (GCP) CSV inputs and reference DEM / SRTM 30m calibration using RANSAC.
"""

import os
import csv
import logging
import numpy as np
from sklearn.linear_model import RANSACRegressor, LinearRegression, HuberRegressor
from typing import Tuple, List, Dict, Any, Union, Optional

logger = logging.getLogger("depthwizard.calibration")


class ScaleCalibrator:
    """
    Calibrates unitless relative depth predictions (D) to metric elevation (Z)
    using linear regression: Z = scale * D + offset.
    """

    @staticmethod
    def parse_gcp_csv(csv_path: str) -> List[Dict[str, float]]:
        """
        Parses GCP CSV file. Supported columns:
        - pixel_x, pixel_y, elevation (or z, height, ele)
        - x, y, z
        - lon, lat, z (requires spatial transform)
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"GCP CSV file not found: {csv_path}")

        gcps = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Normalize field names to lowercase
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]

            for row in reader:
                row_lower = {k.strip().lower(): v.strip() for k, v in row.items()}

                # Determine X coordinate
                x_val = None
                for col in ["pixel_x", "x", "col", "longitude", "lon"]:
                    if col in row_lower and row_lower[col] != "":
                        x_val = float(row_lower[col])
                        break

                # Determine Y coordinate
                y_val = None
                for col in ["pixel_y", "y", "row", "latitude", "lat"]:
                    if col in row_lower and row_lower[col] != "":
                        y_val = float(row_lower[col])
                        break

                # Determine Z (Elevation) coordinate
                z_val = None
                for col in ["elevation", "z", "height", "ele", "alt", "altitude"]:
                    if col in row_lower and row_lower[col] != "":
                        z_val = float(row_lower[col])
                        break

                if x_val is not None and y_val is not None and z_val is not None:
                    gcps.append({"x": x_val, "y": y_val, "z": z_val})

        logger.info(f"Loaded {len(gcps)} valid GCP points from CSV: {csv_path}")
        return gcps

    @staticmethod
    def calibrate_from_gcps(
        relative_depth: np.ndarray,
        gcps: Union[List[Dict[str, float]], str],
        transform_affine: Optional[Any] = None,
    ) -> Tuple[float, float, Dict[str, Any]]:
        """
        Fits robust linear scale (a) and offset (b) such that Z_metric = a * D + b
        using Ground Control Points.

        Args:
            relative_depth: np.ndarray float32 (H, W) relative depth map
            gcps: list of dicts [{'x': px, 'y': py, 'z': ele}] or path to CSV file
            transform_affine: optional affine transform if GCPs are geographic (lon, lat)

        Returns:
            Tuple[scale (float), offset (float), metrics (dict)]
        """
        if isinstance(gcps, str):
            gcp_list = ScaleCalibrator.parse_gcp_csv(gcps)
        else:
            gcp_list = gcps

        if not gcp_list or len(gcp_list) == 0:
            raise ValueError("No valid GCP points provided for scale calibration.")

        H, W = relative_depth.shape[:2]
        d_sampled = []
        z_true = []

        for pt in gcp_list:
            x_raw, y_raw, z_val = pt["x"], pt["y"], pt["z"]

            # Convert geographic coordinates to pixel coordinates if transform provided
            if transform_affine is not None and (abs(x_raw) <= 180.0 or abs(x_raw) > W):
                try:
                    # Inverse affine transform: (lon, lat) -> (col, row)
                    inv_trans = ~transform_affine
                    col, row = inv_trans * (x_raw, y_raw)
                    px, py = int(round(col)), int(round(row))
                except Exception:
                    px, py = int(round(x_raw)), int(round(y_raw))
            else:
                px, py = int(round(x_raw)), int(round(y_raw))

            # Clamp to image boundaries
            if 0 <= px < W and 0 <= py < H:
                d_val = float(relative_depth[py, px])
                if not np.isnan(d_val) and not np.isinf(d_val):
                    d_sampled.append(d_val)
                    z_true.append(z_val)

        if len(d_sampled) < 1:
            raise ValueError("All GCP points fell outside image bounds or nodata regions.")

        D_arr = np.array(d_sampled, dtype=np.float32).reshape(-1, 1)
        Z_arr = np.array(z_true, dtype=np.float32)

        # Handle flat / zero variance relative depth at sampled GCP locations
        if np.std(D_arr) < 1e-6:
            scale_a = 50.0
            offset_b = float(Z_arr.mean() - 50.0 * D_arr.mean())
            inliers = len(d_sampled)
        elif len(d_sampled) >= 3:
            model = RANSACRegressor(min_samples=2, residual_threshold=10.0, random_state=42)
            try:
                model.fit(D_arr, Z_arr)
                scale_a = float(model.estimator_.coef_[0])
                offset_b = float(model.estimator_.intercept_)
                inliers = int(model.inlier_mask_.sum())
            except Exception:
                lin = LinearRegression().fit(D_arr, Z_arr)
                scale_a = float(lin.coef_[0])
                offset_b = float(lin.intercept_)
                inliers = len(d_sampled)
        else:
            lin = LinearRegression().fit(D_arr, Z_arr)
            scale_a = float(lin.coef_[0])
            offset_b = float(lin.intercept_)
            inliers = len(d_sampled)

        # Evaluate fit error
        z_pred = scale_a * D_arr.ravel() + offset_b
        mae = float(np.mean(np.abs(z_pred - Z_arr)))
        rmse = float(np.sqrt(np.mean((z_pred - Z_arr) ** 2)))

        metrics = {
            "scale_a": scale_a,
            "offset_b": offset_b,
            "sample_count": len(d_sampled),
            "inlier_count": inliers,
            "gcp_mae": mae,
            "gcp_rmse": rmse,
        }

        logger.info(f"GCP Calibration successful: Z = {scale_a:.4f} * D + {offset_b:.4f} (RMSE: {rmse:.2f}m)")
        return scale_a, offset_b, metrics

    @staticmethod
    def calibrate_from_dem(
        relative_depth: np.ndarray,
        reference_dem: np.ndarray,
        dem_nodata: float = -9999.0,
        sample_stride: int = 10,
    ) -> Tuple[float, float, Dict[str, Any]]:
        """
        Fits linear scale & offset using reference DEM / SRTM elevation grid.

        Args:
            relative_depth: np.ndarray float32 (H, W) relative depth map
            reference_dem: np.ndarray float32 (H, W) true metric elevation grid
            dem_nodata: float nodata value in reference DEM
            sample_stride: int sub-sampling stride to speed up fitting

        Returns:
            Tuple[scale (float), offset (float), metrics (dict)]
        """
        if relative_depth.shape != reference_dem.shape:
            raise ValueError(
                f"Shape mismatch between depth {relative_depth.shape} and DEM {reference_dem.shape}"
            )

        # Sample valid pixels
        valid_mask = (reference_dem != dem_nodata) & ~np.isnan(reference_dem) & ~np.isnan(relative_depth)
        
        # Subsample grid
        sub_mask = np.zeros_like(valid_mask, dtype=bool)
        sub_mask[::sample_stride, ::sample_stride] = True
        final_mask = valid_mask & sub_mask

        D_samples = relative_depth[final_mask].astype(np.float32).reshape(-1, 1)
        Z_samples = reference_dem[final_mask].astype(np.float32)

        if len(Z_samples) < 5:
            raise ValueError("Insufficient valid reference DEM pixels for calibration.")

        # Fit Huber robust regressor to ignore outliers
        reg = HuberRegressor().fit(D_samples, Z_samples)
        scale_a = float(reg.coef_[0])
        offset_b = float(reg.intercept_)

        z_pred = scale_a * D_samples.ravel() + offset_b
        rmse = float(np.sqrt(np.mean((z_pred - Z_samples) ** 2)))
        mae = float(np.mean(np.abs(z_pred - Z_samples)))

        metrics = {
            "scale_a": scale_a,
            "offset_b": offset_b,
            "sample_count": len(Z_samples),
            "dem_mae": mae,
            "dem_rmse": rmse,
        }

        logger.info(f"DEM Calibration successful: Z = {scale_a:.4f} * D + {offset_b:.4f} (RMSE: {rmse:.2f}m)")
        return scale_a, offset_b, metrics
