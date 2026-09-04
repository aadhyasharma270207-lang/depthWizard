#!/usr/bin/env python
"""
DepthWizard SIH 2026 Automated Smoke & Integration Test Suite.
Verifies backend status, static asset serving, API endpoints, model pipeline, and job output endpoints.
"""

import os
import sys
import io
import json
import logging
from PIL import Image
from fastapi.testclient import TestClient

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set offline test flag for fast deterministic unit execution
os.environ["DEPTHWIZARD_OFFLINE"] = "1"

from depthwizard.api.main import app

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("depthwizard.smoke_test")


def create_sample_png_bytes():
    """Generates a small 64x64 synthetic PNG image for smoke testing."""
    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def run_smoke_test():
    client = TestClient(app)
    results = []

    logger.info("=== Starting DepthWizard System Smoke Test ===")

    # 1. Health Endpoint Test
    try:
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "healthy"
        results.append(("GET /health", "PASS", f"Status: {data.get('status')}, Device: {data.get('device')}"))
    except Exception as e:
        results.append(("GET /health", "FAIL", str(e)))

    # 2. Frontend HTML Root Endpoint Test
    try:
        res = client.get("/")
        assert res.status_code == 200
        content = res.text
        assert "DepthWizard" in content or "app" in content
        results.append(("GET / (Frontend Root)", "PASS", "HTTP 200 OK & index.html rendered"))
    except Exception as e:
        results.append(("GET / (Frontend Root)", "FAIL", str(e)))

    # 3. Static Assets Serving Test
    try:
        frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.exists(assets_dir):
            js_files = [f for f in os.listdir(assets_dir) if f.endswith(".js")]
            if js_files:
                asset_url = f"/assets/{js_files[0]}"
                res = client.get(asset_url)
                assert res.status_code == 200
                results.append((f"GET {asset_url}", "PASS", "Static JS Bundle HTTP 200 OK"))
            else:
                results.append(("GET /assets/*.js", "FAIL", "No .js files found in dist/assets"))
        else:
            results.append(("GET /assets/*.js", "FAIL", "dist/assets directory does not exist"))
    except Exception as e:
        results.append(("GET /assets/*.js", "FAIL", str(e)))

    # 4. OpenAPI Docs Test
    try:
        res = client.get("/docs")
        assert res.status_code == 200
        results.append(("GET /docs (Swagger)", "PASS", "HTTP 200 OK"))
    except Exception as e:
        results.append(("GET /docs (Swagger)", "FAIL", str(e)))

    # 5. Image Upload & Process Pipeline Test
    job_id = None
    try:
        img_bytes = create_sample_png_bytes()
        files = {"file": ("test_sample.png", img_bytes, "image/png")}
        data = {"scale": 50.0, "offset": 10.0}

        res = client.post("/api/process", files=files, data=data)
        assert res.status_code == 200
        res_json = res.json()
        assert res_json.get("status") == "success"
        job_id = res_json.get("job_id")
        results.append(("POST /api/process", "PASS", f"Job ID: {job_id}, Unit: {res_json.get('unit')}"))
    except Exception as e:
        results.append(("POST /api/process", "FAIL", str(e)))

    # 6. Job Outputs Verification
    if job_id:
        endpoints = [
            (f"/api/jobs/{job_id}", "Job Status & Metadata"),
            (f"/api/jobs/{job_id}/preview", "Elevation Preview PNG"),
            (f"/api/jobs/{job_id}/mesh", "3D GLB Terrain Mesh"),
            (f"/api/jobs/{job_id}/metadata", "Metadata JSON"),
        ]
        for url, label in endpoints:
            try:
                res = client.get(url)
                assert res.status_code == 200
                results.append((f"GET {url} ({label})", "PASS", f"HTTP {res.status_code} OK"))
            except Exception as e:
                results.append((f"GET {url} ({label})", "FAIL", str(e)))

    # Display Results Table
    print("\n" + "=" * 80)
    print(f"{'TEST ENDPOINT / COMPONENT':<45} | {'RESULT':<8} | {'DETAILS'}")
    print("=" * 80)
    all_passed = True
    for test, status, detail in results:
        print(f"{test:<45} | {status:<8} | {detail}")
        if status != "PASS":
            all_passed = False
    print("=" * 80 + "\n")

    if all_passed:
        logger.info("🎉 ALL SMOKE TESTS PASSED CLEANLY! SYSTEM IS 100% JUDGE-READY.")
        return 0
    else:
        logger.error("❌ SMOKE TEST FAILED! Check failed endpoints above.")
        return 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())
