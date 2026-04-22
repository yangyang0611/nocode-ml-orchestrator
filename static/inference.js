const state = {
    selectedModelId: null,
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

const uploadBtn     = document.getElementById('uploadModelBtn');
const modelFileInput= document.getElementById('modelFileInput');
const uploadStatus  = document.getElementById('uploadStatus');

function fmtTime(iso) {
    if (!iso) return '-';
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
        ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
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
        modelList.innerHTML = '<div class="empty-state">No models yet. Train one from <a href="/train">Submit Job</a> or upload your own <code>.pt</code>.</div>';
        return;
    }
    modelList.innerHTML = '';
    models.forEach(m => {
        const row = document.createElement('div');
        row.className = 'model-row';
        row.dataset.modelId = m.id;
        const isUploaded = m.source === 'uploaded';
        const pillCls = isUploaded ? 'src-uploaded' : 'src-trained';
        const pillTxt = isUploaded ? 'UPLOADED' : 'TRAINED';

        const title = isUploaded
            ? `${escapeHtml(m.name)}`
            : `${m.id.slice(0, 8)} · ${escapeHtml(m.model)}`;
        const meta = isUploaded
            ? `${escapeHtml(m.filename || '')} · ${m.size_mb} MB · uploaded ${fmtTime(m.uploaded_at)}`
            : `${escapeHtml(m.dataset || '')} · ${m.epochs} epochs · ${m.size_mb} MB · finished ${fmtTime(m.finished_at)}`;

        row.innerHTML = `
            <div style="flex:1; min-width:0;">
                <div class="model-jobid">
                    <span class="source-pill ${pillCls}">${pillTxt}</span>${title}
                </div>
                <div class="model-meta">${meta}</div>
            </div>
            <div class="d-flex align-items-center" style="gap:6px;">
                ${isUploaded
                    ? `<button class="model-delete" data-del="${m.id}" title="Remove">✕</button>`
                    : `<span class="status-badge s-${m.status || 'completed'}">${m.status || 'completed'}</span>`}
            </div>
        `;
        row.addEventListener('click', (e) => {
            if (e.target.closest('[data-del]')) return;
            selectModel(m.id);
        });
        const delBtn = row.querySelector('[data-del]');
        if (delBtn) delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteModel(m.id, m.name);
        });
        modelList.appendChild(row);
    });
}

function selectModel(modelId) {
    state.selectedModelId = modelId;
    [...modelList.querySelectorAll('.model-row')].forEach(r => {
        r.classList.toggle('selected', r.dataset.modelId === modelId);
    });
    updateRunBtn();
}

async function deleteModel(id, name) {
    if (!confirm(`Remove uploaded model "${name}"? This cannot be undone.`)) return;
    try {
        const r = await fetch(`/api/models/${id}`, { method: 'DELETE' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        if (state.selectedModelId === id) {
            state.selectedModelId = null;
            updateRunBtn();
        }
        await fetchModels();
    } catch (e) {
        setUploadStatus(`Delete failed: ${e.message}`, 'danger');
    }
}

function updateRunBtn() {
    runBtn.disabled = !(state.selectedModelId && state.selectedFile);
}

// ── Upload user model ────────────────────────────────────────────────────────
function setUploadStatus(msg, type = 'info') {
    const colors = { info: 'var(--muted)', danger: 'var(--danger)', success: 'var(--success)' };
    uploadStatus.style.color = colors[type] || colors.info;
    uploadStatus.innerHTML = msg;
    uploadStatus.style.display = msg ? 'block' : 'none';
}

uploadBtn.addEventListener('click', () => modelFileInput.click());

modelFileInput.addEventListener('change', async (e) => {
    const f = e.target.files[0];
    e.target.value = '';
    if (!f) return;
    if (!/\.pt$/i.test(f.name)) {
        setUploadStatus('Only .pt files are accepted.', 'danger');
        return;
    }
    const mb = f.size / 1024 / 1024;
    setUploadStatus(`<span class="spinner-ring"></span>Uploading ${escapeHtml(f.name)} (${mb.toFixed(1)} MB)…`, 'info');
    const fd = new FormData();
    fd.append('model', f);
    try {
        const r = await fetch('/api/models/upload', { method: 'POST', body: fd });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
        setUploadStatus(`Uploaded ${escapeHtml(data.name)} (${data.size_mb} MB).`, 'success');
        await fetchModels();
        selectModel(data.id);
    } catch (e) {
        setUploadStatus(`Upload failed: ${e.message}`, 'danger');
    }
});

// ── File handling for inference image ────────────────────────────────────────
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
    if (!state.selectedModelId || !state.selectedFile) return;
    runBtn.disabled = true;
    setStatus('<span class="spinner-ring"></span>Running inference in container — this may take 20–60 s on first run…', 'info');

    const fd = new FormData();
    fd.append('model_id', state.selectedModelId);
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
