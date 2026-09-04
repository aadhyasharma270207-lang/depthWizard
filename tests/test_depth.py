import numpy as np
import pytest
from depthwizard.models.depth_anything import DepthAnythingPredictor


def test_depth_predictor_init():
    predictor = DepthAnythingPredictor(model_size="base")
    assert predictor.is_loaded is True
    assert predictor.model_size in ["base", "small"]


def test_depth_prediction_output():
    predictor = DepthAnythingPredictor(model_size="small")
    # Synthetic RGB image 128x128
    rgb = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)

    depth = predictor.predict(rgb)
    assert depth.dtype == np.float32
    assert depth.shape == (128, 128)
    assert depth.min() >= 0.0
    assert depth.max() <= 1.0


def test_tiled_inference():
    predictor = DepthAnythingPredictor(model_size="small")
    # Large synthetic image (1200x1200) to trigger tiled inference
    large_rgb = np.random.randint(0, 255, (1200, 1200, 3), dtype=np.uint8)

    depth = predictor.predict(large_rgb, tile_size=512, tile_overlap=128)
    assert depth.dtype == np.float32
    assert depth.shape == (1200, 1200)
