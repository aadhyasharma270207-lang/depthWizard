import { renderNavbar } from './components/Navbar.js';
import { Viewer3D } from './components/Viewer3D.js';
import { renderDepthStudio } from './components/DepthStudio.js';
import { renderCalibrationPanel } from './components/CalibrationPanel.js';
import { renderEvaluationDashboard } from './components/EvaluationDashboard.js';
import { runDemoDataset } from './utils/api.js';

document.addEventListener('DOMContentLoaded', () => {
  const appEl = document.getElementById('app');

  // Render Skeleton Layout
  appEl.innerHTML = `
    <div id="navbar-container"></div>
    <main class="main-content">
      <!-- Tab 1: 3D Flythrough Viewer -->
      <div class="tab-panel active" id="tab-viewer">
        <div class="viewer-container">
          <div id="canvas3d"></div>

          <div class="viewer-overlay glass-card">
            <h4 style="font-size: 0.95rem; margin-bottom: 8px;">3D Visualization & Analysis</h4>
            
            <div class="controls-group">
              <label>Flythrough Camera Mode</label>
              <select id="select-camera-mode" class="select-custom">
                <option value="orbit" selected>Orbit Trackball</option>
                <option value="drone">WASD Drone Flythrough</option>
                <option value="topdown">Top-Down Ortho View</option>
                <option value="cinematic">Cinematic Auto-Pilot</option>
              </select>
            </div>

            <div class="controls-group">
              <label>Vertical Exaggeration <span id="val-exagg">1.0x</span></label>
              <input type="range" id="slider-exagg" min="0.1" max="5.0" step="0.1" value="1.0" class="slider-custom">
            </div>

            <div class="controls-group" style="flex-direction: row; justify-content: space-between; align-items: center; margin-top: 6px;">
              <span style="font-size: 0.8rem; color: var(--text-muted);">Wireframe Mode</span>
              <input type="checkbox" id="chk-wireframe">
            </div>

            <div style="display: flex; gap: 8px; margin-top: 10px;">
              <button class="tab-btn" id="btn-reset-cam" style="flex: 1; padding: 6px;">🎯 Reset Cam</button>
              <button class="tab-btn" id="btn-fullscreen" style="flex: 1; padding: 6px;">⛶ Fullscreen</button>
            </div>
          </div>

          <!-- Dynamic Elevation Legend & Scale Indicator -->
          <div style="position: absolute; top: 16px; right: 16px; background: rgba(11, 15, 25, 0.85); backdrop-filter: blur(12px); border: 1px solid var(--glass-border); padding: 12px; border-radius: 10px; z-index: 10; display: flex; flex-direction: column; gap: 8px; width: 220px;">
            <div style="font-size: 0.78rem; font-weight: 600; color: var(--text-muted);">Elevation Color Legend</div>
            <div style="height: 12px; border-radius: 6px; background: linear-gradient(90deg, #440154, #31688e, #35b779, #fde725);"></div>
            <div style="display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 0.72rem; color: var(--accent-cyan);">
              <span>Min: 10m</span>
              <span>Max: 120m</span>
            </div>
            <div style="font-size: 0.72rem; color: var(--text-muted); border-top: 1px solid var(--glass-border); pt-1; margin-top: 4px;">
              📏 Scale Bar: <strong>100 Meters</strong>
            </div>
          </div>

          <!-- Elevation & Slope HUD -->
          <div class="hud-panel">
            <span id="hud-elevation">Hover mouse over 3D terrain to read elevation</span>
            <span id="hud-slope" style="border-left: 1px solid var(--glass-border); padding-left: 12px;">Slope: --°</span>
          </div>
        </div>
      </div>

      <!-- Tab 2: Depth Studio -->
      <div class="tab-panel" id="tab-studio"></div>

      <!-- Tab 3: GCP Calibration -->
      <div class="tab-panel" id="tab-calibration"></div>

      <!-- Tab 4: Accuracy Metrics -->
      <div class="tab-panel" id="tab-evaluation"></div>
    </main>
  `;

  // Initialize 3D Viewer safely with graceful fallback
  let viewer = null;
  try {
    viewer = new Viewer3D('canvas3d');
  } catch (err) {
    console.warn('3D Viewer initialization warning:', err);
    const canvasEl = document.getElementById('canvas3d');
    if (canvasEl) {
      canvasEl.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:var(--text-muted); text-align:center; padding:20px;">
          <div style="font-size:2.5rem; margin-bottom:10px;">🗻</div>
          <div style="font-size:1.1rem; font-weight:600; color:var(--text-main);">DepthWizard 3D Terrain Viewer</div>
          <p style="max-width:420px; font-size:0.85rem; margin-top:8px; color:var(--text-muted);">
            Upload and process a photo or GeoTIFF in the <strong>Depth & DSM Studio</strong> tab to generate your 3D elevation terrain mesh.
          </p>
        </div>
      `;
    }
  }

  // Setup Navbar
  renderNavbar(
    document.getElementById('navbar-container'),
    (tabName) => {
      document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
      document.getElementById(`tab-${tabName}`).classList.add('active');
    },
    async () => {
      // Quick Demo Trigger
      try {
        const demoRes = await runDemoDataset('urban_buildings');
        if (viewer) viewer.loadGLBMesh(demoRes.mesh_glb_url);
        alert('🚀 Quick Demo dataset loaded into 3D Flythrough Viewer!');
      } catch (err) {
        console.error('Demo load error:', err);
      }
    }
  );

  // Render Sub-components
  renderDepthStudio(document.getElementById('tab-studio'), (glbUrl) => {
    if (viewer) viewer.loadGLBMesh(glbUrl);
  });
  renderCalibrationPanel(document.getElementById('tab-calibration'));
  renderEvaluationDashboard(document.getElementById('tab-evaluation'));

  // 3D Controls Bindings
  document.getElementById('select-camera-mode').addEventListener('change', (e) => {
    if (viewer) viewer.setFlyMode(e.target.value);
  });

  document.getElementById('slider-exagg').addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    document.getElementById('val-exagg').innerText = `${val.toFixed(1)}x`;
    if (viewer) viewer.setExaggeration(val);
  });

  document.getElementById('chk-wireframe').addEventListener('change', (e) => {
    if (viewer) viewer.setWireframe(e.target.checked);
  });

  document.getElementById('btn-reset-cam').addEventListener('click', () => {
    if (viewer) viewer.resetCamera();
  });

  document.getElementById('btn-fullscreen').addEventListener('click', () => {
    if (viewer) viewer.toggleFullscreen();
  });
});
