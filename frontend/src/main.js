import { renderNavbar } from './components/Navbar.js';
import { Viewer3D } from './components/Viewer3D.js';
import { renderDepthStudio } from './components/DepthStudio.js';
import { renderCalibrationPanel } from './components/CalibrationPanel.js';
import { renderEvaluationDashboard } from './components/EvaluationDashboard.js';
import { runDemoDataset } from './utils/api.js';

document.addEventListener('DOMContentLoaded', () => {
  const appEl = document.getElementById('app');

  // Render Skeleton Layout with Hero 3D Viewport
  appEl.innerHTML = `
    <div id="navbar-container"></div>
    <main class="main-content">
      <!-- Tab 1: 3D Flythrough Hero Viewer -->
      <div class="tab-panel active" id="tab-viewer">
        <div class="viewer-container">
          <div id="canvas3d"></div>

          <!-- Left Floating Glassmorphic 3D Controls Panel -->
          <div class="viewer-controls-panel glass-card" id="controls-panel">
            <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--glass-border); padding-bottom: 8px; margin-bottom: 8px;">
              <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 6px;">
                <span>⚙</span> 3D Terrain Controls
              </h4>
              <button id="btn-toggle-panel" style="background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 1rem;">
                −
              </button>
            </div>

            <div class="panel-body" id="panel-body-content" style="display: flex; flex-direction: column; gap: 10px; max-height: calc(100vh - 160px); overflow-y: auto; padding-right: 4px;">
              
              <!-- Control 1: Vertical Exaggeration -->
              <div class="controls-group">
                <label title="Amplifies elevation differences to make subtle terrain features easier to inspect.">
                  Vertical Exaggeration <span id="val-exagg" style="color: var(--accent-cyan); font-family: var(--font-mono);">1.0x</span>
                </label>
                <input type="range" id="slider-exagg" min="0.5" max="5.0" step="0.1" value="1.0" class="slider-custom">
              </div>

              <!-- Control 2: Mesh Resolution -->
              <div class="controls-group">
                <label title="Controls vertex sampling density of the 3D surface mesh.">Mesh Resolution</label>
                <div style="display: flex; gap: 4px;">
                  <button class="btn-chip" data-res="low">Low (128²)</button>
                  <button class="btn-chip active" data-res="medium">Medium (256²)</button>
                  <button class="btn-chip" data-res="high">High (512²)</button>
                </div>
              </div>

              <!-- Control 3: Color Mode -->
              <div class="controls-group">
                <label>Color & Shading Mode</label>
                <select id="select-color-mode" class="select-custom">
                  <option value="elevation" selected>Elevation Heatmap (Turbo Gradient)</option>
                  <option value="rgb">RGB Aerial Photo Texture</option>
                  <option value="terrain">Terrain DEM Palette (USGS Style)</option>
                  <option value="depth">Grayscale Depth (0-1 Normalized)</option>
                  <option value="solid">Solid Clay (Specular Shaded)</option>
                </select>
              </div>

              <!-- Control 4: Shading Smooth / Flat -->
              <div class="controls-group" style="flex-direction: row; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.8rem; color: var(--text-muted);">Shading Style</span>
                <div style="display: flex; gap: 4px;">
                  <button class="btn-chip active" id="btn-shade-smooth">Smooth</button>
                  <button class="btn-chip" id="btn-shade-flat">Flat</button>
                </div>
              </div>

              <!-- Control 5: Toggles (Wireframe, Contours, Grid) -->
              <div class="controls-group" style="gap: 6px; border-top: 1px solid var(--glass-border); padding-top: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <label for="chk-wireframe" style="margin:0; cursor:pointer;" title="Overlays triangulated mesh edges over shaded surface.">
                    [✓] Wireframe Overlay
                  </label>
                  <input type="checkbox" id="chk-wireframe">
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <label for="chk-contour" style="margin:0; cursor:pointer;" title="Draws contour lines at constant height intervals.">
                    [✓] Contour Iso-lines
                  </label>
                  <input type="checkbox" id="chk-contour">
                </div>

                <div id="contour-options" style="display: none; align-items: center; justify-content: space-between; margin-left: 12px; margin-top: 2px;">
                  <span style="font-size: 0.75rem; color: var(--text-muted);">Interval:</span>
                  <select id="select-contour-interval" class="select-custom" style="padding: 2px 6px; font-size: 0.75rem;">
                    <option value="1">1 meter</option>
                    <option value="5">5 meters</option>
                    <option value="10" selected>10 meters</option>
                    <option value="25">25 meters</option>
                    <option value="50">50 meters</option>
                  </select>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <label for="chk-grid" style="margin:0; cursor:pointer;">[✓] Base Grid Helper</label>
                  <input type="checkbox" id="chk-grid" checked>
                </div>
              </div>

              <!-- Control 6: Preset Cameras -->
              <div class="controls-group" style="border-top: 1px solid var(--glass-border); padding-top: 8px;">
                <label>Camera View Presets</label>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                  <button class="tab-btn" id="btn-cam-reset" style="padding: 6px; font-size: 0.78rem;">🎯 Reset View</button>
                  <button class="tab-btn" id="btn-cam-top" style="padding: 6px; font-size: 0.78rem;">⬆ Top-Down</button>
                  <button class="tab-btn" id="btn-cam-persp" style="padding: 6px; font-size: 0.78rem;">◉ Perspective</button>
                  <button class="tab-btn" id="btn-cam-low" style="padding: 6px; font-size: 0.78rem;">🛸 Low Fly</button>
                </div>
              </div>

              <!-- Control 7: Cinematic Flythrough Auto-Pilot -->
              <div class="controls-group" style="border-top: 1px solid var(--glass-border); padding-top: 8px;">
                <label>Cinematic Flythrough Auto-Pilot</label>
                <div style="display: flex; gap: 4px; margin-top: 4px;">
                  <button class="btn-primary" id="btn-fly-start" style="flex: 1; padding: 6px; font-size: 0.78rem;">▶ Start</button>
                  <button class="tab-btn" id="btn-fly-pause" style="padding: 6px; font-size: 0.78rem;">⏸ Pause</button>
                  <button class="tab-btn" id="btn-fly-stop" style="padding: 6px; font-size: 0.78rem;">⏹ Stop</button>
                </div>
                <div style="display: flex; gap: 4px; margin-top: 4px;">
                  <span style="font-size: 0.75rem; color: var(--text-muted); align-self: center;">Speed:</span>
                  <button class="btn-chip" data-flyspeed="slow">Slow</button>
                  <button class="btn-chip active" data-flyspeed="normal">Normal</button>
                  <button class="btn-chip" data-flyspeed="fast">Fast</button>
                </div>
              </div>

              <!-- Multi-Point Terrain Inspector Box -->
              <div class="controls-group" style="border-top: 1px solid var(--glass-border); padding-top: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <label>Point-to-Point Inspector</label>
                  <button id="btn-clear-points" style="background: transparent; border: none; color: var(--accent-cyan); font-size: 0.75rem; cursor: pointer;">
                    🗑 Clear
                  </button>
                </div>
                <div id="inspector-points-list" style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; border: 1px solid var(--glass-border); min-height: 48px;">
                  Click points on terrain surface to measure distance & elevation delta (ΔZ).
                </div>
              </div>

              <!-- 3D Mesh Quality Metrics Box -->
              <div class="controls-group" style="border-top: 1px solid var(--glass-border); padding-top: 8px;">
                <label>3D Mesh Geometry Quality</label>
                <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent-cyan); background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; border: 1px solid var(--glass-border); display: flex; flex-direction: column; gap: 4px;">
                  <div>Vertices: <strong id="stats-vertices">65,536</strong></div>
                  <div>Triangles: <strong id="stats-faces">130,050</strong></div>
                  <div>Source DSM: <strong id="stats-cells">512 × 512 cells</strong></div>
                </div>
              </div>

              <button class="tab-btn" id="btn-fullscreen" style="padding: 8px; margin-top: 4px;">⛶ Fullscreen Viewport</button>
            </div>
          </div>

          <!-- Dynamic Elevation Color Legend (Top Right) -->
          <div style="position: absolute; top: 16px; right: 16px; background: rgba(11, 15, 25, 0.85); backdrop-filter: blur(16px); border: 1px solid var(--glass-border); padding: 12px; border-radius: 12px; z-index: 10; display: flex; flex-direction: column; gap: 6px; width: 220px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);">
            <div style="font-size: 0.78rem; font-weight: 700; color: var(--text-main);" id="legend-title">RELATIVE DSM (rDSM)</div>
            <div style="height: 12px; border-radius: 6px; background: linear-gradient(90deg, #7f00ff, #31688e, #35b779, #fde725, #ff0000);"></div>
            <div style="display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 0.74rem; color: var(--accent-cyan);">
              <span id="legend-min-elev">Min: 0m</span>
              <span id="legend-max-elev">Max: 100m</span>
            </div>
          </div>

          <!-- Hover Elevation & Slope HUD (Bottom Left) -->
          <div class="hud-panel">
            <span id="hud-elevation">Hover mouse over 3D terrain to read height</span>
            <span id="hud-slope" style="border-left: 1px solid var(--glass-border); padding-left: 12px;">Slope: --°</span>
            <span id="hud-pos" style="border-left: 1px solid var(--glass-border); padding-left: 12px;">X: -- | Z: --</span>
          </div>

          <!-- 3D Orientation & Compass HUD Widget (Bottom Right) -->
          <div style="position: absolute; bottom: 20px; right: 20px; background: rgba(11, 15, 25, 0.85); backdrop-filter: blur(12px); border: 1px solid var(--glass-border); padding: 10px 14px; border-radius: 12px; z-index: 10; display: flex; align-items: center; gap: 14px; font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-main); box-shadow: 0 8px 24px rgba(0,0,0,0.5);">
            <!-- Compass Rose -->
            <div style="display: flex; flex-direction: column; align-items: center;">
              <div style="font-size: 0.65rem; color: var(--accent-cyan); font-weight: 700;">N</div>
              <div id="compass-arrow" style="width: 22px; height: 22px; border-radius: 50%; border: 1px solid var(--accent-cyan); display: flex; align-items: center; justify-content: center; font-size: 0.8rem; transition: transform 0.1s ease;">
                ↑
              </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 2px;">
              <div id="hud-cam-alt">Cam Alt: 220m</div>
              <div>📏 Scale: <strong style="color: var(--accent-cyan);">100 Meters</strong></div>
              <div id="hud-elev-range" style="color: var(--text-muted); font-size: 0.7rem;">Min: 0m | Max: 100m</div>
            </div>
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

    <!-- How To Use Guidance Modal -->
    <div id="how-to-use-modal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); backdrop-filter: blur(8px); z-index: 1000; align-items: center; justify-content: center;">
      <div class="glass-card" style="max-width: 520px; width: 90%; padding: 24px; display: flex; flex-direction: column; gap: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h3 style="font-size: 1.15rem; color: var(--text-main); font-weight: 700;">❓ How to Use DepthWizard</h3>
          <button id="btn-close-modal" style="background: transparent; border: none; color: var(--text-muted); font-size: 1.2rem; cursor: pointer;">✕</button>
        </div>
        <div style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.6; display: flex; flex-direction: column; gap: 10px;">
          <div>1️⃣ <strong>Upload Image / GeoTIFF</strong>: Navigate to <em>Depth & DSM Studio</em> tab and upload any aerial photo or GeoTIFF file.</div>
          <div>2️⃣ <strong>Generate Height & DSM</strong>: Click <em>Process & Generate 3D Terrain</em> to run Depth Anything V2 monocular depth estimation.</div>
          <div>3️⃣ <strong>GCP Calibration</strong>: Apply Ground Control Points (GCPs) or SRTM scale calibration to fit relative depth to metric elevation (Z = a·D + b).</div>
          <div>4️⃣ <strong>Explore 3D Terrain Surface</strong>: Switch to <em>3D Flythrough</em> tab to interactively rotate, pan, measure distances, toggle wireframe, and fly over your terrain!</div>
        </div>
        <button class="btn-primary" id="btn-modal-got-it" style="padding: 10px; font-weight: 700;">Got it!</button>
      </div>
    </div>
  `;

  // Initialize 3D Hero Viewer safely with fallback
  let viewer = null;
  try {
    viewer = new Viewer3D('canvas3d', {
      onPointSelected: (pts) => updateInspectorPointsList(pts),
      onStatsUpdated: (stats) => updateMeshStatsHUD(stats),
    });
  } catch (err) {
    console.warn('3D Hero Viewer initialization warning:', err);
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
        alert('🚀 Quick Demo dataset loaded into 3D Hero Flythrough Viewer!');
      } catch (err) {
        console.error('Demo load error:', err);
      }
    },
    () => {
      // Show How-to-use Modal
      document.getElementById('how-to-use-modal').style.display = 'flex';
    }
  );

  // Render Sub-components
  renderDepthStudio(
    document.getElementById('tab-studio'),
    (meshUrl, resData) => {
      if (viewer) {
        if (resData && resData.urls && resData.urls.mesh) {
          viewer.loadGLBMesh(resData.urls.mesh);
        }
      }
    },
    (meshUrl, resData) => {
      // Switch tab to viewer and load mesh
      document.querySelectorAll('.tab-btn[data-tab]').forEach((b) => b.classList.remove('active'));
      document.querySelector('.tab-btn[data-tab="viewer"]').classList.add('active');

      document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
      document.getElementById('tab-viewer').classList.add('active');

      if (viewer && resData && resData.urls && resData.urls.mesh) {
        viewer.loadGLBMesh(resData.urls.mesh);
      }
    }
  );
  renderCalibrationPanel(document.getElementById('tab-calibration'));
  renderEvaluationDashboard(document.getElementById('tab-evaluation'));

  // Collapsible Left Controls Panel Toggle
  const btnTogglePanel = document.getElementById('btn-toggle-panel');
  const panelBodyContent = document.getElementById('panel-body-content');
  btnTogglePanel.addEventListener('click', () => {
    if (panelBodyContent.style.display === 'none') {
      panelBodyContent.style.display = 'flex';
      btnTogglePanel.innerText = '−';
    } else {
      panelBodyContent.style.display = 'none';
      btnTogglePanel.innerText = '+';
    }
  });

  // Vertical Exaggeration Slider
  document.getElementById('slider-exagg').addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    document.getElementById('val-exagg').innerText = `${val.toFixed(1)}x`;
    if (viewer) viewer.setExaggeration(val);
  });

  // Mesh Resolution Chips
  document.querySelectorAll('.btn-chip[data-res]').forEach((chip) => {
    chip.addEventListener('click', (e) => {
      document.querySelectorAll('.btn-chip[data-res]').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      const res = chip.dataset.res;
      if (viewer) viewer.setMeshResolution(res);
    });
  });

  // Color Mode Dropdown
  document.getElementById('select-color-mode').addEventListener('change', (e) => {
    if (viewer) viewer.setColorMode(e.target.value);
  });

  // Shading Style Smooth / Flat
  document.getElementById('btn-shade-smooth').addEventListener('click', () => {
    document.getElementById('btn-shade-smooth').classList.add('active');
    document.getElementById('btn-shade-flat').classList.remove('active');
    if (viewer) viewer.setShadingMode('smooth');
  });

  document.getElementById('btn-shade-flat').addEventListener('click', () => {
    document.getElementById('btn-shade-flat').classList.add('active');
    document.getElementById('btn-shade-smooth').classList.remove('active');
    if (viewer) viewer.setShadingMode('flat');
  });

  // Toggles
  document.getElementById('chk-wireframe').addEventListener('change', (e) => {
    if (viewer) viewer.setWireframe(e.target.checked);
  });

  const chkContour = document.getElementById('chk-contour');
  const contourOpts = document.getElementById('contour-options');
  chkContour.addEventListener('change', (e) => {
    const enabled = e.target.checked;
    contourOpts.style.display = enabled ? 'flex' : 'none';
    const interval = parseInt(document.getElementById('select-contour-interval').value, 10);
    if (viewer) viewer.setContour(enabled, interval);
  });

  document.getElementById('select-contour-interval').addEventListener('change', (e) => {
    const interval = parseInt(e.target.value, 10);
    if (viewer) viewer.setContour(chkContour.checked, interval);
  });

  document.getElementById('chk-grid').addEventListener('change', (e) => {
    if (viewer) viewer.setGridVisible(e.target.checked);
  });

  // Camera Presets
  document.getElementById('btn-cam-reset').addEventListener('click', () => {
    if (viewer) viewer.resetCamera();
  });
  document.getElementById('btn-cam-top').addEventListener('click', () => {
    if (viewer) viewer.setCameraPreset('topdown');
  });
  document.getElementById('btn-cam-persp').addEventListener('click', () => {
    if (viewer) viewer.setCameraPreset('perspective');
  });
  document.getElementById('btn-cam-low').addEventListener('click', () => {
    if (viewer) viewer.setCameraPreset('lowfly');
  });

  // Cinematic Flythrough Controls
  document.getElementById('btn-fly-start').addEventListener('click', () => {
    const activeChip = document.querySelector('.btn-chip[data-flyspeed].active');
    const speedMode = activeChip ? activeChip.dataset.flyspeed : 'normal';
    if (viewer) viewer.startFlythrough(speedMode);
  });
  document.getElementById('btn-fly-pause').addEventListener('click', () => {
    if (viewer) viewer.pauseFlythrough();
  });
  document.getElementById('btn-fly-stop').addEventListener('click', () => {
    if (viewer) viewer.stopFlythrough();
  });

  document.querySelectorAll('.btn-chip[data-flyspeed]').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.btn-chip[data-flyspeed]').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
    });
  });

  // Clear Multi-point selection
  document.getElementById('btn-clear-points').addEventListener('click', () => {
    if (viewer) viewer.clearSelectedPoints();
  });

  // Fullscreen Viewport
  document.getElementById('btn-fullscreen').addEventListener('click', () => {
    if (viewer) viewer.toggleFullscreen();
  });

  // Close How To Use Modal
  const modal = document.getElementById('how-to-use-modal');
  document.getElementById('btn-close-modal').addEventListener('click', () => {
    modal.style.display = 'none';
  });
  document.getElementById('btn-modal-got-it').addEventListener('click', () => {
    modal.style.display = 'none';
  });
});

