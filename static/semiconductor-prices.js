const API = '';

let rawRows = [];
let latestDate = null;
let sortBy = 'session_change_pct';
let sortDir = 'desc';
let semiChart = null;

function fmtNum(v, digits = 3) {
    if (v == null || Number.isNaN(Number(v))) return '-';
    return Number(v).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtPct(v) {
    if (v == null || Number.isNaN(Number(v))) return '-';
    const x = Number(v);
    return `${x > 0 ? '+' : ''}${x.toFixed(2)}%`;
}

function fmtDateTime(v) {
    if (!v) return '-';
    return String(v);
}

async function api(method, path) {
    const resp = await fetch(API + path, { method });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `${resp.status} ${resp.statusText}`);
    return data;
}

async function uploadCSV(path, file) {
    const fd = new FormData();
    fd.append('file', file);
    const resp = await fetch(API + path, { method: 'POST', body: fd });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `${resp.status} ${resp.statusText}`);
    return data;
}

function selectedMarket() {
    return document.getElementById('sel-market').value || 'ALL';
}

function selectedDays() {
    return Number(document.getElementById('sel-range').value || 90);
}

function uniqueSortedDates(rows) {
    return Array.from(new Set(rows.map(r => r.trading_date))).sort();
}

function computeLatestDate(rows) {
    const dates = uniqueSortedDates(rows);
    return dates.length ? dates[dates.length - 1] : null;
}

function filterLatestRows() {
    const market = selectedMarket();
    return rawRows.filter(r => r.trading_date === latestDate && (market === 'ALL' || r.market_type === market));
}

function compare(a, b, key) {
    const av = a[key];
    const bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;

    if (key === 'product_name' || key === 'market_type' || key === 'source_updated_at') {
        return String(av).localeCompare(String(bv), 'ko');
    }
    return Number(av) - Number(bv);
}

function sortRows(rows) {
    const out = [...rows];
    out.sort((a, b) => {
        const c = compare(a, b, sortBy);
        return sortDir === 'asc' ? c : -c;
    });
    return out;
}

function renderSummary() {
    const wrap = document.getElementById('summary-cards');
    const rows = filterLatestRows();
    const dramRows = rows.filter(r => r.market_type === 'DRAM');
    const nandRows = rows.filter(r => r.market_type === 'NAND');

    const avg = (arr, key) => {
        const vals = arr.map(x => Number(x[key])).filter(v => !Number.isNaN(v));
        if (!vals.length) return null;
        return vals.reduce((a, b) => a + b, 0) / vals.length;
    };

    const avgDramChg = avg(dramRows, 'session_change_pct');
    const avgNandChg = avg(nandRows, 'session_change_pct');

    wrap.innerHTML = `
        <div class="card">
            <div class="card-label">최신 기준일</div>
            <div class="card-value" style="font-size:1.4rem;">${latestDate || '-'}</div>
            <div class="card-sub">품목 ${rows.length.toLocaleString()}개</div>
        </div>
        <div class="card">
            <div class="card-label">DRAM 평균 변동률</div>
            <div class="card-value" style="font-size:1.4rem; color:${(avgDramChg ?? 0) >= 0 ? '#10b981' : '#ef4444'};">${fmtPct(avgDramChg)}</div>
            <div class="card-sub">DRAM ${dramRows.length.toLocaleString()}개</div>
        </div>
        <div class="card">
            <div class="card-label">NAND 평균 변동률</div>
            <div class="card-value" style="font-size:1.4rem; color:${(avgNandChg ?? 0) >= 0 ? '#10b981' : '#ef4444'};">${fmtPct(avgNandChg)}</div>
            <div class="card-sub">NAND ${nandRows.length.toLocaleString()}개</div>
        </div>
    `;
}

