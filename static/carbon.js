const API = '';
const GLOBAL_CARBON_CACHE_KEY = 'carbon-global-cache-v1';
let priceChart = null;
let volumeChart = null;
let globalCarbonChart = null;
let currentData = [];

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('item-select').addEventListener('change', loadData);
    document.getElementById('period-select').addEventListener('change', loadData);
    document.getElementById('btn-refresh').addEventListener('click', loadData);

    await loadData();
});

// --- API ---
async function api(method, path) {
    const resp = await fetch(API + path, { method });
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

async function loadData() {
    const itemName = document.getElementById('item-select').value;
    const days = parseInt(document.getElementById('period-select').value);

    let url = `/api/carbon/prices?item_name=${itemName}`;
    if (days > 0) {
        const end = new Date();
        const begin = new Date();
        begin.setDate(begin.getDate() - days);
        url += `&begin_date=${fmt(begin)}&end_date=${fmt(end)}`;
    }

    try {
        const [data, stockData] = await Promise.all([
            api('GET', url),
            api('GET', `/api/carbon/stock?code=448280&count=500`),
        ]);
        currentData = data;

        // Build stock lookup by date
        const stockMap = {};
        stockData.forEach(s => { stockMap[s.date] = s; });

        showAll();
        updateCards(data);
        updatePriceChart(data, stockMap);
        updateVolumeChart(data, stockMap);
    } catch (e) {
        console.error('Failed to load carbon data:', e);
        return;
    }

    try {
        const globalData = await api('GET', `/api/carbon/global?days=${days > 0 ? days : 365}`);
        const merged = mergeGlobalCarbonPayload(loadCachedGlobalCarbon(), globalData);
        if ((merged.regions || []).some(r => (r.history || []).length > 0)) {
            try {
                localStorage.setItem(GLOBAL_CARBON_CACHE_KEY, JSON.stringify(merged));
            } catch (err) {
                console.warn('Failed to cache global carbon data:', err);
            }
        }
        updateGlobalCarbon(merged);
    } catch (e) {
        console.error('Failed to load global carbon data:', e);
        const cached = loadCachedGlobalCarbon();
        updateGlobalCarbon(cached || { regions: [] });
    }
}

function fmt(d) {
    return d.getFullYear().toString() +
        (d.getMonth() + 1).toString().padStart(2, '0') +
        d.getDate().toString().padStart(2, '0');
}

function fmtDate(s) {
    return s.substring(0, 4) + '-' + s.substring(4, 6) + '-' + s.substring(6, 8);
}

// --- Cards ---
function updateCards(data) {
    if (!data.length) return;

    const latest = data[data.length - 1];
    document.getElementById('card-price').textContent = num(latest.close) + '원';

    const changeEl = document.getElementById('card-change');
    const sign = latest.change > 0 ? '+' : '';
    changeEl.textContent = `${sign}${num(latest.change)}원 (${sign}${latest.change_rate}%)`;
    changeEl.className = 'card-sub ' + (latest.change < 0 ? 'negative' : latest.change > 0 ? 'positive' : '');

    document.getElementById('card-volume').textContent = num(latest.volume) + '톤';
    document.getElementById('card-date').textContent = fmtDate(latest.date);

    // Period high/low
    let highItem = data[0], lowItem = data[0];
    data.forEach(d => {
        if (d.close > highItem.close) highItem = d;
        if (d.close < lowItem.close) lowItem = d;
    });
    document.getElementById('card-high').textContent = num(highItem.close) + '원';
    document.getElementById('card-high-date').textContent = fmtDate(highItem.date);
    document.getElementById('card-low').textContent = num(lowItem.close) + '원';
    document.getElementById('card-low-date').textContent = fmtDate(lowItem.date);
}

// --- Charts ---
function updatePriceChart(data, stockMap) {
    const labels = data.map(d => fmtDate(d.date));
    const prices = data.map(d => d.close);
    const stockPrices = data.map(d => stockMap[d.date] ? stockMap[d.date].close : null);

    if (priceChart) priceChart.destroy();
    priceChart = new Chart(document.getElementById('chart-price'), {
        data: {
            labels,
            datasets: [
                {
                    type: 'line',
                    label: '배출권 종가 (원/톤)',
                    data: prices,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37,99,235,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 1,
                    yAxisID: 'y',
                },
                {
                    type: 'line',
                    label: '에코아이 주가 (원)',
                    data: stockPrices,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245,158,11,0.1)',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 1,
                    borderDash: [4, 2],
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    title: { display: true, text: '배출권 (원/톤)', color: '#2563eb' },
                    ticks: { callback: v => num(v), color: '#2563eb' },
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    title: { display: true, text: '에코아이 (원)', color: '#f59e0b' },
                    ticks: { callback: v => num(v), color: '#f59e0b' },
                    grid: { drawOnChartArea: false },
                },
                x: { ticks: { maxTicksLimit: 12 } },
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            if (ctx.raw == null) return null;
                            if (ctx.dataset.label.includes('배출권')) return `배출권: ${num(ctx.raw)}원/톤`;
                            return `에코아이: ${num(ctx.raw)}원`;
                        },
                    },
                },
            },
        },
    });
}