/**
 * Multi-Point Distance & Height Inspector List Update
 */
function updateInspectorPointsList(points) {
  const container = document.getElementById('inspector-points-list');
  if (!container) return;

  if (!points || points.length === 0) {
    container.innerHTML = 'Click points on terrain surface to measure distance & elevation delta (ΔZ).';
    return;
  }

  let html = '';
  points.forEach((p, idx) => {
    const letter = String.fromCharCode(65 + idx);
    html += `<div><strong>Point ${letter}</strong>: Elev ${p.elevation.toFixed(1)}m</div>`;
  });

  if (points.length >= 2) {
    const p1 = points[points.length - 2].point;
    const p2 = points[points.length - 1].point;
    const e1 = points[points.length - 2].elevation;
    const e2 = points[points.length - 1].elevation;

    const distM = p1.distanceTo(p2).toFixed(1);
    const deltaZ = (e2 - e1).toFixed(1);
    const sign = deltaZ >= 0 ? '+' : '';

    html += `<div style="border-top: 1px solid var(--glass-border); margin-top: 4px; padding-top: 4px; color: var(--accent-cyan);">
      📏 Dist: <strong>${distM}m</strong> | ΔZ: <strong>${sign}${deltaZ}m</strong>
    </div>`;
  }

  container.innerHTML = html;
}

