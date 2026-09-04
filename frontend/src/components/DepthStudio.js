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
          <label>Optional Manual Scale Factor (a) <span style="font-family: var(--font-mono); color: var(--text-muted);">Z = a·D + b</span></label>
          <input type="number" id="scale-input" placeholder="Default: 50.0 (Manual)" step="0.5" class="select-custom">
        </div>

        <div class="controls-group">
          <label>Optional Shift Offset (b) [meters]</label>
          <input type="number" id="offset-input" placeholder="Default: 10.0 (Manual)" step="0.5" class="select-custom">
        </div>

        <button class="btn-primary" id="btn-process" style="margin-top: 12px; padding: 12px; font-weight: 700;">
          ⚡ Process & Generate 3D Terrain Mesh
        </button>

        <!-- Pipeline Progress Box -->
        <div id="studio-status-box" style="margin-top: 12px; display: none; padding: 12px; background: rgba(0,0,0,0.4); border-radius: 8px; border: 1px solid var(--glass-border);">
          <div style="font-size: 0.78rem; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">Processing Pipeline Stages</div>
          <div id="studio-status-steps" style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--accent-cyan); line-height: 1.5;"></div>
        </div>

        <!-- Data Provenance Card -->
        <div id="provenance-card" style="margin-top: 12px; display: none; padding: 12px; background: rgba(0,242,254,0.04); border-radius: 8px; border: 1px solid rgba(0,242,254,0.2);">
          <div style="font-size: 0.78rem; font-weight: 700; color: var(--accent-cyan); margin-bottom: 6px; text-transform: uppercase;">
            📜 Data Provenance & Metadata
          </div>
          <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-main); display: flex; flex-direction: column; gap: 4px;">
            <div>Filename: <strong id="prov-filename">--</strong></div>
            <div>Georeferenced: <strong id="prov-geo">--</strong></div>
            <div>Model Engine: <strong id="prov-model">Depth Anything V2 (Base)</strong></div>
            <div>Device: <strong id="prov-device">--</strong></div>
            <div>Elevation Output: <strong id="prov-unit">--</strong></div>
          </div>
        </div>

        <button class="btn-primary" id="btn-view-3d-hero" style="display: none; margin-top: 12px; padding: 12px; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple)); font-weight: 700;">
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
          <div class="preview-header">Metric / Relative DSM (Elevation)</div>
          <div class="preview-body">
            <img id="img-dsm-preview" src="" style="display:none;">
            <div id="placeholder-dsm" style="color: var(--text-muted); font-size: 0.85rem; text-align: center;">
              DSM Elevation Preview (Terrain Colormap)
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

  const provCard = document.getElementById('provenance-card');
  const provFilename = document.getElementById('prov-filename');
  const provGeo = document.getElementById('prov-geo');
  const provDevice = document.getElementById('prov-device');
  const provUnit = document.getElementById('prov-unit');

  let currentJobResult = null;

  const setUploadedRgbUrl = (url) => {
    window.__UPLOADED_RGB_URL__ = url;
    if (window.__VIEWER3D_INSTANCE__) {
      window.__VIEWER3D_INSTANCE__.syncMeshToNewInput(url, window.__ACTIVE_DSM_URL__ || null);
    }
  };

  const setActiveDsmUrl = (url) => {
    window.__ACTIVE_DSM_URL__ = url;
    if (window.__VIEWER3D_INSTANCE__) {
      window.__VIEWER3D_INSTANCE__.syncMeshToNewInput(window.__UPLOADED_RGB_URL__ || null, url);
    }
  };

  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      currentJobResult = null;
      btnView3D.style.display = 'none';
      
      const objectUrl = URL.createObjectURL(file);
      const inputImg = document.getElementById('img-input-preview');
      inputImg.src = objectUrl;
      inputImg.style.display = 'block';
      document.getElementById('placeholder-input').style.display = 'none';

      // Immediately set the global/shared state
      setUploadedRgbUrl(objectUrl);
    }
  });

  btnProcess.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) {
      alert('Please select an image or GeoTIFF file first.');
      return;
    }

    currentJobResult = null;
    btnView3D.style.display = 'none';

    const scaleVal = document.getElementById('scale-input').value;
    const offsetVal = document.getElementById('offset-input').value;
    const scale = scaleVal !== '' ? parseFloat(scaleVal) : 50.0;
    const offset = offsetVal !== '' ? parseFloat(offsetVal) : 10.0;

    statusBox.style.display = 'block';
    statusSteps.innerHTML = '1. Uploading input image...<br>2. ⏳ Running Depth Anything V2 inference...';

    try {
      setTimeout(() => {
        statusSteps.innerHTML += '<br>3. ⚡ Processing relative depth & generating DSM...';
      }, 400);

      setTimeout(() => {
        statusSteps.innerHTML += '<br>4. 📐 Triangulating 3D surface mesh & computing normals...';
      }, 800);

      const res = await processImage(file, scale, offset);
      currentJobResult = res;

      const ts = Date.now();
      const relDepthUrl = res.urls.rel_depth ? `${res.urls.rel_depth}?t=${ts}` : `${res.urls.preview}?t=${ts}`;
      const dsmUrl = `${res.urls.preview}?t=${ts}`;
      const slopeUrl = `${res.urls.slope}?t=${ts}`;

      // Set the resulting DSM map URL in shared state
      setActiveDsmUrl(relDepthUrl);

      const imgDepth = document.getElementById('img-depth-preview');
      imgDepth.src = relDepthUrl;
      imgDepth.style.display = 'block';
      document.getElementById('placeholder-depth').style.display = 'none';

      const imgDsm = document.getElementById('img-dsm-preview');
      imgDsm.src = dsmUrl;
      imgDsm.style.display = 'block';
      document.getElementById('placeholder-dsm').style.display = 'none';

      const imgSlope = document.getElementById('img-slope-preview');
      imgSlope.src = slopeUrl;
      imgSlope.style.display = 'block';
      document.getElementById('placeholder-slope').style.display = 'none';

      statusSteps.innerHTML = `✓ Job ${res.job_id} processing complete!<br>✓ Status: ${res.status_message}<br><span style="color: var(--accent-green);">✓ 3D Terrain Surface Ready!</span>`;
      
      // Update Provenance Card
      provFilename.innerText = file.name || 'Input Photo';
      provGeo.innerText = res.is_georeferenced ? 'Yes (GeoTIFF CRS preserved)' : 'No (Standard RGB photo)';
      provDevice.innerText = res.device || 'CPU';
      provUnit.innerText = res.is_georeferenced || res.unit === 'metres' ? 'Metric Absolute DSM (m)' : 'Relative DSM (Unitless rDSM)';

      provCard.style.display = 'block';
      btnView3D.style.display = 'block';

      if (onJobComplete) onJobComplete(res.urls.mesh, res);
    } catch (err) {
      statusSteps.innerHTML = `<span style="color: #ff5252;">❌ Error: ${err.message}</span>`;
      btnView3D.style.display = 'none';
    }
  });

  btnView3D.addEventListener('click', () => {
    if (!currentJobResult || !currentJobResult.job_id) {
      alert('Terrain data is not ready. Process the image first.');
      return;
    }
    if (onViewMeshClicked) {
      onViewMeshClicked(currentJobResult.urls.mesh, currentJobResult);
    }
  });
}
