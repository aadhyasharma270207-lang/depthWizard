export async function processImage(file, scale = 50.0, offset = 10.0, gcpsJson = null) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('scale', scale);
  formData.append('offset', offset);
  if (gcpsJson) formData.append('gcps_json', gcpsJson);

  const res = await fetch('/api/process', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Image processing failed');
  }

  return await res.json();
}

export async function calibrateJob(jobId, gcpsJson) {
  const formData = new FormData();
  formData.append('job_id', jobId);
  formData.append('gcps_json', gcpsJson);

  const res = await fetch('/api/calibrate', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Calibration failed');
  }

  return await res.json();
}

export const calibrateGCPs = calibrateJob;

export async function evaluateJob(jobId, gtFile) {
  const formData = new FormData();
  formData.append('job_id', jobId);
  formData.append('gt_file', gtFile);

  const res = await fetch('/api/evaluate', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Evaluation failed');
  }

  return await res.json();
}

export async function getJobDetails(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to fetch job');
  }
  return await res.json();
}

export async function getSystemHealth() {
  const res = await fetch('/health');
  if (!res.ok) return { status: 'offline' };
  return await res.json();
}

export async function runDemoDataset(datasetId = 'urban_buildings') {
  const res = await fetch(`/api/v1/demo/run?dataset_id=${datasetId}`, {
    method: 'POST',
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Demo dataset launch failed');
  }

  return await res.json();
}
