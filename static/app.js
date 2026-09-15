const fileInput = document.getElementById('fileInput');
const uploadZone = document.getElementById('uploadZone');
const statusBar = document.getElementById('statusBar');
const statusSpinner = document.getElementById('statusSpinner');
const statusText = document.getElementById('statusText');
const results = document.getElementById('results');
const eraseBtn = document.getElementById('eraseBtn');
const eraseStatus = document.getElementById('eraseStatus');

let lastUploadedFile = null;

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) analyze(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) analyze(fileInput.files[0]);
});

async function analyze(file) {
  showStatus('loading', `Analyzing ${file.name}`);
  results.style.display = 'none';
  uploadZone.style.display = 'none';

  const form = new FormData();
  form.append('image', file);

  try {
    const res = await fetch('/analyze', { method: 'POST', body: form });
    const data = await res.json();

    if (data.error) {
      showStatus('error', data.error);
      uploadZone.style.display = 'block';
      return;
    }

    lastUploadedFile = file;
    hideStatus();
    render(data);
  } catch (err) {
    showStatus('error', 'Could not reach server. Is app.py running?');
    uploadZone.style.display = 'block';
  }
}

function render(d) {
  const risk = d.privacy_risk || {};
  const level = (risk.level || 'low').toLowerCase();
  document.getElementById('riskBanner').innerHTML = `
    <div class="risk-banner ${level}">
      <div class="risk-title">Risk level: ${risk.level || 'Unknown'}</div>
      ${(risk.details || []).map((r) => `<div class="risk-item">${r}</div>`).join('')}
    </div>`;

  const fi = d.file_info || {};
  const ii = d.image_info || {};
  const stats = [
    { label: 'Filename', value: fi.filename || '-' },
    { label: 'Format', value: fi.extension || ii.format || '-', cls: 'accent' },
    { label: 'File size', value: fi.size_kb ? `${fi.size_kb} KB` : '-' },
    { label: 'Dimensions', value: ii.width_px ? `${ii.width_px} x ${ii.height_px}` : '-' },
    { label: 'Megapixels', value: ii.megapixels != null ? `${ii.megapixels} MP` : '-' },
    { label: 'Color mode', value: ii.mode || '-' },
    { label: 'DPI', value: ii.dpi || '-' },
    { label: 'Modified', value: fi.modified || '-' },
  ];
  document.getElementById('statGrid').innerHTML = stats
    .map(
      (s) => `<div class="stat-card">
        <div class="stat-label">${s.label}</div>
        <div class="stat-value ${s.cls || ''}">${s.value}</div>
      </div>`
    )
    .join('');

  const exif = d.exif || {};
  const exifKeys = Object.keys(exif);
  document.getElementById('exifTable').innerHTML = exifKeys.length
    ? `<table class="meta-table">
        ${exifKeys.map((k) => `<tr><td>${k}</td><td>${formatExifVal(k, exif[k])}</td></tr>`).join('')}
      </table>`
    : '<div class="empty-block">No EXIF camera data found in this image.</div>';

  // backend keys are capitalized (Latitude/Longitude), matches exif_reader.py's _parse_gps output
  const gps = d.gps || {};
  const gpsEl = document.getElementById('gpsBlock');
  if (gps.Latitude != null) {
    gpsEl.innerHTML = `
      <div class="gps-block">
        <div class="gps-coords">
          <div class="gps-coord-item">
            <span class="gps-coord-label">Latitude</span>
            <span class="gps-coord-val">${gps.Latitude}</span>
          </div>
          <div class="gps-coord-item">
            <span class="gps-coord-label">Longitude</span>
            <span class="gps-coord-val">${gps.Longitude}</span>
          </div>
          ${
            gps.altitude_m != null
              ? `<div class="gps-coord-item">
                  <span class="gps-coord-label">Altitude</span>
                  <span class="gps-coord-val">${gps.altitude_m} m</span>
                </div>`
              : ''
          }
        </div>
        ${gps.google_maps ? `<a class="gps-link" href="${gps.google_maps}" target="_blank" rel="noopener">Open in Google Maps</a>` : ''}
      </div>`;
  } else {
    gpsEl.innerHTML = '<div class="empty-block">No GPS data found. Location is not embedded.</div>';
  }

  document.getElementById('rawBlock').textContent = JSON.stringify(d, null, 2);
  results.style.display = 'block';
}

function formatExifVal(key, val) {
  if (key === 'ExposureTime' && typeof val === 'number') {
    return val < 1 ? `1/${Math.round(1 / val)}s` : `${val}s`;
  }
  if (key === 'FNumber' && typeof val === 'number') return `f/${val}`;
  if (key === 'FocalLength' && typeof val === 'number') return `${val} mm`;
  if (Array.isArray(val)) return val.join(', ');
  return String(val);
}

function toggleRaw() {
  const block = document.getElementById('rawBlock');
  const toggle = document.getElementById('rawToggle');
  const visible = block.classList.toggle('visible');
  toggle.textContent = visible ? 'Hide raw JSON' : 'Show raw JSON';
}

function showStatus(type, msg) {
  statusBar.className = `status-bar ${type}`;
  statusSpinner.style.display = type === 'loading' ? 'block' : 'none';
  statusText.textContent = msg;
}

function hideStatus() {
  statusBar.className = 'status-bar';
}

async function eraseMetadata() {
  if (!lastUploadedFile) return;

  eraseBtn.disabled = true;
  eraseBtn.textContent = 'Erasing...';
  eraseStatus.className = 'erase-status';

  const form = new FormData();
  form.append('image', lastUploadedFile);

  try {
    const res = await fetch('/strip', { method: 'POST', body: form });

    if (!res.ok) {
      const data = await res.json();
      eraseStatus.className = 'erase-status error';
      eraseStatus.textContent = data.error || 'Something went wrong';
      eraseBtn.disabled = false;
      eraseBtn.textContent = 'Erase metadata and download clean image';
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `clean_${lastUploadedFile.name}`;
    a.click();
    URL.revokeObjectURL(url);

    eraseStatus.className = 'erase-status success';
    eraseStatus.textContent = 'Clean image downloaded. All metadata removed.';
  } catch (err) {
    eraseStatus.className = 'erase-status error';
    eraseStatus.textContent = 'Could not reach server. Is app.py running?';
  } finally {
    eraseBtn.disabled = false;
    eraseBtn.textContent = 'Erase metadata and download clean image';
  }
}

function reset() {
  results.style.display = 'none';
  uploadZone.style.display = 'block';
  fileInput.value = '';
  hideStatus();
}
