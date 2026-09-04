import os
import tempfile
import numpy as np
import pytest
from depthwizard.mesh.mesh_generator import TerrainMeshGenerator


def test_mesh_generation_and_export():
    elevation = np.random.uniform(10.0, 50.0, (32, 32)).astype(np.float32)
    mesh = TerrainMeshGenerator.generate_mesh(elevation)

    assert mesh is not None
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0

    with tempfile.TemporaryDirectory() as tmpdir:
        glb_path = os.path.join(tmpdir, "terrain.glb")
        TerrainMeshGenerator.export_glb(mesh, glb_path)
        assert os.path.exists(glb_path)
        assert os.path.getsize(glb_path) > 0
