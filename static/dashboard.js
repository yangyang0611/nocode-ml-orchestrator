// ── Polling ───────────────────────────────────────────────────────────────────
function fetchAll() {
    Promise.all([
        fetch('/api/resources').then(r => r.json()),
        fetch('/api/jobs').then(r => r.json()),
        fetch('/api/queue').then(r => r.json()),
    ]).then(([gpus, jobs, queue]) => {
        renderGPUs(gpus);
        renderQueue(queue);
        renderJobs(jobs);
        document.getElementById('lastUpdated').textContent =
            'Updated ' + new Date().toLocaleTimeString();
    }).catch(err => console.error('Dashboard fetch error:', err));
}

document.addEventListener('DOMContentLoaded', () => {
    fetchAll();
    setInterval(fetchAll, 3000);
});

// ── GPU Panel ─────────────────────────────────────────────────────────────────
function renderGPUs(gpus) {
    const panel = document.getElementById('gpuPanel');
    if (!gpus.length) {
        panel.innerHTML = '<div class="col"><p class="text-muted">No GPU detected.</p></div>';
        return;
    }
    panel.innerHTML = gpus.map(g => {
        const utilPct  = g.utilization;
        const memPct   = Math.round(g.memory_used / g.memory_total * 100);
        const utilColor = utilPct >= 80 ? 'danger' : utilPct >= 50 ? 'warning' : 'success';
        const memColor  = memPct  >= 80 ? 'danger' : memPct  >= 50 ? 'warning' : 'success';
        const statusBadge = g.status === 'occupied'
            ? '<span class="badge badge-primary ml-2">Occupied</span>'
            : '<span class="badge badge-success ml-2">Free</span>';

        return `
        <div class="col-md-6 mb-3">
          <div class="gpu-card">
            <div class="gpu-name">${g.name} ${statusBadge}</div>
            <div class="gpu-stat d-flex justify-content-between">
              <span>GPU Utilization</span><span>${utilPct}%</span>
            </div>
            <div class="progress">
              <div class="progress-bar bg-${utilColor}" style="width:${utilPct}%"></div>
            </div>
            <div class="gpu-stat d-flex justify-content-between">
              <span>Memory</span>
              <span>${g.memory_used} / ${g.memory_total} MB (${memPct}%)</span>
            </div>
            <div class="progress">
              <div class="progress-bar bg-${memColor}" style="width:${memPct}%"></div>
            </div>
            <div class="gpu-stat">Temperature: <strong>${g.temperature}°C</strong>
              ${g.job_id ? `&nbsp;|&nbsp; Running: <code style="font-size:.75rem">${g.job_id.slice(0,8)}</code>` : ''}
            </div>
          </div>
        </div>`;
    }).join('');
}

// ── Queue Panel ───────────────────────────────────────────────────────────────
function renderQueue(queue) {
    document.getElementById('qHigh').textContent   = queue.high   ?? 0;
    document.getElementById('qMedium').textContent = queue.medium ?? 0;
    document.getElementById('qLow').textContent    = queue.low    ?? 0;
}

// ── Job Table ─────────────────────────────────────────────────────────────────
const STATUS_CLASS = {
    pending:   's-pending',
    running:   's-running',
    completed: 's-completed',
    failed:    's-failed',
    cancelled: 's-cancelled',
};

