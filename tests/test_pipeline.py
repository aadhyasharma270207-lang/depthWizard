import os
import tempfile
import cv2
import numpy as np
import pytest
from depthwizard.pipeline import (
    process_image,
    estimate_depth,
    calibrate_depth,
    generate_dsm,
    calculate_slope,
)


def test_pipeline_functions():
    # Synthetic RGB image
    rgb = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)

    # 1. estimate_depth
    rel_depth, meta = estimate_depth(rgb, model_size="small")
    assert rel_depth.shape == (64, 64)

    # 2. calibrate_depth
    scale, offset, cal_meta = calibrate_depth(rel_depth, default_scale=45.0, default_offset=5.0)
    assert scale == 45.0
    assert offset == 5.0

    # 3. generate_dsm
    rdsm, abs_dsm = generate_dsm(rel_depth, scale=scale, offset=offset)
    assert rdsm.shape == (64, 64)
    assert abs_dsm.shape == (64, 64)

    # 4. calculate_slope
    slope = calculate_slope(abs_dsm)
    assert slope.shape == (64, 64)


def test_full_process_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "sample.png")
        out_dir = os.path.join(tmpdir, "output")

        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        cv2.imwrite(input_file, img)

        summary = process_image(
            input_path=input_file,
            output_dir=out_dir,
            model_size="small",
            export_mesh=True,
        )

        assert summary["is_georeferenced"] is False
        assert os.path.exists(summary["outputs"]["rdsm_path"])
        assert os.path.exists(summary["outputs"]["absolute_dsm_path"])
        assert os.path.exists(summary["outputs"]["elevation_preview_path"])
        assert os.path.exists(summary["outputs"]["slope_preview_path"])
        assert os.path.exists(summary["outputs"]["mesh_glb_path"])
        assert os.path.exists(summary["outputs"]["metadata_json_path"])
