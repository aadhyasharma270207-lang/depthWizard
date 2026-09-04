#!/usr/bin/env python
"""
SIH Official Evaluation Script.
Evaluates monocular elevation predictions against reference DSM/LiDAR/DEM rasters
across scene types (Urban, Sparse, Hilly, Forested).

Usage:
  python scripts/evaluate.py --data-dir demo_data/gamus --output-dir outputs/sih_evaluation
"""

import os
import sys
import argparse
import logging
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from depthwizard.datasets.gamus import GAMUSDataset
from depthwizard.pipeline import process_image
from depthwizard.geospatial.alignment import align_rasters
from depthwizard.evaluation.sih_evaluator import SIHEvaluator

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("depthwizard.evaluate")


def run_sih_evaluation(data_dir: str, output_dir: str, model_size: str = "base"):
    """Executes official SIH quantitative evaluation against benchmark ground truth rasters."""
    logger.info(f"=== SIH 2026 Quantitative Evaluation on GAMUS Benchmark ({data_dir}) ===")
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(data_dir):
        logger.warning(f"Reference data directory '{data_dir}' not found.")
        logger.warning("Reference DSM/LiDAR required for quantitative evaluation.")
        print("\nReference DSM/LiDAR required for quantitative evaluation.\n")
        return

    # Load validation split of GAMUS dataset
    try:
        val_dataset = GAMUSDataset(data_dir=data_dir, split="val", val_ratio=0.5)
        if len(val_dataset) == 0:
            val_dataset = GAMUSDataset(data_dir=data_dir, split="train")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        logger.warning("Reference DSM/LiDAR required for quantitative evaluation.")
        print("\nReference DSM/LiDAR required for quantitative evaluation.\n")
        return

    sample_results = []
    temp_out = os.path.join(output_dir, "temp_proc")

    for i in range(len(val_dataset)):
        sample = val_dataset[i]
        img_path = sample["image_path"]
        ref_path = sample["dsm_path"]
        scene_type = sample["scene_type"]
        sample_name = os.path.splitext(os.path.basename(img_path))[0]

        logger.info(f"[{i+1}/{len(val_dataset)}] Evaluating {sample_name} (Scene: {scene_type})...")

        # 1. Run pipeline processing
        summary = process_image(
            input_path=img_path,
            output_dir=os.path.join(temp_out, sample_name),
            model_size=model_size,
            export_mesh=False,
        )

        est_dsm_path = summary["outputs"]["absolute_dsm_path"]

        # 2. Verify CRS, align rasters, reproject if needed, and mask nodata
        aligned_est, aligned_ref, valid_mask, align_meta = align_rasters(
            estimated_dsm=est_dsm_path,
            reference_dsm=ref_path,
        )

        sample_results.append({
            "name": sample_name,
            "scene_type": scene_type,
            "est_dsm": aligned_est,
            "ref_dsm": aligned_ref,
            "valid_mask": valid_mask,
            "alignment_meta": align_meta,
        })

    # 3. Compute aggregate SIH metrics and export artifacts
    res = SIHEvaluator.evaluate_batch_with_scenes(sample_results, output_dir=output_dir)

    ov = res["overall_metrics"]
    logger.info("\n=======================================================")
    logger.info("             SIH 2026 EVALUATION RESULTS               ")
    logger.info("=======================================================")
    if ov.get("rmse") is not None:
        logger.info(f"Overall RMSE:              {ov['rmse']:.4f} m")
        logger.info(f"Overall MAE:               {ov['mae']:.4f} m")
        logger.info(f"Pearson Correlation (r):   {ov['pearson_r']:.4f}")
        logger.info(f"Evaluated Overlapping Pix: {ov['valid_pixel_count']:,}")
    else:
        logger.warning("Reference DSM/LiDAR required for quantitative evaluation.")
        print("\nReference DSM/LiDAR required for quantitative evaluation.\n")

    logger.info("\n--- Generated Artifacts ---")
    for k, path in res["artifacts"].items():
        logger.info(f"  {k:16s}: {path}")

    logger.info("\nEvaluation finished successfully!")


def main():
    parser = argparse.ArgumentParser(description="SIH 2026 Elevation Model Evaluation")
    parser.add_argument("--data-dir", default="demo_data/gamus", help="Path to reference GAMUS dataset directory")
    parser.add_argument("--output-dir", default="outputs/sih_evaluation", help="Directory to save evaluation artifacts")
    parser.add_argument("--model-size", default="base", help="Depth Anything V2 variant ('base' or 'small')")

    args = parser.parse_args()
    run_sih_evaluation(data_dir=args.data_dir, output_dir=args.output_dir, model_size=args.model_size)


if __name__ == "__main__":
    main()
