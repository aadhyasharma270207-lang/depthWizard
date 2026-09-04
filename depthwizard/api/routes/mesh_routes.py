"""
3D Mesh Export API Route.
"""

import os
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from depthwizard.mesh.mesh_generator import TerrainMeshGenerator

router = APIRouter()
TEMP_DIR = os.path.join(os.getcwd(), "outputs", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


class MeshRequest(BaseModel):
    session_id: str
    height_exaggeration: Optional[float] = 1.0
    subsample_stride: Optional[int] = 2


@router.post("/generate")
def generate_mesh_endpoint(req: MeshRequest):
    """
    Generates a 3D binary .GLB mesh file for Three.js 3D viewer.
    """
    dsm_path = os.path.join(TEMP_DIR, f"dsm_{req.session_id}.npy")
    if not os.path.exists(dsm_path):
        # Fall back to relative depth
        dsm_path = os.path.join(TEMP_DIR, f"depth_{req.session_id}.npy")
        if not os.path.exists(dsm_path):
            raise HTTPException(status_code=404, detail="Session ID not found.")

    try:
        elevation_grid = np.load(dsm_path)

        # Load RGB texture if exists
        input_img_path = None
        for ext in [".png", ".jpg", ".tif"]:
            candidate = os.path.join(TEMP_DIR, f"input_{req.session_id}{ext}")
            if os.path.exists(candidate):
                input_img_path = candidate
                break

        rgb_texture = None
        if input_img_path:
            img_bgr = cv2.imread(input_img_path)
            if img_bgr is not None:
                rgb_texture = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        mesh = TerrainMeshGenerator.generate_mesh(
            elevation_grid=elevation_grid,
            rgb_texture=rgb_texture,
            height_exaggeration=req.height_exaggeration,
            subsample_stride=req.subsample_stride,
        )

        glb_path = os.path.join(TEMP_DIR, f"mesh_{req.session_id}.glb")
        TerrainMeshGenerator.export_glb(mesh, glb_path)

        return {
            "status": "success",
            "session_id": req.session_id,
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.faces),
            "mesh_glb_url": f"/outputs/temp/mesh_{req.session_id}.glb",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"3D Mesh generation failed: {str(e)}")
