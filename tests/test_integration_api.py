import os
import tempfile
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from depthwizard.api.main import app

client = TestClient(app)


def test_unified_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["system"] == "DepthWizard SIH 2026 Backend"


def test_full_job_lifecycle_endpoints():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy image
        img_path = os.path.join(tmpdir, "test.png")
        img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        cv2.imwrite(img_path, img)

        # 1. POST /api/process
        with open(img_path, "rb") as f:
            resp = client.post(
                "/api/process",
                files={"file": ("test.png", f, "image/png")},
                data={"scale": "50.0", "offset": "10.0"},
            )

        assert resp.status_code == 200
        pdata = resp.json()
        assert pdata["status"] == "success"
        job_id = pdata["job_id"]
        assert "elevation_stats" in pdata
        assert "urls" in pdata

        # 2. GET /api/jobs/{job_id}
        resp_job = client.get(f"/api/jobs/{job_id}")
        assert resp_job.status_code == 200
        assert resp_job.json()["job_id"] == job_id

        # 3. GET /api/jobs/{job_id}/dsm
        resp_dsm = client.get(f"/api/jobs/{job_id}/dsm")
        assert resp_dsm.status_code == 200

        # 4. GET /api/jobs/{job_id}/mesh
        resp_mesh = client.get(f"/api/jobs/{job_id}/mesh")
        assert resp_mesh.status_code == 200

        # 5. GET /api/jobs/{job_id}/metadata
        resp_meta = client.get(f"/api/jobs/{job_id}/metadata")
        assert resp_meta.status_code == 200
        assert resp_meta.json()["job_id"] == job_id

        # 6. POST /api/calibrate
        gcps = [{"x": 10, "y": 10, "z": 25.0}, {"x": 30, "y": 30, "z": 45.0}]
        import json
        resp_cal = client.post(
            "/api/calibrate",
            data={"job_id": job_id, "gcps_json": json.dumps(gcps)},
        )
        assert resp_cal.status_code == 200
        assert resp_cal.json()["status"] == "success"

        # 7. POST /api/evaluate
        gt_path = os.path.join(tmpdir, "gt.npy")
        np.save(gt_path, np.full((64, 64), 30.0, dtype=np.float32))
        with open(gt_path, "rb") as f:
            resp_eval = client.post(
                "/api/evaluate",
                data={"job_id": job_id},
                files={"gt_file": ("gt.npy", f, "application/octet-stream")},
            )
        assert resp_eval.status_code == 200
        assert "metrics" in resp_eval.json()