function updateVolumeChart(data, stockMap) {
    const labels = data.map(d => fmtDate(d.date));
    const volumes = data.map(d => d.volume);
    const stockVolumes = data.map(d => stockMap[d.date] ? stockMap[d.date].volume : null);

    if (volumeChart) volumeChart.destroy();
    volumeChart = new Chart(document.getElementById('chart-volume'), {
        data: {
            labels,
            datasets: [
                {
                    type: 'bar',
                    label: '배출권 거래량 (톤)',
                    data: volumes,
                    backgroundColor: 'rgba(37,99,235,0.4)',
                    borderColor: '#2563eb',
                    borderWidth: 1,
                    yAxisID: 'y',
                },
                {
                    type: 'bar',
                    label: '에코아이 거래량 (주)',
                    data: stockVolumes,
                    backgroundColor: 'rgba(245,158,11,0.4)',
                    borderColor: '#f59e0b',
                    borderWidth: 1,
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    title: { display: true, text: '배출권 (톤)', color: '#2563eb' },
                    ticks: { callback: v => num(v), color: '#2563eb' },
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    title: { display: true, text: '에코아이 (주)', color: '#f59e0b' },
                    ticks: { callback: v => num(v), color: '#f59e0b' },
                    grid: { drawOnChartArea: false },
                },
                x: { ticks: { maxTicksLimit: 12 } },
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            if (ctx.raw == null) return null;
                            if (ctx.dataset.label.includes('배출권')) return `배출권: ${num(ctx.raw)}톤`;
                            return `에코아이: ${num(ctx.raw)}주`;
                        },
                    },
                },
            },
        },
    });
}

// --- Helpers ---
function num(n) {
    return Number(n).toLocaleString('ko-KR');
}

function loadCachedGlobalCarbon() {
    try {
        const raw = localStorage.getItem(GLOBAL_CARBON_CACHE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        console.warn('Failed to read cached global carbon data:', e);
        return null;
    }
}

function mergeGlobalCarbonPayload(cached, incoming) {
    const cachedRegions = new Map(((cached && cached.regions) || []).map(r => [r.region_key, r]));
    const mergedRegions = [];
    const incomingRegions = (incoming && incoming.regions) || [];

    incomingRegions.forEach(region => {
        const hasData = (region.history || []).some(row => row.close_krw != null);
        if (hasData) {
            mergedRegions.push(region);
        } else if (cachedRegions.has(region.region_key)) {
            mergedRegions.push(cachedRegions.get(region.region_key));
        } else {
            mergedRegions.push(region);
        }
        cachedRegions.delete(region.region_key);
    });

    cachedRegions.forEach(region => mergedRegions.push(region));
    return { ...(incoming || {}), regions: mergedRegions };
}

function showAll() {
    document.getElementById('carbon-cards').style.display = '';
    document.getElementById('charts-section').style.display = '';
    document.getElementById('global-carbon-section').style.display = '';
}

function updateGlobalCarbon(payload) {
    const regions = ((payload && payload.regions) || []).filter(r => (r.history || []).some(row => row.close_krw != null));
    const cardsWrap = document.getElementById('global-carbon-cards');
    cardsWrap.innerHTML = '';
    if (globalCarbonChart) {
        globalCarbonChart.destroy();
        globalCarbonChart = null;
    }
    if (!regions.length) {
        document.getElementById('global-carbon-section').style.display = 'none';
        return;
    }
    document.getElementById('global-carbon-section').style.display = '';

    regions.forEach(region => {
        const latest = region.latest || {};
        const sign = (latest.change || 0) > 0 ? '+' : '';
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="card-label">${region.region_name}</div>
            <div class="card-value">${latest.close_krw != null ? num(Math.round(latest.close_krw)) + '원' : '-'}</div>
            <div class="card-sub ${latest.change_rate < 0 ? 'negative' : (latest.change_rate > 0 ? 'positive' : '')}">
                ${latest.change != null ? `${sign}${num(latest.change)} (${sign}${latest.change_rate}%)` : '-'}
            </div>
            <div class="card-sub" style="margin-top:8px; color:#64748b;">
                ${latest.date || '-'} · ${latest.close != null ? `${num(latest.close)} ${region.unit}` : '-'}${region.fx_rate_to_krw ? ` · ${region.fx_code}/KRW ${num(region.fx_rate_to_krw)}` : ''}${region.note ? ` · ${region.note}` : ''}
            </div>
        `;
        cardsWrap.appendChild(card);
    });

    const labels = buildGlobalLabels(regions);
    const datasets = regions.map((region, idx) => {
        const palette = ['#0f766e', '#dc2626', '#2563eb'];
        const color = palette[idx % palette.length];
        const map = new Map((region.history || []).map(row => [row.date, row]));
        const aligned = labels.map(label => map.get(label)?.close_krw ?? null);
        const indexed = indexSeries(aligned);
        return {
            label: `${region.region_name} (원화환산)`,
            data: indexed,
            borderColor: color,
            backgroundColor: color + '22',
            spanGaps: true,
            tension: 0.25,
            pointRadius: 1,
            fill: false,
        };
    });

    if (globalCarbonChart) globalCarbonChart.destroy();
    globalCarbonChart = new Chart(document.getElementById('chart-global-carbon'), {
        type: 'line',
        data: {
            labels: labels.map(fmtIsoDate),
            datasets,
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    title: { display: true, text: '기준일=100' },
                    ticks: {
                        callback: v => `${v}`,
                    },
                },
                x: {
                    ticks: { maxTicksLimit: 10 },
                },
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: ctx => ctx.raw == null ? null : `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}`,
                    },
                },
            },
        },
    });
}

function buildGlobalLabels(regions) {
    const seen = new Set();
    regions.forEach(region => {
        (region.history || []).forEach(row => seen.add(row.date));
    });
    return [...seen].sort();
}

function indexSeries(values) {
    const base = values.find(v => v != null && Number.isFinite(v));
    if (!base) return values.map(() => null);
    return values.map(v => (v == null ? null : (v / base) * 100));
}

function fmtIsoDate(s) {
    return s || '-';
}
