import numpy as np
import pytest
from depthwizard.calibration.scale_calibration import ScaleCalibrator


def test_gcp_calibration():
    # Synthetic relative depth array
    H, W = 100, 100
    rel_depth = np.zeros((H, W), dtype=np.float32)

    # True relation: Z = 60.0 * D + 15.0
    true_scale = 60.0
    true_offset = 15.0

    gcps = [
        {"x": 10, "y": 10, "z": 60.0 * 0.1 + 15.0},
        {"x": 50, "y": 50, "z": 60.0 * 0.5 + 15.0},
        {"x": 80, "y": 80, "z": 60.0 * 0.8 + 15.0},
    ]

    rel_depth[10, 10] = 0.1
    rel_depth[50, 50] = 0.5
    rel_depth[80, 80] = 0.8

    scale, offset, metrics = ScaleCalibrator.calibrate_from_gcps(rel_depth, gcps)

    assert np.isclose(scale, true_scale, atol=1e-1)
    assert np.isclose(offset, true_offset, atol=1e-1)
    assert metrics["sample_count"] == 3


def test_dem_calibration():
    H, W = 50, 50
    rel_depth = np.random.uniform(0.1, 0.9, (H, W)).astype(np.float32)
    ref_dem = 45.0 * rel_depth + 12.0

    scale, offset, metrics = ScaleCalibrator.calibrate_from_dem(rel_depth, ref_dem)

    assert np.isclose(scale, 45.0, atol=1e-1)
    assert np.isclose(offset, 12.0, atol=1e-1)
    assert metrics["dem_rmse"] < 1.0