function renderChart() {
    const market = selectedMarket();
    const dates = uniqueSortedDates(rawRows);
    const buildSeries = (targetMarket) => {
        const map = {};
        dates.forEach(d => {
            const rows = rawRows.filter(r => r.trading_date === d && r.market_type === targetMarket);
            const vals = rows.map(x => Number(x.session_avg)).filter(v => !Number.isNaN(v));
            map[d] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
        });
        return dates.map(d => map[d]);
    };

    const datasets = [];
    if (market === 'ALL' || market === 'DRAM') {
        datasets.push({
            label: 'DRAM 평균',
            data: buildSeries('DRAM'),
            borderColor: '#2563eb',
            backgroundColor: '#2563eb22',
            tension: 0.2,
            pointRadius: 0,
            spanGaps: true,
        });
    }
    if (market === 'ALL' || market === 'NAND') {
        datasets.push({
            label: 'NAND 평균',
            data: buildSeries('NAND'),
            borderColor: '#f59e0b',
            backgroundColor: '#f59e0b22',
            tension: 0.2,
            pointRadius: 0,
            spanGaps: true,
        });
    }

    const canvas = document.getElementById('semi-chart');
    if (semiChart) semiChart.destroy();
    semiChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: { labels: dates, datasets },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { display: true } },
            scales: { x: { ticks: { maxTicksLimit: 12 } } },
        },
    });
}

function renderTable() {
    const tbody = document.getElementById('semi-tbody');
    const rows = sortRows(filterLatestRows());

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#64748b;">데이터가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map(r => {
        const pct = Number(r.session_change_pct);
        const pctColor = Number.isNaN(pct) ? '#64748b' : (pct >= 0 ? '#10b981' : '#ef4444');
        return `
            <tr>
                <td>${r.market_type}</td>
                <td style="text-align:left;">${r.product_name}</td>
                <td>${fmtNum(r.daily_high, 3)}</td>
                <td>${fmtNum(r.daily_low, 3)}</td>
                <td>${fmtNum(r.session_avg, 3)}</td>
                <td style="color:${pctColor}; font-weight:700;">${fmtPct(r.session_change_pct)}</td>
                <td>${fmtDateTime(r.source_updated_at)}</td>
            </tr>
        `;
    }).join('');

    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.dataset.sort === sortBy) th.classList.add(sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
    });
}

function renderAll() {
    latestDate = computeLatestDate(rawRows);
    renderSummary();
    renderChart();
    renderTable();
}

async function loadData() {
    const market = selectedMarket();
    const days = selectedDays();
    const data = await api('GET', `/api/semiconductor-prices?market=${encodeURIComponent(market)}&days=${days}`);
    rawRows = data.rows || [];
    renderAll();
}

async function refreshData() {
    const btn = document.getElementById('btn-refresh');
    const status = document.getElementById('status-msg');
    btn.disabled = true;
    btn.textContent = '갱신 중...';
    status.textContent = '';
    try {
        const out = await api('POST', '/api/semiconductor-prices/refresh');
        await loadData();
        status.textContent = `업데이트 완료 (${Number(out.inserted || 0).toLocaleString()}건)`;
    } catch (e) {
        status.textContent = `실패: ${e.message}`;
        alert(`반도체 가격 갱신 실패: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '데이터 갱신';
    }
}

async function importCSV() {
    const fileInput = document.getElementById('csv-file');
    const btn = document.getElementById('btn-import-csv');
    const status = document.getElementById('status-msg');
    const file = fileInput?.files?.[0];
    if (!file) {
        alert('CSV 파일을 먼저 선택해 주세요.');
        return;
    }

    btn.disabled = true;
    btn.textContent = '업로드 중...';
    status.textContent = '';
    try {
        const out = await uploadCSV('/api/semiconductor-prices/import-csv', file);
        await loadData();
        status.textContent = `CSV 반영 완료 (적재 ${out.imported || 0}건, 제외 ${out.skipped || 0}건)`;
        if (Number(out.error_count || 0) > 0) {
            console.warn('CSV import errors:', out.errors || []);
        }
    } catch (e) {
        status.textContent = `CSV 실패: ${e.message}`;
        alert(`CSV 업로드 실패: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'CSV 업로드';
    }
}

function downloadTemplateCSV() {
    window.location.href = '/api/semiconductor-prices/template-csv';
}

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('btn-refresh').addEventListener('click', refreshData);
    document.getElementById('btn-template-csv').addEventListener('click', downloadTemplateCSV);
    document.getElementById('btn-import-csv').addEventListener('click', importCSV);
    document.getElementById('sel-market').addEventListener('change', loadData);
    document.getElementById('sel-range').addEventListener('change', loadData);

    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const key = th.dataset.sort;
            if (sortBy === key) {
                sortDir = sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                sortBy = key;
                sortDir = key === 'product_name' || key === 'market_type' ? 'asc' : 'desc';
            }
            renderTable();
        });
    });

    try {
        await loadData();
        if (!rawRows.length) {
            await refreshData();
        }
    } catch {
        await refreshData();
    }
});
