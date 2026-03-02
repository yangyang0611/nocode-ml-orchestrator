document.addEventListener('DOMContentLoaded', loadDatasets);

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
    const priority  = document.getElementById('priority').value;

    const errorBox = document.getElementById('errorBox');
    errorBox.style.display = 'none';

    if (!dataset) {
        showError('Please select a dataset.');
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

    const btn = document.getElementById('submitBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-spinner"></span>Submitting...';

    fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset, model, epochs, batch_size: batchSize, priority })
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        btn.textContent = 'Submit Job';
        if (data.job_id) {
            document.getElementById('resultJobId').textContent = data.job_id;
            document.getElementById('resultCard').style.display = 'block';
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
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
    // Reset model to nano
    document.querySelectorAll('.model-card').forEach(c => c.classList.remove('selected'));
    document.querySelector('[data-model="yolov8n.pt"]').classList.add('selected');
    document.getElementById('model').value = 'yolov8n.pt';
    // Reset priority to medium
    document.querySelectorAll('.priority-btn').forEach(b => b.className = 'priority-btn');
    document.querySelector('[data-value="medium"]').classList.add('sel-medium');
    document.getElementById('priority').value = 'medium';
    // Reload datasets
    loadDatasets();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
