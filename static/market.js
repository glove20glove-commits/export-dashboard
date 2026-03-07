/* market.js - KOSPI vs Export Correlation Chart */

const API = '';
let chart = null;

// --- Helpers ---
function num(v) { return v == null ? '-' : v.toLocaleString(); }
function pct(v) { return v == null ? '-' : v.toFixed(1) + '%'; }

// --- Year selectors ---
function initYearSelectors() {
    const fromSel = document.getElementById('sel-year-from');
    const toSel = document.getElementById('sel-year-to');
    const now = new Date().getFullYear();
    for (let y = 2015; y <= now; y++) {
        fromSel.add(new Option(y, y));
        toSel.add(new Option(y, y));
    }
    fromSel.value = now - 5;
    toSel.value = now;
    fromSel.onchange = toSel.onchange = loadAll;
}

// --- API calls ---
async function fetchJSON(url) {
    const resp = await fetch(API + url);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return resp.json();
}

async function loadAll() {
    const yFrom = document.getElementById('sel-year-from').value;
    const yTo = document.getElementById('sel-year-to').value;

    const [kospi, semi, total] = await Promise.all([
        fetchJSON(`/api/market/index?code=KOSPI&year_from=${yFrom}&year_to=${yTo}`),
        fetchJSON(`/api/market/exports?category=semiconductor&year_from=${yFrom}&year_to=${yTo}`),
        fetchJSON(`/api/market/exports?category=total&year_from=${yFrom}&year_to=${yTo}`),
    ]);

    renderChart(kospi, semi, total);
    renderTable(kospi, semi, total);
    renderSummary(kospi, semi, total);
}

// --- Chart ---
function renderChart(kospi, semi, total) {
    // Build maps
    const kospiMap = {};
    kospi.forEach(d => { kospiMap[d.year + '-' + d.month] = d.close_price; });

    const semiAmtMap = {};
    const semiRateMap = {};
    semi.forEach(d => {
        semiAmtMap[d.year + '-' + d.month] = Math.round(d.export_amt / 1000); // 천불 → 백만불
        semiRateMap[d.year + '-' + d.month] = d.export_rate;
    });

    const totalRateMap = {};
    total.forEach(d => { totalRateMap[d.year + '-' + d.month] = d.export_rate; });

    // Union of all months, sorted
    const allMonths = [...new Set([
        ...Object.keys(kospiMap),
        ...Object.keys(semiAmtMap),
        ...Object.keys(totalRateMap),
    ])].sort();

    const labels = allMonths;
    const kospiData = allMonths.map(m => kospiMap[m] ?? null);
    const semiData = allMonths.map(m => semiAmtMap[m] ?? null);
    const semiRateData = allMonths.map(m => semiRateMap[m] ?? null);
    const totalRateData = allMonths.map(m => totalRateMap[m] ?? null);

    if (chart) chart.destroy();

    const ctx = document.getElementById('correlation-chart').getContext('2d');
    chart = new Chart(ctx, {
        data: {
            labels,
            datasets: [
                {
                    type: 'bar',
                    label: '반도체 수출 (백만불)',
                    data: semiData,
                    yAxisID: 'y',
                    backgroundColor: 'rgba(37,99,235,0.4)',
                    borderColor: '#2563eb',
                    borderWidth: 1,
                    order: 4,
                },
                {
                    type: 'line',
                    label: 'KOSPI (pt)',
                    data: kospiData,
                    yAxisID: 'y1',
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239,68,68,0.1)',
                    borderWidth: 2,
                    pointRadius: 2,
                    tension: 0.3,
                    fill: false,
                    order: 1,
                },
                {
                    type: 'line',
                    label: '반도체 수출 증감률 (%)',
                    data: semiRateData,
                    yAxisID: 'y2',
                    borderColor: '#f59e0b',
                    borderWidth: 2,
                    pointRadius: 2,
                    tension: 0.3,
                    borderDash: [5, 3],
                    fill: false,
                    order: 2,
                },
                {
                    type: 'line',
                    label: '총수출 증감률 (%)',
                    data: totalRateData,
                    yAxisID: 'y2',
                    borderColor: '#10b981',
                    borderWidth: 2,
                    pointRadius: 2,
                    tension: 0.3,
                    fill: false,
                    order: 3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label(ctx) {
                            const v = ctx.parsed.y;
                            if (v == null) return null;
                            if (ctx.dataset.yAxisID === 'y') return `${ctx.dataset.label}: ${num(v)}`;
                            if (ctx.dataset.yAxisID === 'y1') return `${ctx.dataset.label}: ${v.toFixed(2)}`;
                            return `${ctx.dataset.label}: ${v.toFixed(1)}%`;
                        }
                    }
                },
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, pointStyle: 'circle', padding: 16 },
                },
            },
            scales: {
                x: {
                    ticks: {
                        callback(val, idx) {
                            const lbl = this.getLabelForValue(val);
                            return lbl.endsWith('-01') ? lbl.slice(0, 4) : '';
                        },
                        maxRotation: 0,
                    },
                    grid: { display: false },
                },
                y: {
                    position: 'left',
                    title: { display: true, text: '반도체 수출 (백만불)', color: '#2563eb' },
                    ticks: { color: '#2563eb', callback: v => num(v) },
                    grid: { color: 'rgba(0,0,0,0.06)' },
                },
                y1: {
                    position: 'right',
                    title: { display: true, text: 'KOSPI (pt)', color: '#ef4444' },
                    ticks: { color: '#ef4444', callback: v => num(v) },
                    grid: { drawOnChartArea: false },
                },
                y2: {
                    position: 'right',
                    title: { display: true, text: '증감률 (%)', color: '#10b981' },
                    ticks: { color: '#10b981', callback: v => v + '%' },
                    grid: { drawOnChartArea: false },
                    offset: true,
                },
            },
        },
    });
}

