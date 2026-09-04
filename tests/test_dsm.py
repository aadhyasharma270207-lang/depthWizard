import numpy as np
import pytest
from depthwizard.geospatial.dsm import (
    generate_rdsm,
    generate_absolute_dsm,
    calculate_slope,
)


def test_generate_rdsm():
    depth = np.linspace(0.2, 0.8, 100, dtype=np.float32).reshape(10, 10)
    rdsm = generate_rdsm(depth, percentile_scale=False)

    assert rdsm.dtype == np.float32
    assert rdsm.shape == (10, 10)
    assert np.isclose(rdsm.min(), 0.0)
    assert np.isclose(rdsm.max(), 1.0)


def test_generate_absolute_dsm():
    depth = np.array([[0.0, 0.5], [1.0, 0.2]], dtype=np.float32)
    scale = 40.0
    offset = 10.0

    dsm = generate_absolute_dsm(depth, scale=scale, offset=offset)

    expected = np.array([[10.0, 30.0], [50.0, 18.0]], dtype=np.float32)
    assert np.allclose(dsm, expected)


def test_calculate_slope():
    # Inclined plane height = 10 * x
    H, W = 50, 50
    x = np.arange(W, dtype=np.float32)
    y = np.arange(H, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    elevation = xx * 10.0

    slope = calculate_slope(elevation, pixel_size_x=1.0, pixel_size_y=1.0)
    assert slope.dtype == np.float32
    assert slope.shape == (50, 50)
    # Slope of 10m rise per 1m run is arctan(10) ~ 84.29 degrees
    assert slope[25, 25] > 70.0
