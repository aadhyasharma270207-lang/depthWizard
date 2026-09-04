"""
Official SIH Evaluation Engine.
Computes non-hardcoded RMSE, MAE, and Pearson Correlation metrics,
generates scene-type breakdowns (Urban, Sparse, Hilly, Forested),
and exports evaluation.json, evaluation.csv, error maps, scatter plots, and markdown reports.
"""

import os
import json
import csv
import logging
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server export
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("depthwizard.evaluation.sih")


class SIHEvaluator:
    """
    SIH 2026 Official Evaluation Engine for Monocular Elevation Models.
    Calculates exact RMSE, MAE, and Pearson correlation metrics without hardcoding.
    """

    @staticmethod
    def compute_sih_metrics(
        est_dsm: np.ndarray,
        ref_dsm: np.ndarray,
        valid_mask: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Calculates exact RMSE, MAE, and Pearson correlation coefficient (r).
        """
        if valid_mask is None:
            valid_mask = (
                ~np.isnan(est_dsm)
                & ~np.isnan(ref_dsm)
                & ~np.isinf(est_dsm)
                & ~np.isinf(ref_dsm)
            )

        est_val = est_dsm[valid_mask].astype(np.float64)
        ref_val = ref_dsm[valid_mask].astype(np.float64)

        if est_val.size == 0:
            return {
                "error": "Reference DSM/LiDAR required for quantitative evaluation.",
                "rmse": None,
                "mae": None,
                "pearson_r": None,
                "valid_pixel_count": 0,
            }

        diff = est_val - ref_val
        abs_diff = np.abs(diff)

        # 1. RMSE & MAE
        rmse = float(np.sqrt(np.mean(diff**2)))
        mae = float(np.mean(abs_diff))

        # 2. Pearson Correlation Coefficient (r)
        if est_val.size >= 2 and np.std(est_val) > 1e-6 and np.std(ref_val) > 1e-6:
            r_val, _ = pearsonr(est_val, ref_val)
            pearson_r = float(r_val)
        else:
            pearson_r = 0.0

        return {
            "rmse": rmse,
            "mae": mae,
            "pearson_r": pearson_r,
            "valid_pixel_count": int(est_val.size),
            "est_min": float(est_val.min()),
            "est_max": float(est_val.max()),
            "ref_min": float(ref_val.min()),
            "ref_max": float(ref_val.max()),
        }

    @staticmethod
    def evaluate_batch_with_scenes(
        sample_results: List[Dict[str, Any]],
        output_dir: str,
    ) -> Dict[str, Any]:
        """
        Evaluates a collection of samples with scene labels (Urban, Sparse, Hilly, Forested)
        and exports all required SIH artifacts.
        """
        os.makedirs(output_dir, exist_ok=True)

        overall_est = []
        overall_ref = []
        scene_buckets: Dict[str, Dict[str, List]] = {
            "Urban": {"est": [], "ref": []},
            "Sparse": {"est": [], "ref": []},
            "Hilly": {"est": [], "ref": []},
            "Forested": {"est": [], "ref": []},
        }

        csv_rows = []

        for sample in sample_results:
            est_arr = sample["est_dsm"]
            ref_arr = sample["ref_dsm"]
            v_mask = sample.get("valid_mask")
            scene_type = sample.get("scene_type", "Urban")
            name = sample.get("name", "sample")

            if v_mask is None:
                v_mask = ~np.isnan(est_arr) & ~np.isnan(ref_arr)

            m = SIHEvaluator.compute_sih_metrics(est_arr, ref_arr, v_mask)

            csv_rows.append({
                "sample_name": name,
                "scene_type": scene_type,
                "rmse_m": f"{m['rmse']:.4f}" if m.get("rmse") is not None else "N/A",
                "mae_m": f"{m['mae']:.4f}" if m.get("mae") is not None else "N/A",
                "pearson_r": f"{m['pearson_r']:.4f}" if m.get("pearson_r") is not None else "N/A",
                "valid_pixels": m.get("valid_pixel_count", 0),
            })

            if m.get("rmse") is not None:
                est_v = est_arr[v_mask]
                ref_v = ref_arr[v_mask]
                overall_est.extend(est_v)
                overall_ref.extend(ref_v)

                if scene_type in scene_buckets:
                    scene_buckets[scene_type]["est"].extend(est_v)
                    scene_buckets[scene_type]["ref"].extend(ref_v)

        # Compute aggregate overall & scene metrics
        overall_est_arr = np.array(overall_est, dtype=np.float32)
        overall_ref_arr = np.array(overall_ref, dtype=np.float32)

        if overall_est_arr.size > 0:
            overall_metrics = SIHEvaluator.compute_sih_metrics(overall_est_arr, overall_ref_arr)
        else:
            overall_metrics = {
                "message": "Reference DSM/LiDAR required for quantitative evaluation.",
                "rmse": None,
                "mae": None,
                "pearson_r": None,
            }

        scene_metrics = {}
        for stype, bucket in scene_buckets.items():
            if bucket["est"]:
                e_arr = np.array(bucket["est"], dtype=np.float32)
                r_arr = np.array(bucket["ref"], dtype=np.float32)
                scene_metrics[stype] = SIHEvaluator.compute_sih_metrics(e_arr, r_arr)
            else:
                scene_metrics[stype] = {"sample_count": 0, "status": "No data available"}

        # 1. Export evaluation.json
        eval_json_path = os.path.join(output_dir, "evaluation.json")
        json_content = {
            "overall_sih_metrics": overall_metrics,
            "scene_type_breakdown": scene_metrics,
            "sample_count": len(sample_results),
        }
        with open(eval_json_path, "w", encoding="utf-8") as f:
            json.dump(json_content, f, indent=2)

        # 2. Export evaluation.csv
        eval_csv_path = os.path.join(output_dir, "evaluation.csv")
        with open(eval_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["sample_name", "scene_type", "rmse_m", "mae_m", "pearson_r", "valid_pixels"])
            writer.writeheader()
            writer.writerows(csv_rows)

        # 3. Export Error Map & Scatter Plot
        error_map_path = os.path.join(output_dir, "error_map.png")
        scatter_plot_path = os.path.join(output_dir, "scatter_plot.png")

        if sample_results:
            # Generate Error Map for first sample
            s0 = sample_results[0]
            err_arr = np.abs(s0["est_dsm"] - s0["ref_dsm"])
            if s0.get("valid_mask") is not None:
                err_arr[~s0["valid_mask"]] = 0.0

            from depthwizard.geospatial.colormaps import save_colormap_preview
            save_colormap_preview(err_arr, error_map_path, cmap_name="inferno")

        if overall_est_arr.size > 0:
            plt.figure(figsize=(7, 6))
            sub_idx = np.random.choice(overall_est_arr.size, size=min(2000, overall_est_arr.size), replace=False)
            plt.scatter(overall_ref_arr[sub_idx], overall_est_arr[sub_idx], alpha=0.4, c="#00f2fe", edgecolors="none", s=15)
            
            min_val = min(overall_ref_arr[sub_idx].min(), overall_est_arr[sub_idx].min())
            max_val = max(overall_ref_arr[sub_idx].max(), overall_est_arr[sub_idx].max())
            plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='1:1 Ideal Line')
            
            plt.title("Ground Truth vs Estimated DSM Elevation (m)", fontsize=11)
            plt.xlabel("Reference Elevation (m)")
            plt.ylabel("DepthWizard Estimated Elevation (m)")
            plt.legend()
            plt.grid(True, linestyle=":", alpha=0.6)
            plt.tight_layout()
            plt.savefig(scatter_plot_path, dpi=150)
            plt.close()

        # 4. Export Markdown Report
        report_md_path = os.path.join(output_dir, "evaluation_report.md")
        SIHEvaluator._write_markdown_report(report_md_path, json_content)

        return {
            "overall_metrics": overall_metrics,
            "scene_metrics": scene_metrics,
            "artifacts": {
                "evaluation_json": eval_json_path,
                "evaluation_csv": eval_csv_path,
                "error_map": error_map_path,
                "scatter_plot": scatter_plot_path,
                "report_md": report_md_path,
            },
        }

    @staticmethod
    def _write_markdown_report(path: str, data: Dict[str, Any]):
        ov = data.get("overall_sih_metrics", {})
        sc = data.get("scene_type_breakdown", {})

        with open(path, "w", encoding="utf-8") as f:
            f.write("# SIH 2026 Elevation Model Evaluation Report\n\n")
            f.write("## 1. Overall Performance Metrics\n\n")
            if ov.get("rmse") is not None:
                f.write(f"- **RMSE (Root Mean Square Error)**: {ov['rmse']:.4f} m\n")
                f.write(f"- **MAE (Mean Absolute Error)**: {ov['mae']:.4f} m\n")
                f.write(f"- **Pearson Correlation (r)**: {ov['pearson_r']:.4f}\n")
                f.write(f"- **Evaluated Overlapping Pixels**: {ov['valid_pixel_count']:,}\n\n")
            else:
                f.write("> [!WARNING]\n")
                f.write("> **Reference DSM/LiDAR required for quantitative evaluation.**\n\n")

            f.write("## 2. Accuracy Breakdown by Scene Type\n\n")
            f.write("| Scene Type | RMSE (m) | MAE (m) | Pearson r | Status |\n")
            f.write("|---|---|---|---|---|\n")
            for stype in ["Urban", "Sparse", "Hilly", "Forested"]:
                info = sc.get(stype, {})
                if info.get("rmse") is not None:
                    f.write(f"| {stype} | {info['rmse']:.4f} | {info['mae']:.4f} | {info['pearson_r']:.4f} | Validated |\n")
                else:
                    f.write(f"| {stype} | N/A | N/A | N/A | No Data |\n")
