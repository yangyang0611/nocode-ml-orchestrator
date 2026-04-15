const state = {
    selectedJobId: null,
    selectedFile: null,
};

const modelList = document.getElementById('modelList');
const dropZone  = document.getElementById('dropZone');
const imageInput= document.getElementById('imageInput');
const fileName  = document.getElementById('fileName');
const runBtn    = document.getElementById('runBtn');
const confRange = document.getElementById('confRange');
const confValue = document.getElementById('confValue');
const statusEl  = document.getElementById('status');
const resultCard= document.getElementById('resultCard');
const inputPreview  = document.getElementById('inputPreview');
const outputPreview = document.getElementById('outputPreview');
const detBody   = document.getElementById('detBody');
const detCount  = document.getElementById('detCount');

function fmtTime(iso) {
    if (!iso) return '-';
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

async function fetchModels() {
    modelList.innerHTML = '<div class="empty-state">Loading models…</div>';
    try {
        const r = await fetch('/api/models');
        const data = await r.json();
        renderModels(data);
    } catch (e) {
        modelList.innerHTML = `<div class="empty-state" style="color:var(--danger)">Failed to load: ${e}</div>`;
    }
}

function renderModels(models) {
    if (!models.length) {
        modelList.innerHTML = '<div class="empty-state">No trained models yet. Submit a job from the <a href="/train">training page</a> first.</div>';
        return;
    }
    modelList.innerHTML = '';
    models.forEach(m => {
        const row = document.createElement('div');
        row.className = 'model-row';
        row.dataset.jobId = m.job_id;
        row.innerHTML = `
            <div>
                <div class="model-jobid">${m.job_id.slice(0, 8)} · ${escapeHtml(m.model)}</div>
                <div class="model-meta">
                    ${escapeHtml(m.dataset || '')} · ${m.epochs} epochs · ${m.size_mb} MB · finished ${fmtTime(m.finished_at)}
                </div>
            </div>
            <div>
                <span class="status-badge s-${m.status || 'completed'}">${m.status || 'completed'}</span>
            </div>
        `;
        row.addEventListener('click', () => selectModel(m.job_id));
        modelList.appendChild(row);
    });
}

function selectModel(jobId) {
    state.selectedJobId = jobId;
    [...modelList.querySelectorAll('.model-row')].forEach(r => {
        r.classList.toggle('selected', r.dataset.jobId === jobId);
    });
    updateRunBtn();
}

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
        ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

function updateRunBtn() {
    runBtn.disabled = !(state.selectedJobId && state.selectedFile);
}

// ── File handling ────────────────────────────────────────────────────────────
function handleFile(file) {
    if (!file) return;
    if (!/\.(jpe?g|png)$/i.test(file.name)) {
        setStatus('Only .jpg / .png files are accepted.', 'danger');
        return;
    }
    state.selectedFile = file;
    fileName.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    const reader = new FileReader();
    reader.onload = e => {
        inputPreview.src = e.target.result;
        resultCard.style.display = 'block';
        outputPreview.removeAttribute('src');
        outputPreview.style.background = '#f7f9ff';
        detBody.innerHTML = '';
        detCount.textContent = '0';
    };
    reader.readAsDataURL(file);
    updateRunBtn();
}

imageInput.addEventListener('change', e => handleFile(e.target.files[0]));

dropZone.addEventListener('click', (e) => {
    if (e.target.tagName !== 'BUTTON') imageInput.click();
});
['dragenter', 'dragover'].forEach(evt =>
    dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.add('dragover'); }));
['dragleave', 'drop'].forEach(evt =>
    dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.remove('dragover'); }));
dropZone.addEventListener('drop', e => handleFile(e.dataTransfer.files[0]));

confRange.addEventListener('input', () => { confValue.textContent = confRange.value; });

// ── Run ──────────────────────────────────────────────────────────────────────
runBtn.addEventListener('click', runInference);

function setStatus(msg, type = 'info') {
    const colors = { info: 'var(--muted)', danger: 'var(--danger)', success: 'var(--success)' };
    statusEl.style.color = colors[type] || colors.info;
    statusEl.innerHTML = msg;
}

async function runInference() {
    if (!state.selectedJobId || !state.selectedFile) return;
    runBtn.disabled = true;
    setStatus('<span class="spinner-ring"></span>Running inference in container — this may take 20–60 s on first run…', 'info');

    const fd = new FormData();
    fd.append('job_id', state.selectedJobId);
    fd.append('image', state.selectedFile);
    fd.append('conf', confRange.value);

    try {
        const r = await fetch('/api/inference', { method: 'POST', body: fd });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
        renderResult(data);
        setStatus(`Done. ${data.count} detection(s).`, 'success');
    } catch (e) {
        setStatus(`Error: ${e.message}`, 'danger');
    } finally {
        updateRunBtn();
    }
}

function renderResult(data) {
    outputPreview.src = `${data.image_url}?t=${Date.now()}`;
    outputPreview.style.background = '#fff';
    detCount.textContent = data.count;
    detBody.innerHTML = '';
    (data.boxes || []).forEach((b, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${i + 1}</td>
            <td>${escapeHtml(b.label)}</td>
            <td>${(b.conf * 100).toFixed(1)}%</td>
            <td>${b.x1}, ${b.y1}, ${b.x2}, ${b.y2}</td>
        `;
        detBody.appendChild(tr);
    });
}

fetchModels();
document.getElementById('refreshModels').addEventListener('click', fetchModels);
