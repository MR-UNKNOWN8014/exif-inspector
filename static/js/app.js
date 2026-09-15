const fileInput  = document.getElementById('fileInput');
const uploadZone = document.getElementById('uploadZone');
const statusBar  = document.getElementById('statusBar');
const statusSpinner = document.getElementById('statusSpinner');
const statusText = document.getElementById('statusText');
const results    = document.getElementById('results');
const previewBox = document.getElementById('previewBox');
const previewImg = document.getElementById('previewImg');
const batchResults = document.getElementById('batchResults');

let rawData = null;
let lastUploadedFile = null;
let previewUrl = null;
let batchFiles = [];

const formatSelect  = document.getElementById('formatSelect');
const qualityLabel  = document.getElementById('qualityLabel');
const qualitySlider = document.getElementById('qualitySlider');
const qualityValue  = document.getElementById('qualityValue');

formatSelect.addEventListener('change', () => {
  const isJpeg = formatSelect.value === 'jpeg';
  qualityLabel.hidden = !isJpeg;
  qualitySlider.hidden = !isJpeg;
});

qualitySlider.addEventListener('input', () => {
  qualityValue.textContent = qualitySlider.value;
});

const batchFormatSelect  = document.getElementById('batchFormatSelect');
const batchQualityLabel  = document.getElementById('batchQualityLabel');
const batchQualitySlider = document.getElementById('batchQualitySlider');
const batchQualityValue  = document.getElementById('batchQualityValue');

batchFormatSelect.addEventListener('change', () => {
  const isJpeg = batchFormatSelect.value === 'jpeg';
  batchQualityLabel.hidden = !isJpeg;
  batchQualitySlider.hidden = !isJpeg;
});

batchQualitySlider.addEventListener('input', () => {
  batchQualityValue.textContent = batchQualitySlider.value;
});

function handleFiles(files) {
  if (!files || !files.length) return;
  if (files.length > 1) analyzeBatch(files);
  else analyze(files[0]);
}

uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', () => handleFiles(fileInput.files));

function resetStripOptions() {
  document.querySelectorAll('.keep-check').forEach(cb => { cb.checked = false; });
  formatSelect.value = '';
  qualityLabel.hidden = true;
  qualitySlider.hidden = true;
  qualitySlider.value = 85;
  qualityValue.textContent = '85';
}

async function analyze(file) {
  resetStripOptions();
  showStatus('loading', `Analyzing ${file.name}…`);
  results.classList.remove('visible');
  uploadZone.style.display = 'none';

  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  previewImg.onerror = () => { previewBox.hidden = true; };
  previewImg.src = previewUrl;
  previewBox.hidden = false;

  const form = new FormData();
  form.append('image', file);

  try {
    const res  = await fetch('/analyze', { method: 'POST', body: form });
    const data = await res.json();

    if (data.error) {
      showStatus('error', '! ' + data.error);
      uploadZone.style.display = 'block';
      return;
    }

    lastUploadedFile = file;
    rawData = data;
    hideStatus();
    render(data);
  } catch (err) {
    showStatus('error', '! Could not reach server. Is app.py running?');
    uploadZone.style.display = 'block';
  }
}

