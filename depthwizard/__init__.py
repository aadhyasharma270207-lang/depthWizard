"""
DepthWizard: Single-View Height Estimation, DSM Generation, Scale Calibration, and 3D Flythrough.
"""

from depthwizard.pipeline import (
    process_image,
    estimate_depth,
    calibrate_depth,
    generate_dsm,
    calculate_slope,
)

__version__ = "1.0.0"
__all__ = [
    "process_image",
    "estimate_depth",
    "calibrate_depth",
    "generate_dsm",
    "calculate_slope",
]
