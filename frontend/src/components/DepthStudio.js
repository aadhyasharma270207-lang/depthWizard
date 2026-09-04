import { processImage } from '../utils/api.js';

export function renderDepthStudio(container, onJobComplete) {
  container.innerHTML = `
    <div class="studio-layout">
      <div class="studio-sidebar glass-card">
        <h3 style="font-size: 1.05rem; margin-bottom: 12px;">Image & GeoTIFF Workbench</h3>
        
        <div class="controls-group">
          <label>Select RGB Photo / GeoTIFF File</label>
          <input type="file" id="file-input" accept=".png,.jpg,.jpeg,.tif,.tiff" class="select-custom" style="padding: 8px;">
        </div>

        <div class="controls-group">
          <label>Scale Calibration Factor (a) <span>Z = a·D + b</span></label>
          <input type="number" id="scale-input" value="50.0" step="0.5" class="select-custom">
        </div>

        <div class="controls-group">
          <label>Elevation Shift Offset (b) [meters]</label>
          <input type="number" id="offset-input" value="10.0" step="0.5" class="select-custom">
        </div>

        <button class="btn-primary" id="btn-process" style="margin-top: 12px; padding: 12px;">
          ⚡ Process & Generate 3D Terrain
        </button>

        <div id="studio-status" style="font-size: 0.8rem; color: var(--accent-cyan); margin-top: 8px;"></div>
      </div>

      <div class="studio-display">
        <div class="preview-box glass-card">
          <div class="preview-header">RGB Input Photo / GeoTIFF Tile</div>
          <div class="preview-body">
            <img id="img-input-preview" src="" style="display:none;">
            <div id="placeholder-input" style="color: var(--text-muted); font-size: 0.85rem;">Upload image or GeoTIFF</div>
          </div>
        </div>

        <div class="preview-box glass-card">
          <div class="preview-header">Relative Depth / rDSM Output</div>
          <div class="preview-body">
            <img id="img-depth-preview" src="" style="display:none;">
            <div id="placeholder-depth" style="color: var(--text-muted); font-size: 0.85rem;">rDSM preview (Unitless)</div>
          </div>
        </div>

        <div class="preview-box glass-card">
          <div class="preview-header">Metric Absolute DSM (GeoTIFF / Elevation)</div>
          <div class="preview-body">
            <img id="img-dsm-preview" src="" style="display:none;">
            <div id="placeholder-dsm" style="color: var(--text-muted); font-size: 0.85rem;">Metric DSM preview (Terrain Colormap)</div>
          </div>
        </div>

        <div class="preview-box glass-card">
          <div class="preview-header">Slope Gradient Map (Degrees)</div>
          <div class="preview-body">
            <img id="img-slope-preview" src="" style="display:none;">
            <div id="placeholder-slope" style="color: var(--text-muted); font-size: 0.85rem;">Slope gradient heatmap preview</div>
          </div>
        </div>
      </div>
    </div>
  `;

  const fileInput = document.getElementById('file-input');
  const btnProcess = document.getElementById('btn-process');
  const statusEl = document.getElementById('studio-status');

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

    statusEl.innerText = 'Uploading & running Depth Anything V2 inference...';

    try {
      const res = await processImage(file, scale, offset);
      
      document.getElementById('img-depth-preview').src = res.urls.preview;
      document.getElementById('img-depth-preview').style.display = 'block';
      document.getElementById('placeholder-depth').style.display = 'none';

      document.getElementById('img-dsm-preview').src = res.urls.preview;
      document.getElementById('img-dsm-preview').style.display = 'block';
      document.getElementById('placeholder-dsm').style.display = 'none';

      document.getElementById('img-slope-preview').src = res.urls.slope;
      document.getElementById('img-slope-preview').style.display = 'block';
      document.getElementById('placeholder-slope').style.display = 'none';

      statusEl.innerText = `Success! Job ${res.job_id} complete. Unit: ${res.unit}.`;
      if (onJobComplete) onJobComplete(res.urls.mesh, res);
    } catch (err) {
      statusEl.innerText = `Error: ${err.message}`;
    }
  });
}
