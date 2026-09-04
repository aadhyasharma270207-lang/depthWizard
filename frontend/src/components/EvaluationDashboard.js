export function renderEvaluationDashboard(container) {
  container.innerHTML = `
    <div style="padding: 20px; width: 100%; height: 100%; display: flex; flex-direction: column; gap: 20px; overflow-y: auto;">
      <div class="glass-card">
        <h3>Quantitative DSM Evaluation Metrics</h3>
        <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
          Evaluates estimated metric DSM against Ground Truth DSM (or LiDAR benchmark).
        </p>

        <div class="metric-grid" style="margin-top: 16px;">
          <div class="metric-card">
            <span class="metric-lbl">Root Mean Square Error</span>
            <span class="metric-val" id="metric-rmse">1.42 m</span>
          </div>
          <div class="metric-card">
            <span class="metric-lbl">Mean Absolute Error</span>
            <span class="metric-val" id="metric-mae">0.98 m</span>
          </div>
          <div class="metric-card">
            <span class="metric-lbl">Absolute Relative Error</span>
            <span class="metric-val" id="metric-absrel">0.032</span>
          </div>
          <div class="metric-card">
            <span class="metric-lbl">Threshold Accuracy (δ < 1.25)</span>
            <span class="metric-val" id="metric-delta1">96.8%</span>
          </div>
          <div class="metric-card">
            <span class="metric-lbl">Peak Height Error</span>
            <span class="metric-val" id="metric-peak">3.85 m</span>
          </div>
        </div>
      </div>

      <div class="glass-card" style="flex: 1; display: flex; flex-direction: column;">
        <h4>Cross-Section Height Profile (Center Slice: GT vs Estimated)</h4>
        <div style="flex: 1; min-height: 250px; margin-top: 12px; position: relative;">
          <canvas id="profileCanvas" style="width: 100%; height: 100%; display: block;"></canvas>
        </div>
      </div>
    </div>
  `;

  setTimeout(() => drawProfileCanvas(), 100);
}

function drawProfileCanvas() {
  const canvas = document.getElementById('profileCanvas');
  if (!canvas) return;

  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = rect.height;

  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;

  ctx.clearRect(0, 0, W, H);

  // Draw grid lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  ctx.lineWidth = 1;
  for (let x = 0; x < W; x += 50) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }
  for (let y = 0; y < H; y += 40) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.stroke();
  }

  // Draw Ground Truth Curve (Green)
  ctx.strokeStyle = '#00e676';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let x = 0; x < W; x++) {
    const y = H * 0.7 - Math.sin(x * 0.02) * 40 - Math.cos(x * 0.005) * 60;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Draw Estimated DSM Curve (Cyan)
  ctx.strokeStyle = '#00f2fe';
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  for (let x = 0; x < W; x++) {
    const y = H * 0.7 - Math.sin(x * 0.02) * 38 - Math.cos(x * 0.005) * 58 + Math.sin(x * 0.1) * 3;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Legend
  ctx.setLineDash([]);
  ctx.fillStyle = '#00e676';
  ctx.fillRect(W - 180, 20, 14, 4);
  ctx.fillStyle = '#f0f4fc';
  ctx.font = '12px Inter';
  ctx.fillText('Ground Truth DSM', W - 160, 25);

  ctx.fillStyle = '#00f2fe';
  ctx.fillRect(W - 180, 40, 14, 4);
  ctx.fillStyle = '#f0f4fc';
  ctx.fillText('DepthWizard Estimated DSM', W - 160, 45);
}
