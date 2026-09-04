import numpy as np
import pytest
from depthwizard.evaluation.dsm_evaluation import DSMEvaluator


def test_dsm_evaluator_metrics():
    gt = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32)
    # Add 2.0m constant error
    est = gt + 2.0

    metrics = DSMEvaluator.evaluate(est, gt)

    assert metrics["rmse"] == 2.0
    assert metrics["mae"] == 2.0
    assert metrics["peak_error"] == 2.0
    assert metrics["mean_bias"] == 2.0
    assert metrics["valid_pixel_count"] == 4


def test_height_profile_extraction():
    H, W = 50, 50
    est_dsm = np.linspace(10.0, 100.0, H * W, dtype=np.float32).reshape((H, W))

    profile = DSMEvaluator.extract_height_profile(
        estimated_dsm=est_dsm,
        p1=(0, 25),
        p2=(49, 25),
        num_samples=10,
    )

    assert len(profile["distance"]) == 10
    assert len(profile["est_height"]) == 10
    assert profile["num_samples"] == 10
