// ============================================================
// CivicTrack frontend logic
// EDIT THESE THREE LINES to match your own AWS resources
// ============================================================
const UPLOAD_URL_ENDPOINT = "https://uh1wr7wloh.execute-api.ap-south-1.amazonaws.com/prod/upload-url";
const REPORT_STATUS_ENDPOINT = "https://uh1wr7wloh.execute-api.ap-south-1.amazonaws.com/prod/report-status";
const COUNTS_JSON_URL = "https://civic-problem-images.s3.ap-south-1.amazonaws.com/public/counts.json";

const REFRESH_INTERVAL_MS = 5000;   // dashboard re-check interval
const POLL_MAX_ATTEMPTS = 8;         // status poll attempts after upload
const POLL_INTERVAL_MS = 2500;       // gap between poll attempts (~20s ceiling)

// ---------- elements ----------
const form = document.getElementById('report-form');
const photoInput = document.getElementById('photo-input');
const dropzone = document.getElementById('dropzone');
const dropzoneCopy = document.getElementById('dropzone-copy');
const previewImg = document.getElementById('preview-img');
const submitBtn = document.getElementById('submit-btn');
const statusLine = document.getElementById('status-line');
const ticketNo = document.getElementById('ticket-no');
const updatedAtEl = document.getElementById('updated-at');

const countEls = {
  Pothole: document.getElementById('count-pothole'),
  'Garbage Collection': document.getElementById('count-garbage'),
  'Street Light': document.getElementById('count-streetlight'),
  Traffic: document.getElementById('count-traffic'),
};

let selectedFile = null;

// ---------- photo selection & preview ----------
photoInput.addEventListener('change', () => {
  const file = photoInput.files[0];
  if (!file) return;
  selectedFile = file;

  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    previewImg.hidden = false;
    dropzoneCopy.hidden = true;
    dropzone.classList.add('has-image');
  };
  reader.readAsDataURL(file);

  submitBtn.disabled = false;
  setStatus('Photo ready. Submit when you are.', 'neutral');
});

// drag & drop support
['dragover', 'dragenter'].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'var(--safety-orange)';
  })
);
['dragleave', 'drop'].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '';
  })
);
dropzone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  if (file) {
    photoInput.files = e.dataTransfer.files;
    photoInput.dispatchEvent(new Event('change'));
  }
});

// ---------- submit flow ----------
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!selectedFile) return;

  submitBtn.disabled = true;
  setStatus('Requesting an upload slot…', 'neutral');

  try {
    const ext = (selectedFile.name.split('.').pop() || 'jpg').toLowerCase();

    // 1. Ask our API for a presigned S3 URL
    const urlResponse = await fetch(`${UPLOAD_URL_ENDPOINT}?ext=${encodeURIComponent(ext)}`);
    if (!urlResponse.ok) throw new Error('Could not get an upload URL');
    const { uploadUrl, key, contentType } = await urlResponse.json();

    // 2. Upload the photo straight to S3
    setStatus('Uploading photo…', 'neutral');
    const putResponse = await fetch(uploadUrl, {
      method: 'PUT',
      headers: { 'Content-Type': contentType },
      body: selectedFile,
    });
    if (!putResponse.ok) throw new Error('Upload to storage failed');

    ticketNo.textContent = `#${key.split('/').pop().split('.')[0].slice(0, 8).toUpperCase()}`;
    setStatus('Report submitted. Analyzing photo…', 'neutral');
    resetForm();

    // 3. Poll for the Rekognition + RDS result (async pipeline, not instant)
    const result = await pollReportStatus(key);
    if (result && result.status === 'done') {
      setStatus(`Categorized as: ${result.category} (confidence ${result.confidence}%)`, 'success');
    } else {
      setStatus('Report submitted. Still processing — check back shortly.', 'neutral');
    }
  } catch (err) {
    console.error(err);
    setStatus(`Something went wrong: ${err.message}. Please try again.`, 'error');
    submitBtn.disabled = false;
  }
});

// ---------- status polling ----------
async function pollReportStatus(key, maxAttempts = POLL_MAX_ATTEMPTS, intervalMs = POLL_INTERVAL_MS) {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    try {
      const res = await fetch(`${REPORT_STATUS_ENDPOINT}?key=${encodeURIComponent(key)}`);
      if (res.status === 200) {
        return await res.json(); // { status: 'done', category, confidence }
      }
      // 202 = still processing, keep polling; anything else falls through and retries too
    } catch (err) {
      console.error('Status poll failed:', err);
    }
  }
  return null; // gave up after maxAttempts
}

function resetForm() {
  selectedFile = null;
  photoInput.value = '';
  previewImg.hidden = true;
  previewImg.src = '';
  dropzoneCopy.hidden = false;
  dropzone.classList.remove('has-image');
  submitBtn.disabled = true;
}

function setStatus(message, kind) {
  statusLine.textContent = message;
  statusLine.classList.remove('is-success', 'is-error');
  if (kind === 'success') statusLine.classList.add('is-success');
  if (kind === 'error') statusLine.classList.add('is-error');
}

// ---------- dashboard polling ----------
async function refreshCounts() {
  try {
    const response = await fetch(`${COUNTS_JSON_URL}?t=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('counts.json not available yet');
    const data = await response.json();

    Object.entries(countEls).forEach(([category, el]) => {
      const value = data.counts?.[category];
      el.textContent = typeof value === 'number' ? value : '—';
    });

    if (data.updatedAt) {
      const d = new Date(data.updatedAt);
      updatedAtEl.textContent = `Updated ${d.toLocaleTimeString()}`;
    }
  } catch (err) {
    updatedAtEl.textContent = 'Totals not available yet';
  }
}

refreshCounts();
setInterval(refreshCounts, REFRESH_INTERVAL_MS);