function render(d) {
  const risk  = d.privacy_risk || {};
  const level = (risk.level || 'low').toLowerCase();
  document.getElementById('riskBanner').innerHTML = `
    <div class="risk-banner ${level}">
      <div class="risk-title">Risk level: ${risk.level || 'Unknown'}</div>
      ${(risk.details || []).map(r => `<div class="risk-item">${r}</div>`).join('')}
    </div>`;

  const fi = d.file_info  || {};
  const ii = d.image_info || {};
  const stats = [
    { label: 'Filename',    value: fi.filename    || '-' },
    { label: 'Format',      value: fi.extension   || ii.format || '-', cls: 'accent' },
    { label: 'File size',   value: fi.size_kb ? fi.size_kb + ' KB' : '-' },
    { label: 'Dimensions',  value: ii.width_px ? `${ii.width_px} × ${ii.height_px}` : '-' },
    { label: 'Megapixels',  value: ii.megapixels != null ? ii.megapixels + ' MP' : '-' },
    { label: 'Color mode',  value: ii.mode || '-' },
    { label: 'DPI',         value: ii.dpi  || '-' },
    { label: 'Modified',    value: fi.modified || '-' },
  ];
  document.getElementById('statGrid').innerHTML = stats.map(s =>
    `<div class="stat-card">
      <div class="stat-label">${s.label}</div>
      <div class="stat-value ${s.cls || ''}">${s.value}</div>
    </div>`
  ).join('');

  const exif = d.exif || {};
  const exifKeys = Object.keys(exif);
  document.getElementById('exifTable').innerHTML = exifKeys.length ? `
    <table class="meta-table">
      ${exifKeys.map(k =>
        `<tr><td>${k}</td><td>${formatExifVal(k, exif[k])}</td></tr>`
      ).join('')}
    </table>` : `<div class="gps-empty">No EXIF camera data found in this image.</div>`;

  const gps = d.gps || {};
  const gpsEl = document.getElementById('gpsBlock');
  if (gps.latitude != null) {
    gpsEl.innerHTML = `
      <div class="gps-block">
        <div class="gps-coords">
          <div class="gps-coord-item">
            <span class="gps-coord-label">Latitude</span>
            <span class="gps-coord-val">${gps.latitude}</span>
          </div>
          <div class="gps-coord-item">
            <span class="gps-coord-label">Longitude</span>
            <span class="gps-coord-val">${gps.longitude}</span>
          </div>
          ${gps.altitude_m != null ? `
          <div class="gps-coord-item">
            <span class="gps-coord-label">Altitude</span>
            <span class="gps-coord-val">${gps.altitude_m} m</span>
          </div>` : ''}
        </div>
        ${gps.google_maps ? `<a class="gps-link" href="${gps.google_maps}" target="_blank">Open in Google Maps &rarr;</a>` : ''}
      </div>`;
  } else {
    gpsEl.innerHTML = `<div class="gps-empty">No GPS data found. Location is not embedded.</div>`;
  }

  document.getElementById('rawBlock').textContent = JSON.stringify(d, null, 2);

  results.classList.add('visible');
}

function formatExifVal(key, val) {
  if (key === 'ExposureTime' && typeof val === 'number') {
    return val < 1 ? `1/${Math.round(1/val)}s` : `${val}s`;
  }
  if (key === 'FNumber' && typeof val === 'number') return `f/${val}`;
  if (key === 'FocalLength' && typeof val === 'number') return `${val} mm`;
  if (Array.isArray(val)) return val.join(', ');
  return String(val);
}

function toggleRaw() {
  const block  = document.getElementById('rawBlock');
  const arrow  = document.getElementById('rawToggleArrow');
  const toggle = document.getElementById('rawToggle');
  const visible = block.classList.toggle('visible');
  arrow.textContent = visible ? '▼' : '▶';
  toggle.lastChild.textContent = visible ? ' Hide raw JSON' : ' Show raw JSON';
}

function showStatus(type, msg) {
  statusBar.className = 'status-bar ' + type;
  statusSpinner.style.display = type === 'loading' ? 'block' : 'none';
  statusText.textContent = msg;
}

function hideStatus() {
  statusBar.className = 'status-bar';
}

async function eraseMetadata() {
  if (!lastUploadedFile) return;

  const btn    = document.getElementById('eraseBtn');
  const status = document.getElementById('eraseStatus');

  btn.disabled     = true;
  btn.textContent  = 'erasing...';
  status.className = 'erase-status';

  const form = new FormData();
  form.append('image', lastUploadedFile);
  if (formatSelect.value) form.append('format', formatSelect.value);
  form.append('quality', qualitySlider.value);
  document.querySelectorAll('.keep-check:checked').forEach(cb => form.append('keep', cb.value));

  try {
    const res = await fetch('/strip', { method: 'POST', body: form });

    if (!res.ok) {
      const data = await res.json();
      status.className   = 'erase-status error';
      status.textContent = '! ' + (data.error || 'Something went wrong');
      btn.disabled       = false;
      btn.textContent    = 'erase metadata & download clean image';
      return;
    }

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const nameMatch = disposition.match(/filename="?([^"]+)"?/);
    const downloadName = nameMatch ? nameMatch[1] : 'clean_' + lastUploadedFile.name;

    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href     = url;
    a.download = downloadName;
    a.click();
    URL.revokeObjectURL(url);

    status.className   = 'erase-status success';
    status.textContent = 'Clean image downloaded. All metadata removed.';
    btn.textContent    = 'erase metadata & download clean image';
    btn.disabled       = false;

  } catch (err) {
    status.className   = 'erase-status error';
    status.textContent = '! Could not reach server. Is app.py running?';
    btn.disabled       = false;
    btn.textContent    = 'erase metadata & download clean image';
  }
}

