// ── State ─────────────────────────────────────────────────────────────────────
let _me = null;                              // current username
let _jobFilter = 'all';                      // 'all' | 'me'

// ── Polling ───────────────────────────────────────────────────────────────────
function fetchAll() {
    const jobsUrl = _jobFilter === 'me' ? '/api/jobs?owner=me' : '/api/jobs';
    Promise.all([
        fetch('/api/resources').then(r => r.json()),
        fetch(jobsUrl).then(r => r.json()),
        fetch('/api/queue').then(r => r.json()),
    ]).then(([gpus, jobs, queue]) => {
        renderGPUs(gpus);
        renderQueue(queue);
        renderJobs(Array.isArray(jobs) ? jobs : []);
        document.getElementById('lastUpdated').textContent =
            'Updated ' + new Date().toLocaleTimeString();
    }).catch(err => console.error('Dashboard fetch error:', err));
}

function setJobFilter(f) {
    _jobFilter = f;
    document.querySelectorAll('.jobs-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === f));
    fetchAll();
}

document.addEventListener('DOMContentLoaded', () => {
    fetch('/api/auth/me').then(r => r.json()).then(d => { _me = d && d.username; });
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
        const memPct   = g.memory_total ? Math.round(g.memory_used / g.memory_total * 100) : 0;
        const utilColor = utilPct >= 80 ? 'danger' : utilPct >= 50 ? 'warning' : 'success';
        const memColor  = memPct  >= 80 ? 'danger' : memPct  >= 50 ? 'warning' : 'success';

        const isOccupied = g.status === 'occupied';
        const isMine = isOccupied && _me && g.owner_user === _me;
        const statusBadge = isOccupied
            ? `<span class="badge ${isMine ? 'badge-success' : 'badge-primary'} ml-2">${isMine ? 'Yours' : 'Occupied'}</span>`
            : '<span class="badge badge-light ml-2" style="background:#d1fae5;color:#065f46;">Free</span>';

        const ownerLine = isOccupied
            ? `<div class="gpu-logical">
                 <div><span class="lbl">Owner</span> <strong>${g.owner_user || '—'}</strong></div>
                 <div><span class="lbl">Job</span> <code>${g.job_id ? g.job_id.slice(0,8) : '—'}</code></div>
               </div>`
            : `<div class="gpu-logical gpu-logical-free">Available · ${g.memory_free} MB free</div>`;

        return `
        <div class="col-md-6 mb-3">
          <div class="gpu-card">
            <div class="gpu-name">GPU ${g.gpu_id} · ${g.name} ${statusBadge}</div>
            ${ownerLine}
            <div class="gpu-section-label">Physical</div>
            <div class="gpu-stat d-flex justify-content-between">
              <span>Utilization</span><span>${utilPct}%</span>
            </div>
            <div class="progress">
              <div class="progress-bar bg-${utilColor}" style="width:${utilPct}%"></div>
            </div>
            <div class="gpu-stat d-flex justify-content-between">
              <span>VRAM</span>
              <span>${g.memory_used} / ${g.memory_total} MB (${memPct}%)</span>
            </div>
            <div class="progress">
              <div class="progress-bar bg-${memColor}" style="width:${memPct}%"></div>
            </div>
            <div class="gpu-stat">Temperature: <strong>${g.temperature}°C</strong></div>
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
        const emptyMsg = _jobFilter === 'me'
            ? `<div style="font-weight:700; font-size:1rem; margin-bottom:6px;">You have no training jobs yet</div>
               <div style="color:#6b7280; font-size:.875rem; margin-bottom:20px;">Submit one to see it listed here.</div>`
            : `<div style="font-weight:700; font-size:1rem; margin-bottom:6px;">No training jobs yet</div>
               <div style="color:#6b7280; font-size:.875rem; margin-bottom:20px;">Start by preprocessing your dataset, then submit a training job.</div>`;
        tbody.innerHTML = `
        <tr><td colspan="10">
            <div style="text-align:center; padding:40px 20px;">
                <div style="font-size:2rem; margin-bottom:12px;">🤖</div>
                ${emptyMsg}
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
        const owner     = job.user || '—';
        const ownerCls  = _me && owner === _me ? 'owner-me' : 'owner-other';

        return `
        <tr>
          <td><input type="checkbox" class="job-cb" value="${id}" ${checked} onchange="updateDeleteBtn()"></td>
          <td><code style="font-size:.8rem; cursor:pointer; text-decoration:underline dotted;" title="Click to see details" onclick="showDetails('${id}')">${short}</code></td>
          <td><span class="owner-chip ${ownerCls}">${owner}</span></td>
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
                    onclick="showDetails('${id}')">Details</button>
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
    Promise.allSettled(ids.map(id =>
        fetch(`/api/jobs/${id}`, { method: 'DELETE' }).then(r => {
            if (!r.ok) throw new Error(`${id.slice(0,8)}: HTTP ${r.status}`);
            return r.json();
        })
    )).then(results => {
        const failed = results.filter(r => r.status === 'rejected');
        if (failed.length) {
            alert(`Deleted ${ids.length - failed.length}/${ids.length}. Failures:\n` +
                  failed.map(r => r.reason.message).join('\n'));
        }
        fetchAll();
    });
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

function fmtTs(ts) {
    if (!ts) return '-';
    const d = new Date(ts);
    return isNaN(d) ? ts : d.toLocaleString();
}

function showDetails(jobId) {
    document.getElementById('detailsJobId').textContent = jobId.slice(0, 8);
    document.getElementById('detailsContent').innerHTML = 'Loading...';
    $('#detailsModal').modal('show');

    fetch(`/api/jobs/${jobId}`)
        .then(r => r.json())
        .then(job => {
            if (job.error) {
                document.getElementById('detailsContent').textContent = job.error;
                return;
            }

            const row = (k, v) => `
                <tr>
                    <th style="width:180px; font-weight:600; color:#374151;">${k}</th>
                    <td><code style="font-size:.85rem;">${v === '' || v === undefined || v === null ? '-' : v}</code></td>
                </tr>`;

            const statusCls = STATUS_CLASS[job.status] || 's-pending';
            const gpuLabel = (job.gpu_id === '' || job.gpu_id === undefined || job.gpu_id === null)
                ? '-' : `GPU ${job.gpu_id}`;

            document.getElementById('detailsContent').innerHTML = `
                <div style="margin-bottom:12px;">
                    <span class="status-badge ${statusCls}">${job.status || '-'}</span>
                    <span class="priority-dot p-${job.priority || 'medium'}"></span>
                    <span style="font-size:.9rem; color:#6b7280;">${job.priority || '-'} priority</span>
                </div>

                <h6 style="margin-top:12px; font-weight:700;">Training Parameters</h6>
                <table class="table table-sm table-bordered">
                    <tbody>
                        ${row('Model', job.model)}
                        ${row('Epochs', job.epochs)}
                        ${row('Batch Size', job.batch_size)}
                        ${row('Image Size', job.imgsz)}
                        ${row('Learning Rate (lr0)', job.lr0)}
                        ${row('Optimizer', job.optimizer)}
                        ${row('Patience', job.patience)}
                        ${row('Workers', job.workers)}
                        ${row('Dataset', job.dataset)}
                    </tbody>
                </table>

                <h6 style="margin-top:16px; font-weight:700;">Execution</h6>
                <table class="table table-sm table-bordered">
                    <tbody>
                        ${row('Job ID', job.job_id)}
                        ${row('User', job.user)}
                        ${row('GPU', gpuLabel)}
                        ${row('Container ID', job.container_id ? job.container_id.slice(0, 12) : '-')}
                        ${row('Submitted', fmtTs(job.submitted_at))}
                        ${row('Started', fmtTs(job.started_at))}
                        ${row('Finished', fmtTs(job.finished_at))}
                    </tbody>
                </table>
            `;
        })
        .catch(err => {
            document.getElementById('detailsContent').textContent = 'Error: ' + err;
        });
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
