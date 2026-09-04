export function renderNavbar(container, onTabChange, onRunDemo) {
  container.innerHTML = `
    <header class="navbar">
      <div class="brand">
        <div class="brand-icon">DW</div>
        <div>
          <div class="brand-title">DepthWizard</div>
          <span class="brand-badge">SIH 2026 Edition</span>
        </div>
      </div>

      <nav class="nav-tabs">
        <button class="tab-btn active" data-tab="viewer">
          <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></button>
          3D Flythrough
        </button>
        <button class="tab-btn" data-tab="studio">
          <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
          Depth & DSM Studio
        </button>
        <button class="tab-btn" data-tab="calibration">
          <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
          GCP Calibration
        </button>
        <button class="tab-btn" data-tab="evaluation">
          <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
          Accuracy Metrics
        </button>
      </nav>

      <div class="nav-actions">
        <div class="status-pill">
          <span class="dot-green"></span>
          <span>Depth Anything V2 (Base)</span>
        </div>
        <button class="btn-primary" id="btn-quick-demo">🚀 Quick Demo</button>
      </div>
    </header>
  `;

  container.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      container.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      const tabName = btn.dataset.tab;
      btn.classList.add('active');
      onTabChange(tabName);
    });
  });

  document.getElementById('btn-quick-demo').addEventListener('click', onRunDemo);
}
