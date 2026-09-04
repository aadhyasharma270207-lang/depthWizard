import os
import tempfile
import numpy as np
import pytest
from depthwizard.geospatial.io import GeospatialIO
from rasterio.transform import Affine


def test_geospatial_write_read_geotiff():
    with tempfile.TemporaryDirectory() as tmpdir:
        tif_path = os.path.join(tmpdir, "test_elevation.tif")

        # Create dummy elevation array
        H, W = 64, 64
        elevation_data = np.linspace(10.0, 100.0, H * W, dtype=np.float32).reshape((H, W))

        meta = {
            "is_georeferenced": True,
            "crs": "EPSG:4326",
            "transform": (10.0, 0.01, 0.0, 50.0, 0.0, -0.01),
            "transform_affine": Affine(0.01, 0.0, 10.0, 0.0, -0.01, 50.0),
            "nodata": -9999.0,
        }

        # Write GeoTIFF
        GeospatialIO.write_geotiff(tif_path, elevation_data, meta)
        assert os.path.exists(tif_path)

        # Read back GeoTIFF
        read_img, read_meta = GeospatialIO.read_image(tif_path)
        assert read_meta["is_georeferenced"] is True
        assert read_meta["crs"] == "EPSG:4326"
        assert read_meta["width"] == 64
        assert read_meta["height"] == 64
