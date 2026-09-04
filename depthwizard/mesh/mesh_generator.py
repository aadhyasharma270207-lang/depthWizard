"""
3D Mesh generation module using Trimesh.
Converts 2D DSM elevation grid + RGB texture into textured 3D terrain meshes (GLB/OBJ).
"""

import os
import logging
import numpy as np
import trimesh
from PIL import Image
from typing import Optional, Tuple

logger = logging.getLogger("depthwizard.mesh")


class TerrainMeshGenerator:
    """
    Generates 3D surface meshes from elevation grids for interactive web visualization.
    """

    @staticmethod
    def generate_mesh(
        elevation_grid: np.ndarray,
        rgb_texture: Optional[np.ndarray] = None,
        height_exaggeration: float = 1.0,
        subsample_stride: int = 1,
        max_vertices: int = 50000,
    ) -> trimesh.Trimesh:
        """
        Creates a 3D Trimesh object from an elevation grid.

        Args:
            elevation_grid: np.ndarray float32 (H, W) height array
            rgb_texture: optional np.ndarray uint8 (H, W, 3) image
            height_exaggeration: float vertical scaling factor
            subsample_stride: int pixel subsampling factor
            max_vertices: int maximum target vertex count after simplification

        Returns:
            trimesh.Trimesh object
        """
        grid = elevation_grid[::subsample_stride, ::subsample_stride].astype(np.float32)
        H, W = grid.shape[:2]

        # Handle NaNs
        valid_mask = ~np.isnan(grid) & ~np.isinf(grid)
        if not valid_mask.all():
            min_valid = grid[valid_mask].min() if valid_mask.any() else 0.0
            grid[~valid_mask] = min_valid

        # Create 3D grid vertices (X, Y, Z)
        x = np.linspace(-W / 2.0, W / 2.0, W, dtype=np.float32)
        y = np.linspace(H / 2.0, -H / 2.0, H, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)

        zz = grid * height_exaggeration

        vertices = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])

        # Create UV texture coordinates [0, 1]
        u = np.linspace(0, 1, W, dtype=np.float32)
        v = np.linspace(1, 0, H, dtype=np.float32)
        uu, vv = np.meshgrid(u, v)
        uvs = np.column_stack([uu.ravel(), vv.ravel()])

        # Build triangular face indices
        # Grid indices
        i, j = np.meshgrid(np.arange(H - 1), np.arange(W - 1), indexing="ij")
        v0 = (i * W + j).ravel()
        v1 = (i * W + (j + 1)).ravel()
        v2 = ((i + 1) * W + j).ravel()
        v3 = ((i + 1) * W + (j + 1)).ravel()

        # Two triangles per grid cell
        faces_t1 = np.column_stack([v0, v2, v1])
        faces_t2 = np.column_stack([v1, v2, v3])
        faces = np.vstack([faces_t1, faces_t2])

        # Construct Trimesh
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, visual=None, process=False)
        mesh.visual = trimesh.visual.TextureVisuals(uv=uvs)

        if rgb_texture is not None:
            tex_img = rgb_texture[::subsample_stride, ::subsample_stride]
            pil_tex = Image.fromarray(tex_img)
            mesh.visual.material.image = pil_tex

        # Apply simplification if mesh is too detailed
        if len(mesh.vertices) > max_vertices:
            try:
                target_faces = int(max_vertices * 1.8)
                mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
                logger.info(f"Simplified mesh to {len(mesh.vertices)} vertices.")
            except Exception as e:
                logger.warning(f"Mesh simplification skipped: {e}")

        return mesh

    @staticmethod
    def export_glb(mesh: trimesh.Trimesh, output_path: str) -> str:
        """Exports 3D mesh to GLB binary file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        scene = trimesh.Scene(mesh)
        glb_data = scene.export(file_type="glb")
        with open(output_path, "wb") as f:
            f.write(glb_data)
        logger.info(f"Exported 3D GLB mesh to {output_path}")
        return output_path

    @staticmethod
    def export_obj(mesh: trimesh.Trimesh, output_path: str) -> str:
        """Exports 3D mesh to OBJ file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        mesh.export(output_path, file_type="obj")
        logger.info(f"Exported 3D OBJ mesh to {output_path}")
        return output_path

    @staticmethod
    def export_ply(mesh: trimesh.Trimesh, output_path: str) -> str:
        """Exports 3D mesh to PLY file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        mesh.export(output_path, file_type="ply")
        logger.info(f"Exported 3D PLY mesh to {output_path}")
        return output_path

