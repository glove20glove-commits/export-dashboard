const API = '';
const DEFAULT_DAYS = 365;
const LINE_COLOR = '#2563eb';

let selectedDays = DEFAULT_DAYS;
let depositChart = null;

function toNum(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
}

function fmtSigned(v, digits = 1) {
    const n = toNum(v);
    if (n == null) return '-';
    return `${n > 0 ? '+' : ''}${n.toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    })}`;
}

function fmtPercent(v) {
    const n = toNum(v);
    if (n == null) return '-';
    return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function eokToJo(v) {
    const n = toNum(v);
    if (n == null) return null;
    return n / 10000;
}

function fmtJo(v, digits = 1) {
    const jo = eokToJo(v);
    if (jo == null) return '-';
    return `${jo.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: digits,
    })}조`;
}

function changeColor(diff) {
    const n = toNum(diff);
    if (n == null || n === 0) return '';
    return n > 0 ? 'positive' : 'negative';
}

async function fetchJSON(url) {
    const resp = await fetch(API + url);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `${resp.status} ${resp.statusText}`);
    return data;
}

function setPeriodButtonsActive(days) {
    document.querySelectorAll('.period-btn').forEach(btn => {
        const d = Number(btn.dataset.days || 0);
        btn.classList.toggle('active', d === days);
    });
}

function renderDummyAlert(data) {
    const el = document.getElementById('dummy-alert');
    const isDummy = Boolean(data?.used_fallback) || data?.source === 'dummy';
    el.style.display = isDummy ? '' : 'none';
}

function renderStats(stats = {}) {
    const currentEl = document.getElementById('card-current');
    const currentSubEl = document.getElementById('card-current-sub');
    currentEl.textContent = fmtJo(stats.current, 1);
    currentSubEl.textContent = stats.as_of_date ? `기준일: ${stats.as_of_date}` : '';

    const map = [
        { key: 'change_day', valId: 'card-day', subId: 'card-day-sub', baseDate: stats.base_day_date },
        { key: 'change_1m', valId: 'card-1m', subId: 'card-1m-sub', baseDate: stats.base_1m_date },
        { key: 'change_1y', valId: 'card-1y', subId: 'card-1y-sub', baseDate: stats.base_1y_date },
    ];

    map.forEach(item => {
        const row = stats[item.key];
        const valEl = document.getElementById(item.valId);
        const subEl = document.getElementById(item.subId);

        if (!row) {
            valEl.textContent = '-';
            valEl.className = 'card-value';
            subEl.textContent = '';
            return;
        }

        valEl.textContent = `${fmtSigned(eokToJo(row.diff), 1)}조`;
        valEl.className = `card-value ${changeColor(row.diff)}`.trim();
        subEl.textContent = `${fmtPercent(row.diff_pct)} (${item.baseDate || '-'})`;
        subEl.className = `card-sub ${changeColor(row.diff)}`.trim();
    });
}

function renderChart(series = []) {
    const labels = series.map(r => r.trading_date);
    const data = series.map(r => toNum(r.deposit_fund));
    const canvas = document.getElementById('deposit-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, canvas.height || 280);
    grad.addColorStop(0, 'rgba(37,99,235,0.28)');
    grad.addColorStop(1, 'rgba(37,99,235,0.02)');

    if (depositChart) depositChart.destroy();
    depositChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '예탁금',
                data,
                borderColor: LINE_COLOR,
                backgroundColor: grad,
                fill: true,
                tension: 0.24,
                pointRadius: 0,
                pointHitRadius: 10,
                spanGaps: true,
            }],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctxItem) => {
                            const eok = toNum(ctxItem.raw);
                            if (eok == null) return '예탁금: -';
                            return `예탁금: ${fmtJo(eok, 2)} (${eok.toLocaleString()}억)`;
                        },
                    },
                },
            },
            scales: {
                x: { ticks: { maxTicksLimit: 12 } },
                y: {
                    ticks: {
                        callback: (value) => {
                            const v = toNum(value);
                            if (v == null) return '-';
                            return `${eokToJo(v).toFixed(1)}조`;
                        },
                    },
                },
            },
        },
    });
}

async function loadDepositFund(days = selectedDays) {
    selectedDays = Number(days || DEFAULT_DAYS);
    setPeriodButtonsActive(selectedDays);

    const statusEl = document.getElementById('status-msg');
    statusEl.textContent = '불러오는 중...';

    try {
        const out = await fetchJSON(`/api/deposit-fund?days=${encodeURIComponent(selectedDays)}`);
        renderDummyAlert(out);
        renderStats(out.stats || {});
        renderChart(out.series || []);
        statusEl.textContent = `조회 기간 ${selectedDays}일`;
    } catch (e) {
        statusEl.textContent = `실패: ${e.message}`;
        alert(`예탁금 데이터 조회 실패: ${e.message}`);
    }
}

function bindEvents() {
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const days = Number(btn.dataset.days || DEFAULT_DAYS);
            if (days === selectedDays) return;
            loadDepositFund(days);
        });
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    await loadDepositFund(DEFAULT_DAYS);
});