function renderJobs(jobs) {
    const tbody = document.getElementById('jobTableBody');

    // preserve checked state across refreshes
    const checkedIds = new Set(
        [...document.querySelectorAll('.job-cb:checked')].map(cb => cb.value)
    );

    if (!jobs.length) {
        tbody.innerHTML = `
        <tr><td colspan="9">
            <div style="text-align:center; padding:40px 20px;">
                <div style="font-size:2rem; margin-bottom:12px;">🤖</div>
                <div style="font-weight:700; font-size:1rem; margin-bottom:6px;">No training jobs yet</div>
                <div style="color:#6b7280; font-size:.875rem; margin-bottom:20px;">
                    Start by preprocessing your dataset, then submit a training job.
                </div>
                <a href="/" class="btn btn-outline-secondary btn-sm mr-2">Go to Preprocessing</a>
                <a href="/train" class="btn btn-primary btn-sm">Submit Training Job →</a>
            </div>
        </td></tr>`;
        updateDeleteBtn();
        return;
    }

    tbody.innerHTML = jobs.map(job => {
        const id        = job.job_id;
        const short     = id.slice(0, 8);
        const status    = job.status;
        const sCls      = STATUS_CLASS[status] || 's-pending';
        const pCls      = 'p-' + (job.priority || 'medium');
        const canCancel = status === 'pending' || status === 'running';
        const submitted = job.submitted_at
            ? new Date(job.submitted_at).toLocaleString()
            : '-';
        const checked   = checkedIds.has(id) ? 'checked' : '';

        return `
        <tr>
          <td><input type="checkbox" class="job-cb" value="${id}" ${checked} onchange="updateDeleteBtn()"></td>
          <td><code style="font-size:.8rem; cursor:default;" title="${id}">${short}</code></td>
          <td><span class="status-badge ${sCls}">${status}</span></td>
          <td>${job.model || '-'}</td>
          <td>${job.epochs || '-'}</td>
          <td>
            <span class="priority-dot ${pCls}"></span>
            ${job.priority || '-'}
          </td>
          <td style="font-size:.82rem;">${submitted}</td>
          <td>${job.gpu_id !== '' && job.gpu_id !== undefined ? 'GPU ' + job.gpu_id : '-'}</td>
          <td class="text-nowrap">
            <button class="btn btn-outline-secondary btn-sm mr-1"
                    onclick="showLogs('${id}')">Logs</button>
            ${canCancel ? `
            <button class="btn btn-outline-danger btn-sm"
                    onclick="cancelJob('${id}', this)">Cancel</button>` : ''}
          </td>
        </tr>`;
    }).join('');

    updateDeleteBtn();
}

function toggleSelectAll(cb) {
    document.querySelectorAll('.job-cb').forEach(jobCb => jobCb.checked = cb.checked);
    updateDeleteBtn();
}

function updateDeleteBtn() {
    const checked = document.querySelectorAll('.job-cb:checked');
    const total   = document.querySelectorAll('.job-cb');
    const btn     = document.getElementById('deleteSelectedBtn');
    const allCb   = document.getElementById('selectAllCb');

    if (checked.length > 0) {
        btn.style.display = 'inline-block';
        btn.textContent = `Delete Selected (${checked.length})`;
    } else {
        btn.style.display = 'none';
    }

    if (allCb) {
        allCb.checked       = total.length > 0 && checked.length === total.length;
        allCb.indeterminate = checked.length > 0 && checked.length < total.length;
    }
}

function deleteSelected() {
    const ids = [...document.querySelectorAll('.job-cb:checked')].map(cb => cb.value);
    if (!ids.length) return;
    if (!confirm(`Delete ${ids.length} job(s)? This cannot be undone.`)) return;
    Promise.all(ids.map(id =>
        fetch(`/api/jobs/${id}`, { method: 'DELETE' }).then(r => r.json())
    )).then(() => fetchAll())
      .catch(err => alert('Delete failed: ' + err));
}

// ── Actions ───────────────────────────────────────────────────────────────────
function cancelJob(jobId, btn) {
    if (!confirm('Cancel this job?')) return;
    btn.disabled = true;
    fetch(`/api/jobs/${jobId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(() => fetchAll())
        .catch(err => { btn.disabled = false; alert('Cancel failed: ' + err); });
}

function showLogs(jobId) {
    document.getElementById('logsJobId').textContent = jobId.slice(0, 8);
    document.getElementById('logsContent').textContent = 'Loading...';
    $('#logsModal').modal('show');

    fetch(`/api/jobs/${jobId}/logs`)
        .then(r => r.json())
        .then(data => {
            const logs = data.logs || '(no logs yet)';
            document.getElementById('logsContent').textContent = logs;
        })
        .catch(err => {
            document.getElementById('logsContent').textContent = 'Error: ' + err;
        });
}
