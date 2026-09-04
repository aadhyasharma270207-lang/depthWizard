import { processImage } from '../utils/api.js';

export function renderDepthStudio(container, onJobComplete, onViewMeshClicked) {
  container.innerHTML = `
    <div class="studio-layout">
      <div class="studio-sidebar glass-card">
        <h3 style="font-size: 1.05rem; margin-bottom: 12px; color: var(--text-main); font-weight: 700;">
          📷 Satellite & Aerial Image Workbench
        </h3>
        
        <div class="controls-group">
          <label>Select RGB Photo / GeoTIFF Tile <span style="color: var(--accent-cyan);">*</span></label>
          <input type="file" id="file-input" accept=".png,.jpg,.jpeg,.tif,.tiff" class="select-custom" style="padding: 8px;">
        </div>

        <div class="controls-group">
          <label>Scale Calibration Factor (a) <span style="font-family: var(--font-mono);">Z = a·D + b</span></label>
          <input type="number" id="scale-input" value="50.0" step="0.5" class="select-custom">
        </div>

        <div class="controls-group">
          <label>Elevation Shift Offset (b) [meters]</label>
          <input type="number" id="offset-input" value="10.0" step="0.5" class="select-custom">
        </div>

        <button class="btn-primary" id="btn-process" style="margin-top: 12px; padding: 12px; font-weight: 700;">
          ⚡ Process & Generate 3D Terrain Mesh
        </button>

        <div id="studio-status-box" style="margin-top: 12px; display: none; padding: 12px; background: rgba(0,0,0,0.4); border-radius: 8px; border: 1px solid var(--glass-border);">
          <div style="font-size: 0.78rem; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">Processing Pipeline Status</div>
          <div id="studio-status-steps" style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--accent-cyan); line-height: 1.5;"></div>
        </div>

        <button class="btn-primary" id="btn-view-3d-hero" style="display: none; margin-top: 12px; padding: 12px; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));">
          🗻 Explore 3D Terrain Surface →
        </button>
      </div>

      <div class="studio-display">
        <div class="preview-box glass-card">
          <div class="preview-header">RGB Input Photo / GeoTIFF Tile</div>
          <div class="preview-body">
            <img id="img-input-preview" src="" style="display:none;">
            <div id="placeholder-input" style="color: var(--text-muted); font-size: 0.85rem; text-align: center;">
              📁 Upload an aerial photo or GeoTIFF file to begin monocular height estimation.
            </div>
          </div>
        </div>

        <div class="preview-box glass-card">
          <div class="preview-header">Relative Depth / rDSM Output</div>
          <div class="preview-body">
            <img id="img-depth-preview" src="" style="display:none;">
            <div id="placeholder-depth" style="color: var(--text-muted); font-size: 0.85rem; text-align: center;">
              rDSM Relative Depth Map Preview (Unitless [0 - 1])
            </div>
          </div>
        </div>

        <div class="preview-box glass-card">
          <div class="preview-header">Metric Absolute DSM (GeoTIFF / Elevation)</div>
          <div class="preview-body">
            <img id="img-dsm-preview" src="" style="display:none;">
            <div id="placeholder-dsm" style="color: var(--text-muted); font-size: 0.85rem; text-align: center;">
              Metric Elevation DSM Preview (Terrain Colormap)
            </div>
          </div>
        </div>

        <div class="preview-box glass-card">
          <div class="preview-header">Slope Gradient Map (Degrees)</div>
          <div class="preview-body">
            <img id="img-slope-preview" src="" style="display:none;">
            <div id="placeholder-slope" style="color: var(--text-muted); font-size: 0.85rem; text-align: center;">
              Terrain Slope Gradient Heatmap Preview
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  const fileInput = document.getElementById('file-input');
  const btnProcess = document.getElementById('btn-process');
  const btnView3D = document.getElementById('btn-view-3d-hero');
  const statusBox = document.getElementById('studio-status-box');
  const statusSteps = document.getElementById('studio-status-steps');

  let currentJobResult = null;

  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const inputImg = document.getElementById('img-input-preview');
        inputImg.src = ev.target.result;
        inputImg.style.display = 'block';
        document.getElementById('placeholder-input').style.display = 'none';
      };
      reader.readAsDataURL(file);
    }
  });

  btnProcess.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) {
      alert('Please select an image or GeoTIFF file first.');
      return;
    }

    const scale = parseFloat(document.getElementById('scale-input').value);
    const offset = parseFloat(document.getElementById('offset-input').value);

    statusBox.style.display = 'block';
    statusSteps.innerHTML = 'Preparing input image...<br>⏳ Running Depth Anything V2 inference...';

    try {
      setTimeout(() => {
        statusSteps.innerHTML += '<br>⚡ Calibrating relative depth & generating DSM...';
      }, 500);

      setTimeout(() => {
        statusSteps.innerHTML += '<br>📐 Triangulating 3D mesh & calculating normals...';
      }, 1000);

      const res = await processImage(file, scale, offset);
      currentJobResult = res;

      document.getElementById('img-depth-preview').src = res.urls.preview;
      document.getElementById('img-depth-preview').style.display = 'block';
      document.getElementById('placeholder-depth').style.display = 'none';

      document.getElementById('img-dsm-preview').src = res.urls.preview;
      document.getElementById('img-dsm-preview').style.display = 'block';
      document.getElementById('placeholder-dsm').style.display = 'none';

      document.getElementById('img-slope-preview').src = res.urls.slope;
      document.getElementById('img-slope-preview').style.display = 'block';
      document.getElementById('placeholder-slope').style.display = 'none';

      statusSteps.innerHTML = `✓ Job ${res.job_id} complete!<br>✓ Unit: ${res.unit}<br>✓ Device: ${res.device}<br><span style="color: var(--accent-green);">✓ 3D Terrain Surface Ready!</span>`;
      btnView3D.style.display = 'block';

      if (onJobComplete) onJobComplete(res.urls.mesh, res);
    } catch (err) {
      statusSteps.innerHTML = `<span style="color: #ff5252;">❌ Error: ${err.message}</span>`;
    }
  });

  btnView3D.addEventListener('click', () => {
    if (onViewMeshClicked && currentJobResult) {
      onViewMeshClicked(currentJobResult.urls.mesh, currentJobResult);
    }
  });
}
