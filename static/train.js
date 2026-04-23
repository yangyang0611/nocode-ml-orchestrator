let _me = null;

document.addEventListener('DOMContentLoaded', () => {
    loadDatasets();
    fetch('/api/auth/me').then(r => r.json()).then(d => { _me = d && d.username; });
    loadGpuStrip();
    setInterval(loadGpuStrip, 3000);
});

function loadGpuStrip() {
    fetch('/api/resources')
        .then(r => r.json())
        .then(renderGpuStrip)
        .catch(() => {});
}

function renderGpuStrip(gpus) {
    const el = document.getElementById('gpuStrip');
    if (!Array.isArray(gpus) || !gpus.length) {
        el.innerHTML = '<div class="text-muted" style="font-size:.82rem;">No GPUs detected.</div>';
        return;
    }
    const freeCount = gpus.filter(g => g.status !== 'occupied').length;
    document.getElementById('gpuStripHint').textContent =
        `Live · ${freeCount}/${gpus.length} free`;

    el.innerHTML = gpus.map(g => {
        const occupied = g.status === 'occupied';
        const mine = occupied && _me && g.owner_user === _me;
        const cls = mine ? 'mine' : (occupied ? 'busy' : 'free');
        const badgeCls = mine ? 'b-mine' : (occupied ? 'b-busy' : 'b-free');
        const badgeText = mine ? 'Your job' : (occupied ? 'Busy' : 'Free');
        const memPct = g.memory_total ? Math.round(g.memory_used / g.memory_total * 100) : 0;
        const ownerLine = occupied
            ? `<div class="gpu-mini-line"><span>Owner</span><span><strong>${g.owner_user || '—'}</strong></span></div>`
            : `<div class="gpu-mini-line" style="color:#059669;"><span>Ready to use</span><span>${g.memory_free} MB free</span></div>`;
        return `
        <div class="gpu-mini ${cls}">
            <div class="gpu-mini-head">
                <span>GPU ${g.gpu_id}</span>
                <span class="gpu-mini-badge ${badgeCls}">${badgeText}</span>
            </div>
            <div class="gpu-mini-line"><span>${g.name}</span><span>${g.utilization}%</span></div>
            <div class="gpu-mini-line"><span>VRAM</span><span>${g.memory_used} / ${g.memory_total} MB</span></div>
            <div class="gpu-mini-bar"><div style="width:${memPct}%"></div></div>
            ${ownerLine}
        </div>`;
    }).join('');
}

function loadDatasets() {
    const sel  = document.getElementById('dataset');
    const hint = document.getElementById('datasetHint');
    sel.disabled = true;

    fetch('/api/datasets')
        .then(r => r.json())
        .then(datasets => {
            sel.disabled = false;
            if (!datasets.length) {
                sel.innerHTML = '<option value="">No processed datasets found</option>';
                hint.innerHTML = 'No datasets yet. <a href="/">Go to Preprocessing first →</a>';
                return;
            }
            sel.innerHTML = '<option value="">-- Select a dataset --</option>' +
                datasets.map(d =>
                    `<option value="${d.name}">${d.name} (${d.size_mb} MB)</option>`
                ).join('');
            // Auto-select if only one dataset
            if (datasets.length === 1) sel.value = datasets[0].name;
        })
        .catch(() => {
            sel.disabled = false;
            sel.innerHTML = '<option value="">Failed to load datasets</option>';
        });
}

function selectPriority(el) {
    document.querySelectorAll('.priority-btn').forEach(b => {
        b.className = 'priority-btn';
    });
    const val = el.dataset.value;
    el.classList.add('sel-' + val);
    document.getElementById('priority').value = val;
}

function submitJob() {
    const dataset   = document.getElementById('dataset').value.trim();
    const model     = document.getElementById('model').value;
    const epochs    = parseInt(document.getElementById('epochs').value);
    const batchSize = parseInt(document.getElementById('batchSize').value);
    const imgsz     = parseInt(document.getElementById('imgsz').value);
    const lr0       = parseFloat(document.getElementById('lr0').value);
    const optimizer = document.getElementById('optimizer').value;
    const patience  = parseInt(document.getElementById('patience').value);
    const priority  = document.getElementById('priority').value;

    const errorBox = document.getElementById('errorBox');
    errorBox.style.display = 'none';

    if (!dataset) {
        showError('Please select a dataset.');
        return;
    }
    if (!model) {
        showError('Please complete model selection (Family → Version → Size).');
        return;
    }
    if (isNaN(epochs) || epochs < 1) {
        showError('Epochs must be at least 1.');
        return;
    }
    if (isNaN(batchSize) || batchSize < 1) {
        showError('Batch size must be at least 1.');
        return;
    }
    if (isNaN(imgsz) || imgsz < 32) {
        showError('Image size must be at least 32.');
        return;
    }
    if (isNaN(lr0) || lr0 <= 0) {
        showError('Learning rate must be greater than 0.');
        return;
    }
    if (isNaN(patience) || patience < 0) {
        showError('Patience must be 0 or greater.');
        return;
    }

    const btn = document.getElementById('submitBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-spinner"></span>Submitting...';

    fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset, model, epochs, batch_size: batchSize, imgsz, lr0, optimizer, patience, priority })
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        btn.textContent = 'Submit Job';
        if (data.job_id) {
            document.getElementById('resultJobId').textContent = data.job_id;
            document.getElementById('resultCard').style.display = 'block';
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
            localStorage.setItem('mlorch_step2_done', '1');
        } else {
            showError(data.error || 'Unknown error');
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.textContent = 'Submit Job';
        showError('Request failed: ' + err);
    });
}

function showError(msg) {
    const box = document.getElementById('errorBox');
    box.textContent = msg;
    box.style.display = 'block';
}

function resetForm() {
    document.getElementById('resultCard').style.display = 'none';
    document.getElementById('errorBox').style.display = 'none';
    document.getElementById('epochs').value = 10;
    document.getElementById('batchSize').value = 16;
    document.getElementById('imgsz').value = 640;
    document.getElementById('lr0').value = 0.01;
    document.getElementById('optimizer').value = 'auto';
    document.getElementById('patience').value = 50;
    // Reset model selector to default (YOLO → YOLOv8 → m)
    resetModelSelector();
    // Reset priority to medium
    document.querySelectorAll('.priority-btn').forEach(b => b.className = 'priority-btn');
    document.querySelector('[data-value="medium"]').classList.add('sel-medium');
    document.getElementById('priority').value = 'medium';
    // Reload datasets
    loadDatasets();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