function reset() {
  results.classList.remove('visible');
  batchResults.hidden = true;
  uploadZone.style.display = 'block';
  fileInput.value = '';
  rawData = null;
  batchFiles = [];
  hideStatus();
  resetStripOptions();
  batchFormatSelect.value = '';
  batchQualityLabel.hidden = true;
  batchQualitySlider.hidden = true;
  batchQualitySlider.value = 85;
  batchQualityValue.textContent = '85';
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  previewBox.hidden = true;
}

function analyzeBatch(files) {
  batchFormatSelect.value = '';
  batchQualityLabel.hidden = true;
  batchQualitySlider.hidden = true;
  batchQualitySlider.value = 85;
  batchQualityValue.textContent = '85';

  batchFiles = Array.from(files);
  results.classList.remove('visible');
  uploadZone.style.display = 'none';
  hideStatus();

  document.getElementById('batchCount').textContent = batchFiles.length;
  document.getElementById('batchFileList').innerHTML = batchFiles.map(f =>
    `<div class="batch-file-item"><span>${f.name}</span><span>${(f.size / 1024).toFixed(1)} KB</span></div>`
  ).join('');

  const status = document.getElementById('batchStatus');
  status.className = 'erase-status';
  batchResults.hidden = false;
}

async function stripBatch() {
  if (!batchFiles.length) return;

  const btn    = document.getElementById('batchStripBtn');
  const status = document.getElementById('batchStatus');

  btn.disabled    = true;
  btn.textContent = 'erasing...';
  status.className = 'erase-status';

  const form = new FormData();
  batchFiles.forEach(f => form.append('images', f));
  if (batchFormatSelect.value) form.append('format', batchFormatSelect.value);
  form.append('quality', batchQualitySlider.value);

  try {
    const res = await fetch('/strip-batch', { method: 'POST', body: form });

    if (!res.ok) {
      const data = await res.json();
      status.className   = 'erase-status error';
      status.textContent = '! ' + (data.error || 'Something went wrong');
      btn.disabled       = false;
      btn.textContent    = 'erase metadata for all & download zip';
      return;
    }

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const nameMatch = disposition.match(/filename="?([^"]+)"?/);
    const downloadName = nameMatch ? nameMatch[1] : 'clean_images.zip';

    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href     = url;
    a.download = downloadName;
    a.click();
    URL.revokeObjectURL(url);

    status.className   = 'erase-status success';
    status.textContent = 'Clean images downloaded as a zip.';
    btn.textContent    = 'erase metadata for all & download zip';
    btn.disabled        = false;

  } catch (err) {
    status.className   = 'erase-status error';
    status.textContent = '! Could not reach server. Is app.py running?';
    btn.disabled       = false;
    btn.textContent    = 'erase metadata for all & download zip';
  }
}

async function toggleHistory() {
  const block  = document.getElementById('historyBlock');
  const arrow  = document.getElementById('historyToggleArrow');
  const toggle = document.getElementById('historyToggle');
  const visible = block.classList.toggle('visible');
  arrow.textContent = visible ? '▼' : '▶';
  toggle.lastChild.textContent = visible ? ' Hide scan history' : ' Show scan history';

  if (visible) {
    try {
      const res = await fetch('/history');
      const entries = await res.json();
      block.innerHTML = entries.length ? `
        <table class="meta-table">
          ${entries.map(e =>
            `<tr><td>${e.timestamp.replace('T', ' ').slice(0, 19)}</td><td>${e.action} - ${e.filename}${e.risk_level ? ' (' + e.risk_level + ')' : ''}</td></tr>`
          ).join('')}
        </table>` : `<div class="gps-empty">No scan history yet.</div>`;
    } catch (err) {
      block.innerHTML = `<div class="gps-empty">Could not load history.</div>`;
    }
  }
}
