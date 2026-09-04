"""
Quantitative evaluation module for Digital Surface Models (DSM).
Calculates RMSE, MAE, AbsRel, delta threshold metrics, peak height errors,
and cross-section height slice profiles.
"""

import logging
import numpy as np
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger("depthwizard.evaluation")


class DSMEvaluator:
    """
    Computes mathematical accuracy metrics comparing estimated DSM against Ground Truth DSM.
    """

    @staticmethod
    def evaluate(
        estimated_dsm: np.ndarray,
        ground_truth_dsm: np.ndarray,
        nodata_val: float = -9999.0,
        mask: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Calculates metric accuracy scores between estimated_dsm and ground_truth_dsm.

        Returns:
            dict containing:
                - rmse: Root Mean Square Error (m)
                - mae: Mean Absolute Error (m)
                - abs_rel: Absolute Relative Difference
                - delta1: % pixels with max(est/gt, gt/est) < 1.25
                - delta2: % pixels with max(est/gt, gt/est) < 1.25^2
                - delta3: % pixels with max(est/gt, gt/est) < 1.25^3
                - peak_error: Maximum absolute height difference (m)
                - mean_bias: Mean signed difference (est - gt) (m)
                - valid_pixel_count: total evaluated pixels
        """
        est = estimated_dsm.astype(np.float32)
        gt = ground_truth_dsm.astype(np.float32)

        if est.shape != gt.shape:
            raise ValueError(f"Shape mismatch: estimated {est.shape} vs GT {gt.shape}")

        # Construct valid data mask
        valid_mask = (
            (gt != nodata_val)
            & (est != nodata_val)
            & ~np.isnan(gt)
            & ~np.isnan(est)
            & ~np.isinf(gt)
            & ~np.isinf(est)
        )

        if mask is not None:
            valid_mask = valid_mask & mask

        est_valid = est[valid_mask]
        gt_valid = gt[valid_mask]

        if est_valid.size == 0:
            raise ValueError("No valid overlapping pixels between estimated and ground truth DSM.")

        # Diff array
        diff = est_valid - gt_valid
        abs_diff = np.abs(diff)

        # 1. RMSE & MAE
        rmse = float(np.sqrt(np.mean(diff**2)))
        mae = float(np.mean(abs_diff))

        # 2. AbsRel
        # Avoid division by zero
        gt_safe = np.where(np.abs(gt_valid) < 1e-3, 1e-3, gt_valid)
        abs_rel = float(np.mean(abs_diff / np.abs(gt_safe)))

        # 3. Delta Threshold Accuracies
        ratio = np.maximum(est_valid / gt_safe, gt_safe / np.where(np.abs(est_valid) < 1e-3, 1e-3, est_valid))
        delta1 = float(np.mean(ratio < 1.25))
        delta2 = float(np.mean(ratio < (1.25**2)))
        delta3 = float(np.mean(ratio < (1.25**3)))

        # 4. Peak Error & Bias
        peak_error = float(np.max(abs_diff))
        mean_bias = float(np.mean(diff))

        results = {
            "rmse": rmse,
            "mae": mae,
            "abs_rel": abs_rel,
            "delta1": delta1,
            "delta2": delta2,
            "delta3": delta3,
            "peak_error": peak_error,
            "mean_bias": mean_bias,
            "valid_pixel_count": int(est_valid.size),
            "gt_min": float(gt_valid.min()),
            "gt_max": float(gt_valid.max()),
            "est_min": float(est_valid.min()),
            "est_max": float(est_valid.max()),
        }

        logger.info(f"DSM Evaluation Complete: RMSE={rmse:.2f}m, MAE={mae:.2f}m, AbsRel={abs_rel:.4f}, Delta1={delta1*100:.1f}%")
        return results

    @staticmethod
    def extract_height_profile(
        estimated_dsm: np.ndarray,
        p1: Tuple[int, int],
        p2: Tuple[int, int],
        ground_truth_dsm: Optional[np.ndarray] = None,
        num_samples: int = 100,
        pixel_resolution: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Extracts cross-section height profile along a 2D line slice from (x1, y1) to (x2, y2).

        Args:
            estimated_dsm: np.ndarray float32 (H, W)
            p1: Tuple (x1, y1) start point
            p2: Tuple (x2, y2) end point
            ground_truth_dsm: Optional np.ndarray float32 (H, W)
            num_samples: int number of points along line
            pixel_resolution: float resolution in meters per pixel

        Returns:
            dict containing:
                - distance: list of distances along slice (meters)
                - est_height: list of estimated heights (meters)
                - gt_height: list of GT heights (meters, or None)
                - coords: list of (x, y) pixel coordinates
        """
        x1, y1 = p1
        x2, y2 = p2

        H, W = estimated_dsm.shape[:2]

        x_coords = np.linspace(x1, x2, num_samples)
        y_coords = np.linspace(y1, y2, num_samples)

        distances = []
        est_heights = []
        gt_heights = [] if ground_truth_dsm is not None else None
        coords = []

        total_length_px = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        for i in range(num_samples):
            px = int(round(x_coords[i]))
            py = int(round(y_coords[i]))

            # Clamp
            px_c = max(0, min(W - 1, px))
            py_c = max(0, min(H - 1, py))

            dist_m = float(i / (num_samples - 1) * total_length_px * pixel_resolution)
            distances.append(dist_m)
            coords.append({"x": px_c, "y": py_c})

            h_est = float(estimated_dsm[py_c, px_c])
            est_heights.append(h_est if not np.isnan(h_est) else 0.0)

            if ground_truth_dsm is not None:
                h_gt = float(ground_truth_dsm[py_c, px_c])
                gt_heights.append(h_gt if not np.isnan(h_gt) else 0.0)

        return {
            "distance": distances,
            "est_height": est_heights,
            "gt_height": gt_heights,
            "coords": coords,
            "num_samples": num_samples,
        }
