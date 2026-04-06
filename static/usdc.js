const API = '';
let usdcChart = null;
let coinRows = { USDC: [], USDT: [], FDUSD: [] };

const COLORS = {
    USDC: '#2563eb',
    USDT: '#16a34a',
    FDUSD: '#f59e0b',
};

function fmtNum(v, digits = 0) {
    if (v == null) return '-';
    return Number(v).toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

function pct(curr, prev) {
    if (curr == null || prev == null || prev === 0) return null;
    return ((curr - prev) / prev) * 100;
}

async function fetchJSON(url) {
    const resp = await fetch(API + url);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `${resp.status} ${resp.statusText}`);
    return data;
}

async function postJSON(url) {
    const resp = await fetch(API + url, { method: 'POST' });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `${resp.status} ${resp.statusText}`);
    return data;
}

function selectedSymbols() {
    return Array.from(document.querySelectorAll('.sym-opt:checked')).map(el => el.value);
}

function getPrevRow(rows, daysBack) {
    if (!rows.length) return null;
    const latest = rows[rows.length - 1];
    const target = new Date(latest.trading_date);
    target.setDate(target.getDate() - daysBack);
    const targetStr = target.toISOString().slice(0, 10);
    for (let i = rows.length - 1; i >= 0; i--) {
        if (rows[i].trading_date <= targetStr) return rows[i];
    }
    return null;
}

function renderChart() {
    const el = document.getElementById('chart-usdc-supply');
    if (!el) return;
    const syms = selectedSymbols();
    const dateSet = new Set();
    syms.forEach(sym => (coinRows[sym] || []).forEach(r => dateSet.add(r.trading_date)));
    const labels = Array.from(dateSet).sort();

    const datasets = syms.map(sym => {
        const map = {};
        (coinRows[sym] || []).forEach(r => { map[r.trading_date] = Number(r.supply_amount || 0); });
        return {
            label: `${sym} 유통량`,
            data: labels.map(d => map[d] ?? null),
            borderColor: COLORS[sym] || '#64748b',
            backgroundColor: `${COLORS[sym] || '#64748b'}22`,
            fill: false,
            tension: 0.2,
            pointRadius: 0,
            spanGaps: true,
        };
    });

    if (usdcChart) usdcChart.destroy();
    usdcChart = new Chart(el.getContext('2d'), {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { display: true } },
            scales: {
                y: { ticks: { callback: (v) => `${(Number(v) / 1_000_000_000).toFixed(1)}B` } },
                x: { ticks: { maxTicksLimit: 10 } },
            },
        },
    });
}

