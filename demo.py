#!/usr/bin/env python
"""
DepthWizard SIH 2026 Launcher & Demonstration Script.

Usage:
  python demo.py                  Launch complete integrated application on http://127.0.0.1:8000
  python demo.py --cli            Run end-to-end elevation processing CLI benchmark
  python demo.py --serve          Launch FastAPI server on http://127.0.0.1:8000
  python demo.py --generate-demo  Generate benchmark demo datasets
"""

import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("depthwizard.demo")


def run_server():
    """Launches FastAPI Uvicorn Server serving both API & Web Frontend on one URL."""
    logger.info("=================================================================")
    logger.info("           DEPTHWIZARD SIH 2026 INTEGRATED SYSTEM                ")
    logger.info("=================================================================")
    logger.info("🚀 Launching DepthWizard Application Server...")
    logger.info("🌐 Web Application & API available at:  http://127.0.0.1:8000")
    logger.info("📖 Interactive API Documentation at:     http://127.0.0.1:8000/docs")
    logger.info("=================================================================\n")

    import uvicorn
    uvicorn.run("depthwizard.api.main:app", host="127.0.0.1", port=8000, reload=False)


def run_cli_demo():
    """Executes end-to-end CLI workflow demonstration."""
    logger.info("=== DepthWizard SIH 2026 CLI Demonstration ===")
    from depthwizard.api.routes.demo_routes import ensure_demo_dataset
    from depthwizard.pipeline import process_image
    from depthwizard.evaluation.dsm_evaluation import DSMEvaluator
    import numpy as np

    # Ensure synthetic dataset is generated
    ensure_demo_dataset()

    input_img = os.path.join("demo_data", "urban_buildings.png")
    out_dir = os.path.join("outputs", "cli_demo")
    gt_dsm_file = os.path.join("demo_data", "urban_gt_dsm.npy")

    gcps = [
        {"x": 150, "y": 150, "z": 45.0},
        {"x": 350, "y": 240, "z": 68.0},
        {"x": 256, "y": 400, "z": 85.0},
        {"x": 30, "y": 30, "z": 15.0},
    ]

    logger.info(f"Processing input photo: {input_img}")
    summary = process_image(
        input_path=input_img,
        output_dir=out_dir,
        gcps=gcps,
        model_size="base",
        export_mesh=True,
    )

    logger.info("\n--- Pipeline Summary ---")
    logger.info(f"Is Georeferenced: {summary['is_georeferenced']}")
    logger.info(f"Fitted Scale (a): {summary['scale_a']:.4f}")
    logger.info(f"Fitted Offset (b): {summary['offset_b']:.4f} meters")
    logger.info(f"Elevation Range: {summary['min_elevation_m']:.2f}m to {summary['max_elevation_m']:.2f}m")
    logger.info(f"Max Slope: {summary['max_slope_deg']:.2f} degrees")

    # Evaluate against synthetic Ground Truth DSM
    if os.path.exists(gt_dsm_file) and os.path.exists(summary["outputs"]["absolute_dsm_path"]):
        gt_dsm = np.load(gt_dsm_file)
        est_dsm = np.load(summary["outputs"]["absolute_dsm_path"])

        metrics = DSMEvaluator.evaluate(est_dsm, gt_dsm)
        logger.info("\n--- Quantitative Accuracy Metrics ---")
        logger.info(f"Root Mean Square Error (RMSE): {metrics['rmse']:.2f} m")
        logger.info(f"Mean Absolute Error (MAE):     {metrics['mae']:.2f} m")
        logger.info(f"AbsRel Error:                  {metrics['abs_rel']:.4f}")
        logger.info(f"Threshold Accuracy (δ < 1.25): {metrics['delta1']*100:.1f}%")
        logger.info(f"Peak Error:                    {metrics['peak_error']:.2f} m")

    logger.info("\n--- Exported Output Artifacts ---")
    for k, v in summary["outputs"].items():
        logger.info(f"  {k:22s}: {v}")

    logger.info("\nCLI Demo finished successfully!")


def main():
    parser = argparse.ArgumentParser(description="DepthWizard SIH 2026 Launcher")
    parser.add_argument("--cli", action="store_true", help="Run end-to-end CLI demonstration")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI backend server")
    parser.add_argument("--generate-demo", action="store_true", help="Generate benchmark demo datasets")

    args = parser.parse_args()

    if args.cli:
        run_cli_demo()
    elif args.generate_demo:
        from depthwizard.api.routes.demo_routes import ensure_demo_dataset
        ensure_demo_dataset()
        logger.info("Demo datasets successfully created in demo_data/")
    else:
        run_server()


if __name__ == "__main__":
    main()