/**
 * Updates 3D Mesh Quality Statistics in HUD
 */
function updateMeshStatsHUD(stats) {
  const vEl = document.getElementById('stats-vertices');
  const fEl = document.getElementById('stats-faces');
  const cEl = document.getElementById('stats-cells');
  const legendTitle = document.getElementById('legend-title');
  const minL = document.getElementById('legend-min-elev');
  const maxL = document.getElementById('legend-max-elev');
  const rangeHUD = document.getElementById('hud-elev-range');

  if (vEl) vEl.innerText = stats.vertices.toLocaleString();
  if (fEl) fEl.innerText = stats.faces.toLocaleString();
  if (cEl) cEl.innerText = `${stats.sourceCells.toLocaleString()} cells`;

  const isMetric = stats.isCalibrated || stats.unit === 'metres';
  const unitStr = isMetric ? 'm' : ' (rDSM)';

  if (legendTitle) legendTitle.innerText = isMetric ? 'METRIC DSM ELEVATION' : 'RELATIVE DSM (rDSM)';
  if (minL) minL.innerText = `Min: ${stats.minElev.toFixed(2)}${unitStr}`;
  if (maxL) maxL.innerText = `Max: ${stats.maxElev.toFixed(2)}${unitStr}`;
  if (rangeHUD) rangeHUD.innerText = `Min: ${stats.minElev.toFixed(2)}${unitStr} | Max: ${stats.maxElev.toFixed(2)}${unitStr}`;
}