function renderTable() {
    const tbody = document.getElementById('usdc-tbody');
    const mobile = document.getElementById('usdc-mobile-cards');
    if (!tbody) return;

    const syms = selectedSymbols();
    const rows = [];
    syms.forEach(sym => {
        const series = coinRows[sym] || [];
        if (!series.length) return;
        const latest = series[series.length - 1];
        const prev7 = getPrevRow(series, 7);
        const prev30 = getPrevRow(series, 30);
        const ch7 = pct(latest.supply_amount, prev7 ? prev7.supply_amount : null);
        const ch30 = pct(latest.supply_amount, prev30 ? prev30.supply_amount : null);
        rows.push({ sym, latest, ch7, ch30 });
    });

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#6b7280;">데이터가 없습니다</td></tr>';
        if (mobile) mobile.innerHTML = '<div class="mobile-empty">데이터가 없습니다</div>';
        return;
    }

    tbody.innerHTML = rows.map(x => `
        <tr>
            <td style="text-align:left;font-weight:700;color:${COLORS[x.sym] || '#111827'};">${x.sym}</td>
            <td style="text-align:left;">${x.latest.trading_date}</td>
            <td style="text-align:right;">${fmtNum(x.latest.supply_amount, 0)}</td>
            <td style="text-align:right; color:${x.ch7 == null ? '#6b7280' : (x.ch7 >= 0 ? '#16a34a' : '#dc2626')};">${x.ch7 == null ? '-' : `${x.ch7 >= 0 ? '+' : ''}${x.ch7.toFixed(2)}%`}</td>
            <td style="text-align:right; color:${x.ch30 == null ? '#6b7280' : (x.ch30 >= 0 ? '#16a34a' : '#dc2626')};">${x.ch30 == null ? '-' : `${x.ch30 >= 0 ? '+' : ''}${x.ch30.toFixed(2)}%`}</td>
            <td style="text-align:right;">$${fmtNum(x.latest.market_cap_usd, 0)}</td>
            <td style="text-align:right;">$${fmtNum(x.latest.price_usd, 4)}</td>
        </tr>
    `).join('');

    if (mobile) {
        mobile.innerHTML = rows.map(x => `
            <article class="mobile-card">
                <div class="m-head">
                    <div class="m-title" style="color:${COLORS[x.sym] || '#111827'};">${x.sym}</div>
                    <div class="m-sub">${x.latest.trading_date}</div>
                </div>
                <div class="m-grid">
                    <div class="m-k">유통량</div><div class="m-v">${fmtNum(x.latest.supply_amount, 0)}</div>
                    <div class="m-k">7일 변화</div><div class="m-v" style="color:${x.ch7 == null ? '#6b7280' : (x.ch7 >= 0 ? '#16a34a' : '#dc2626')};">${x.ch7 == null ? '-' : `${x.ch7 >= 0 ? '+' : ''}${x.ch7.toFixed(2)}%`}</div>
                    <div class="m-k">30일 변화</div><div class="m-v" style="color:${x.ch30 == null ? '#6b7280' : (x.ch30 >= 0 ? '#16a34a' : '#dc2626')};">${x.ch30 == null ? '-' : `${x.ch30 >= 0 ? '+' : ''}${x.ch30.toFixed(2)}%`}</div>
                    <div class="m-k">시가총액</div><div class="m-v">$${fmtNum(x.latest.market_cap_usd, 0)}</div>
                    <div class="m-k">가격</div><div class="m-v">$${fmtNum(x.latest.price_usd, 4)}</div>
                </div>
            </article>
        `).join('');
    }
}

function renderAll() {
    renderChart();
    renderTable();
}

async function loadStablecoins() {
    const range = Number(document.getElementById('sel-range').value || 365);
    const days = range > 0 ? range : 0;
    const syms = selectedSymbols();
    const out = await fetchJSON(`/api/stablecoin/supply?symbols=${encodeURIComponent(syms.join(','))}&days=${days}`);
    const data = out.data || {};
    coinRows = { USDC: data.USDC || [], USDT: data.USDT || [], FDUSD: data.FDUSD || [] };
    renderAll();
}

async function refreshStablecoins() {
    const btn = document.getElementById('btn-refresh-usdc');
    const msg = document.getElementById('usdc-msg');
    btn.disabled = true;
    btn.textContent = '갱신 중...';
    msg.textContent = '';
    try {
        const syms = selectedSymbols();
        const out = await postJSON(`/api/stablecoin/refresh?symbols=${encodeURIComponent(syms.join(','))}&days=365`);
        await loadStablecoins();
        const total = Object.values(out.items || {}).reduce((acc, x) => acc + Number(x.upserted || 0), 0);
        if (out.status === 'partial') {
            msg.textContent = `부분 업데이트 (${total}건)`;
        } else {
            msg.textContent = `업데이트 완료 (${total}건)`;
        }
    } catch (e) {
        msg.textContent = `실패: ${e.message}`;
        alert(`스테이블코인 데이터 갱신 실패: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '데이터 갱신';
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('btn-refresh-usdc').addEventListener('click', refreshStablecoins);
    document.getElementById('sel-range').addEventListener('change', loadStablecoins);
    document.querySelectorAll('.sym-opt').forEach(el => el.addEventListener('change', loadStablecoins));

    try {
        await loadStablecoins();
    } catch {
        await refreshStablecoins();
    }
});
