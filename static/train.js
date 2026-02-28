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
        showError('Please enter a dataset filename.');
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
    btn.textContent = 'Submitting...';

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