// --- Summary Cards ---
function renderSummary(kospi, semi, total) {
    const container = document.getElementById('summary-cards');
    const cards = [];

    if (kospi.length) {
        const latest = kospi[kospi.length - 1];
        const prev = kospi.length >= 2 ? kospi[kospi.length - 2] : null;
        const change = prev ? ((latest.close_price - prev.close_price) / prev.close_price * 100).toFixed(1) : '-';
        const color = change > 0 ? '#ef4444' : change < 0 ? '#2563eb' : '#6b7280';
        cards.push(`<div class="card">
            <div class="card-label">KOSPI (${latest.year}-${latest.month})</div>
            <div class="card-value">${latest.close_price.toFixed(2)}</div>
            <div style="color:${color}; font-size:13px;">전월 대비 ${change}%</div>
        </div>`);
    }

    if (semi.length) {
        const latest = semi[semi.length - 1];
        const amt = Math.round(latest.export_amt / 1000);
        cards.push(`<div class="card">
            <div class="card-label">반도체 수출 (${latest.year}-${latest.month})</div>
            <div class="card-value">${num(amt)} 백만불</div>
            <div style="color:${latest.export_rate >= 0 ? '#10b981' : '#ef4444'}; font-size:13px;">YoY ${pct(latest.export_rate)}</div>
        </div>`);
    }

    if (total.length) {
        const latest = total[total.length - 1];
        const color = latest.export_rate >= 0 ? '#10b981' : '#ef4444';
        cards.push(`<div class="card">
            <div class="card-label">총수출 증감률 (${latest.year}-${latest.month})</div>
            <div class="card-value" style="color:${color}">${pct(latest.export_rate)}</div>
        </div>`);
    }

    container.innerHTML = cards.join('');
}

// --- Data Table ---
function renderTable(kospi, semi, total) {
    const kospiMap = {};
    kospi.forEach(d => { kospiMap[d.year + '-' + d.month] = d.close_price; });
    const semiAmtMap = {};
    const semiRateMap = {};
    semi.forEach(d => {
        semiAmtMap[d.year + '-' + d.month] = Math.round(d.export_amt / 1000);
        semiRateMap[d.year + '-' + d.month] = d.export_rate;
    });
    const totalRateMap = {};
    total.forEach(d => { totalRateMap[d.year + '-' + d.month] = d.export_rate; });

    const allMonths = [...new Set([
        ...Object.keys(kospiMap), ...Object.keys(semiAmtMap), ...Object.keys(totalRateMap),
    ])].sort().reverse();

    const tbody = document.getElementById('data-tbody');
    tbody.innerHTML = allMonths.map(m => {
        const k = kospiMap[m];
        const s = semiAmtMap[m];
        const sr = semiRateMap[m];
        const tr = totalRateMap[m];
        return `<tr>
            <td>${m}</td>
            <td>${k != null ? k.toFixed(2) : '-'}</td>
            <td>${s != null ? num(s) : '-'}</td>
            <td class="${sr >= 0 ? 'positive' : 'negative'}">${sr != null ? pct(sr) : '-'}</td>
            <td class="${tr >= 0 ? 'positive' : 'negative'}">${tr != null ? pct(tr) : '-'}</td>
        </tr>`;
    }).join('');
}

// --- Fetch Buttons ---
document.getElementById('btn-fetch-kospi').onclick = async () => {
    const btn = document.getElementById('btn-fetch-kospi');
    btn.disabled = true;
    btn.textContent = '가져오는 중...';
    try {
        const resp = await fetch(API + '/api/market/fetch-index', { method: 'POST' });
        const data = await resp.json();
        alert(`KOSPI ${data.fetched}개월 데이터 저장 완료`);
        await loadAll();
    } catch (e) {
        alert('KOSPI 데이터 가져오기 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'KOSPI 가져오기';
    }
};

document.getElementById('btn-fetch-semi').onclick = async () => {
    const btn = document.getElementById('btn-fetch-semi');
    btn.disabled = true;
    btn.textContent = '가져오는 중...';
    try {
        const yFrom = document.getElementById('sel-year-from').value;
        const yTo = document.getElementById('sel-year-to').value;
        const resp = await fetch(API + `/api/market/fetch-exports?year_from=${yFrom}&year_to=${yTo}`, { method: 'POST' });
        const data = await resp.json();
        alert(`반도체 수출 ${data.fetched}개월 데이터 저장 (${data.skipped}개월 스킵)`);
        await loadAll();
    } catch (e) {
        alert('반도체 수출 데이터 가져오기 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '반도체수출 가져오기';
    }
};

// --- Import total export data ---
document.getElementById('btn-import').onclick = async () => {
    const text = document.getElementById('import-textarea').value.trim();
    if (!text) return;

    const rows = [];
    for (const line of text.split('\n')) {
        const parts = line.trim().split(',');
        if (parts.length < 2) continue;
        const [ym, rate] = parts;
        const [year, month] = ym.split('-');
        if (!year || !month) continue;
        rows.push({ year, month, export_amt: 0, export_rate: parseFloat(rate) || 0 });
    }

    if (!rows.length) { alert('파싱 가능한 데이터가 없습니다.'); return; }

    try {
        const resp = await fetch(API + '/api/market/import-exports', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: 'total', rows }),
        });
        const data = await resp.json();
        alert(`총수출 증감률 ${data.imported}개월 임포트 완료`);
        document.getElementById('import-textarea').value = '';
        await loadAll();
    } catch (e) {
        alert('임포트 실패: ' + e.message);
    }
};

// --- Init ---
initYearSelectors();
loadAll();
