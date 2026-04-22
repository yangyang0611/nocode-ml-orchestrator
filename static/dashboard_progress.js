(function () {
    const sel     = document.getElementById('progressJobSelect');
    const emptyEl = document.getElementById('progressEmpty');
    const wrapEl  = document.getElementById('progressChartWrap');
    const metaEl  = document.getElementById('progressMeta');
    const canvas  = document.getElementById('lossChart');

    let chart = null;
    let currentJob = null;

    const SERIES = [
        { key: 'train/box_loss', label: 'train/box', color: '#4361ee' },
        { key: 'train/cls_loss', label: 'train/cls', color: '#ef4444' },
        { key: 'val/box_loss',   label: 'val/box',   color: '#4361ee', dashed: true },
        { key: 'val/cls_loss',   label: 'val/cls',   color: '#ef4444', dashed: true },
    ];

    const mark = s => ({ pending:'⏳', running:'▶', completed:'✓', failed:'✗', cancelled:'⊘' }[s] || '');

    async function loadJobs() {
        const r = await fetch('/api/jobs');
        const jobs = await r.json();
        const prev = sel.value;
        sel.innerHTML = '<option value="">— select a job —</option>';
        jobs.forEach(j => {
            const opt = document.createElement('option');
            opt.value = j.job_id;
            opt.textContent = `${mark(j.status)} ${j.job_id.slice(0,8)} · ${j.model || ''} · ${j.epochs || '?'}ep · ${j.status}`;
            sel.appendChild(opt);
        });
        if (prev && jobs.some(j => j.job_id === prev)) sel.value = prev;
    }

    async function loadMetrics(jobId) {
        const r = await fetch(`/api/jobs/${jobId}/metrics`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    }

    function render(data) {
        const { epochs, series } = data;
        if (!epochs.length) {
            wrapEl.style.display = 'none';
            emptyEl.style.display = 'block';
            emptyEl.textContent = 'No metrics yet — results.csv is written after the first epoch finishes.';
            return;
        }
        emptyEl.style.display = 'none';
        wrapEl.style.display  = 'block';

        const datasets = SERIES
            .filter(s => series[s.key] && series[s.key].length)
            .map(s => ({
                label: s.label,
                data: series[s.key],
                borderColor: s.color,
                backgroundColor: s.color + '22',
                borderDash: s.dashed ? [5, 4] : [],
                borderWidth: 2,
                pointRadius: 2,
                tension: 0.25,
            }));

        if (!chart) {
            chart = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: { labels: epochs, datasets },
                options: {
                    responsive: true,
                    animation: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        x: { title: { display: true, text: 'epoch' } },
                        y: { title: { display: true, text: 'loss' } },
                    },
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                    },
                },
            });
        } else {
            chart.data.labels = epochs;
            chart.data.datasets = datasets;
            chart.update('none');
        }

        const last = epochs[epochs.length - 1];
        const m50 = series['metrics/mAP50(B)'];
        const m5095 = series['metrics/mAP50-95(B)'];
        const parts = [`epochs: ${last}`];
        if (m50)   parts.push(`mAP50: ${m50[m50.length-1].toFixed(4)}`);
        if (m5095) parts.push(`mAP50-95: ${m5095[m5095.length-1].toFixed(4)}`);
        metaEl.textContent = parts.join(' · ');
    }

    async function refreshCurrent() {
        if (!currentJob) return;
        try {
            const data = await loadMetrics(currentJob);
            render(data);
        } catch (e) {
            emptyEl.textContent = `Failed to load metrics: ${e.message}`;
            emptyEl.style.display = 'block';
            wrapEl.style.display = 'none';
        }
    }

    sel.addEventListener('change', async () => {
        currentJob = sel.value || null;
        if (!currentJob) {
            wrapEl.style.display = 'none';
            emptyEl.style.display = 'block';
            emptyEl.textContent = 'Select a job to view its loss curve.';
            return;
        }
        await refreshCurrent();
    });

    loadJobs();
    // Dashboard already polls /api/jobs every 3s via fetchAll; piggy-back to
    // refresh the chart + dropdown at the same cadence.
    setInterval(async () => {
        await loadJobs();
        await refreshCurrent();
    }, 5000);
})();
