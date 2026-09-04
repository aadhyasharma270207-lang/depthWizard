import os
import tempfile
import numpy as np
import pytest
from depthwizard.datasets.gamus import GAMUSDataset, create_sample_gamus_dataset
from depthwizard.geospatial.alignment import align_rasters
from depthwizard.evaluation.sih_evaluator import SIHEvaluator


def test_gamus_dataset_creation_and_loading():
    with tempfile.TemporaryDirectory() as tmpdir:
        gamus_dir = os.path.join(tmpdir, "gamus")
        create_sample_gamus_dataset(gamus_dir)

        assert os.path.exists(os.path.join(gamus_dir, "metadata.csv"))

        train_ds = GAMUSDataset(data_dir=gamus_dir, split="train")
        val_ds = GAMUSDataset(data_dir=gamus_dir, split="val")

        assert len(train_ds) + len(val_ds) == 4

        sample = train_ds[0]
        assert "image" in sample
        assert "dsm" in sample
        assert "scene_type" in sample
        assert sample["image"].shape[0] == 3
        assert sample["dsm"].shape[0] == 1


def test_align_rasters():
    est = np.random.uniform(10.0, 50.0, (50, 50)).astype(np.float32)
    ref = np.random.uniform(10.0, 50.0, (100, 100)).astype(np.float32)

    aligned_est, aligned_ref, valid_mask, meta = align_rasters(est, ref)

    assert aligned_est.shape == (100, 100)
    assert aligned_ref.shape == (100, 100)
    assert valid_mask.shape == (100, 100)
    assert meta["valid_pixel_count"] == 10000


def test_sih_evaluator_metrics():
    ref = np.linspace(10.0, 50.0, 100, dtype=np.float32)
    est = ref + 3.0  # Constant 3.0m shift

    m = SIHEvaluator.compute_sih_metrics(est, ref)

    assert np.isclose(m["rmse"], 3.0)
    assert np.isclose(m["mae"], 3.0)
    assert np.isclose(m["pearson_r"], 1.0)


def test_sih_batch_evaluation_and_artifacts():
    with tempfile.TemporaryDirectory() as tmpdir:
        sample_results = [
            {
                "name": "urban_01",
                "scene_type": "Urban",
                "est_dsm": np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32),
                "ref_dsm": np.array([[11.0, 21.0], [31.0, 41.0]], dtype=np.float32),
            },
            {
                "name": "hilly_01",
                "scene_type": "Hilly",
                "est_dsm": np.array([[100.0, 200.0], [300.0, 400.0]], dtype=np.float32),
                "ref_dsm": np.array([[105.0, 205.0], [305.0, 405.0]], dtype=np.float32),
            },
        ]

        out_dir = os.path.join(tmpdir, "eval_out")
        res = SIHEvaluator.evaluate_batch_with_scenes(sample_results, output_dir=out_dir)

        assert os.path.exists(res["artifacts"]["evaluation_json"])
        assert os.path.exists(res["artifacts"]["evaluation_csv"])
        assert os.path.exists(res["artifacts"]["error_map"])
        assert os.path.exists(res["artifacts"]["scatter_plot"])
        assert os.path.exists(res["artifacts"]["report_md"])

        assert "Urban" in res["scene_metrics"]
        assert "Hilly" in res["scene_metrics"]
