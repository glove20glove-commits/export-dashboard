const API = '';
let currentItemId = null;
let monthlyChart = null;
let yearlyChart = null;
let balanceChart = null;
let comparisonChart = null;
let currentData = [];
let sortCol = null;
let sortAsc = true;

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    initYearSelectors();
    await loadItems();

    document.getElementById('item-select').addEventListener('change', onItemChange);
    document.getElementById('year-from').addEventListener('change', onFilterChange);
    document.getElementById('year-to').addEventListener('change', onFilterChange);
    document.getElementById('btn-add-item').addEventListener('click', openModal);
    document.getElementById('btn-fetch-latest').addEventListener('click', fetchLatest);
    document.getElementById('btn-modal-cancel').addEventListener('click', closeModal);
    document.getElementById('btn-modal-save').addEventListener('click', saveNewItem);

    document.querySelectorAll('#data-table th').forEach(th => {
        th.addEventListener('click', () => sortTable(th.dataset.sort));
    });
});

function initYearSelectors() {
    const now = new Date().getFullYear();
    const fromSel = document.getElementById('year-from');
    const toSel = document.getElementById('year-to');
    for (let y = 2000; y <= now; y++) {
        fromSel.add(new Option(y, y));
        toSel.add(new Option(y, y));
    }
    fromSel.value = '2020';
    toSel.value = String(now);
}

// --- API Calls ---
async function api(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(API + path, opts);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

async function loadItems() {
    const items = await api('GET', '/api/items');
    const sel = document.getElementById('item-select');
    sel.innerHTML = '<option value="">기업을 선택하세요</option>';
    items.forEach(item => {
        const label = item.stock_name
            ? `${item.stock_name} (${item.region_name} / ${item.item_code})`
            : (item.label || `${item.region_name} ${item.item_type} ${item.item_code}`);
        sel.add(new Option(label, item.id));
    });
    if (items.length === 1) {
        sel.value = items[0].id;
        onItemChange();
    }
}

async function onItemChange() {
    const id = document.getElementById('item-select').value;
    if (!id) {
        hideAll();
        return;
    }
    currentItemId = parseInt(id);
    await loadData();
}

async function onFilterChange() {
    if (currentItemId) await loadData();
}

async function loadData() {
    const yearFrom = document.getElementById('year-from').value;
    const yearTo = document.getElementById('year-to').value;
    const data = await api('GET', `/api/data/${currentItemId}?year_from=${yearFrom}-01&year_to=${yearTo}-12`);
    const summary = await api('GET', `/api/summary/${currentItemId}`);
    currentData = data;
    showAll();
    updateMonthlyChart(data);
    updateYearlyChart(summary);
    updateBalanceChart(data);
    updateTable(data);
    await loadStockComparison(data);
}

// --- Charts ---
function updateMonthlyChart(data) {
    const labels = data.map(d => d.year + '-' + d.month);
    const exports = data.map(d => d.export_amt);

    if (monthlyChart) monthlyChart.destroy();
    monthlyChart = new Chart(document.getElementById('chart-monthly'), {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: '수출액',
                    data: exports,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37,99,235,0.1)',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 2,
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    ticks: { callback: v => num(v) },
                },
                x: {
                    ticks: {
                        maxTicksLimit: 15,
                        callback: function(val, idx) {
                            const label = this.getLabelForValue(val);
                            return label.endsWith('-01') ? label.substring(0, 4) : '';
                        },
                    },
                },
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${num(ctx.raw)} 천불`,
                    },
                },
            },
        },
    });
}

function updateYearlyChart(summary) {
    const labels = summary.map(s => s.year);
    const exports = summary.map(s => s.total_export);
    const imports = summary.map(s => s.total_import);

    if (yearlyChart) yearlyChart.destroy();
    yearlyChart = new Chart(document.getElementById('chart-yearly'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: '수출', data: exports, backgroundColor: '#2563eb' },
                { label: '수입', data: imports, backgroundColor: '#ef4444' },
            ],
        },
        options: {
            responsive: true,
            scales: {
                y: { ticks: { callback: v => num(v) } },
            },
            plugins: {
                tooltip: {
                    callbacks: { label: ctx => `${ctx.dataset.label}: ${num(ctx.raw)} 천불` },
                },
            },
        },
    });
}

function updateBalanceChart(data) {
    const labels = data.map(d => d.year + '-' + d.month);
    const balances = data.map(d => d.balance);

    if (balanceChart) balanceChart.destroy();
    balanceChart = new Chart(document.getElementById('chart-balance'), {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '무역수지',
                data: balances,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16,185,129,0.15)',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }],
        },
        options: {
            responsive: true,
            scales: {
                y: { ticks: { callback: v => num(v) } },
                x: {
                    ticks: {
                        maxTicksLimit: 15,
                        callback: function(val) {
                            const label = this.getLabelForValue(val);
                            return label.endsWith('-01') ? label.substring(0, 4) : '';
                        },
                    },
                },
            },
            plugins: {
                tooltip: {
                    callbacks: { label: ctx => `수지: ${num(ctx.raw)} 천불` },
                },
            },
        },
    });
}

// --- Stock Comparison Chart ---
async function loadStockComparison(tradeData) {
    const stockSection = document.getElementById('stock-section');
    try {
        const yearFrom = document.getElementById('year-from').value;
        const yearTo = document.getElementById('year-to').value;
        const [stockData, stockInfo, revenueData] = await Promise.all([
            api('GET', `/api/stock/${currentItemId}?year_from=${yearFrom}-01&year_to=${yearTo}-12`),
            api('GET', `/api/stock-info/${currentItemId}`),
            api('GET', `/api/revenue/${currentItemId}?year_from=${yearFrom}&year_to=${yearTo}`),
        ]);

        if (!stockData || stockData.length === 0) {
            stockSection.style.display = 'none';
            return;
        }

        stockSection.style.display = '';
        const title = stockInfo.stock_name
            ? `수출액 vs ${stockInfo.stock_name}(${stockInfo.stock_code}) 주가·매출 비교`
            : '수출액 vs 주가·매출 비교';
        document.getElementById('stock-chart-title').textContent = title;

        // Build aligned datasets by yearMonth key
        const tradeMap = {};
        tradeData.forEach(d => { tradeMap[d.year + '-' + d.month] = d.export_amt; });
        const stockMap = {};
        stockData.forEach(d => { stockMap[d.year + '-' + d.month] = d.close_price; });

        // Map quarterly revenue to last month of quarter
        const quarterEndMonth = { Q1: '03', Q2: '06', Q3: '09', Q4: '12' };
        const revenueMap = {};
        revenueData.forEach(d => {
            const key = d.year + '-' + quarterEndMonth[d.quarter];
            revenueMap[key] = d.revenue;
        });

        // Union of all months, sorted
        const allMonths = [...new Set([...Object.keys(tradeMap), ...Object.keys(stockMap)])].sort();
        const labels = allMonths;
        const exports = allMonths.map(m => tradeMap[m] ?? null);
        const prices = allMonths.map(m => stockMap[m] ?? null);
        const revenues = allMonths.map(m => revenueMap[m] ?? null);

        if (comparisonChart) comparisonChart.destroy();
        comparisonChart = new Chart(document.getElementById('chart-comparison'), {
            data: {
                labels,
                datasets: [
                    {
                        type: 'bar',
                        label: '분기 매출 (억원)',
                        data: revenues,
                        backgroundColor: 'rgba(139,92,246,0.35)',
                        borderColor: '#8b5cf6',
                        borderWidth: 1,
                        yAxisID: 'y2',
                        barPercentage: 0.6,
                        order: 3,
                    },
                    {
                        type: 'line',
                        label: '수출액 (천불)',
                        data: exports,
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37,99,235,0.1)',
                        fill: false,
                        tension: 0.3,
                        pointRadius: 2,
                        yAxisID: 'y',
                        order: 1,
                    },
                    {
                        type: 'line',
                        label: '주가 (원)',
                        data: prices,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245,158,11,0.1)',
                        fill: false,
                        tension: 0.3,
                        pointRadius: 2,
                        yAxisID: 'y1',
                        order: 2,
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
                        title: { display: true, text: '수출액 (천불)', color: '#2563eb' },
                        ticks: { callback: v => num(v), color: '#2563eb' },
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        title: { display: true, text: '주가 (원)', color: '#f59e0b' },
                        ticks: { callback: v => num(v), color: '#f59e0b' },
                        grid: { drawOnChartArea: false },
                    },
                    y2: {
                        type: 'linear',
                        position: 'right',
                        title: { display: true, text: '매출 (억원)', color: '#8b5cf6' },
                        ticks: { callback: v => num(v), color: '#8b5cf6' },
                        grid: { drawOnChartArea: false },
                        offset: true,
                    },
                    x: {
                        ticks: {
                            maxTicksLimit: 15,
                            callback: function(val) {
                                const label = this.getLabelForValue(val);
                                return label.endsWith('-01') ? label.substring(0, 4) : '';
                            },
                        },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                if (ctx.raw == null) return null;
                                if (ctx.dataset.label.includes('수출')) return `수출액: ${num(ctx.raw)} 천불`;
                                if (ctx.dataset.label.includes('주가')) return `주가: ${num(ctx.raw)} 원`;
                                return `매출: ${ctx.raw.toFixed(1)}억원`;
                            },
                        },
                    },
                },
            },
        });
    } catch (e) {
        stockSection.style.display = 'none';
    }
}

// --- Table ---
function updateTable(data) {
    const tbody = document.querySelector('#data-table tbody');
    tbody.innerHTML = '';
    data.forEach(d => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${d.year}-${d.month}</td>
            <td>${num(d.export_amt)}</td>
            <td class="${d.export_rate < 0 ? 'negative' : ''}">${d.export_rate.toFixed(1)}</td>
            <td>${num(d.import_amt)}</td>
            <td class="${d.import_rate < 0 ? 'negative' : ''}">${d.import_rate.toFixed(1)}</td>
            <td>${num(d.balance)}</td>
        `;
        tbody.appendChild(tr);
    });
}

function sortTable(col) {
    if (sortCol === col) {
        sortAsc = !sortAsc;
    } else {
        sortCol = col;
        sortAsc = true;
    }

    document.querySelectorAll('#data-table th').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.dataset.sort === col) {
            th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
        }
    });

    currentData.sort((a, b) => {
        let va, vb;
        if (col === 'yearMonth') {
            va = a.year + a.month;
            vb = b.year + b.month;
        } else {
            va = a[col];
            vb = b[col];
        }
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
    });

    updateTable(currentData);
}

// --- Modal ---
function openModal() {
    document.getElementById('modal-overlay').style.display = 'flex';
    document.getElementById('modal-status').textContent = '';
}

function closeModal() {
    document.getElementById('modal-overlay').style.display = 'none';
}

async function saveNewItem() {
    const stockName = document.getElementById('new-stock-name').value.trim();
    const stockCode = document.getElementById('new-stock-code').value.trim();
    const code = document.getElementById('new-item-code').value.trim();
    const regionName = document.getElementById('new-region-name').value.trim();
    if (!stockName || !code || !regionName) {
        document.getElementById('modal-status').textContent = '기업명, 품목 코드, 지역명을 입력해주세요.';
        return;
    }

    const statusEl = document.getElementById('modal-status');
    statusEl.textContent = '기업 추가 중...';

    const itemType = document.getElementById('new-item-type').value;
    const regionType = document.getElementById('new-region-type').value;
    const yearFrom = parseInt(document.getElementById('new-year-from').value);
    const now = new Date();

    try {
        const result = await api('POST', '/api/items', {
            item_code: code,
            item_type: itemType,
            region_type: regionType,
            region_name: regionName,
            stock_code: stockCode || null,
            stock_name: stockName,
        });

        statusEl.textContent = 'KITA에서 수출입 데이터를 가져오는 중...';
        try {
            await api('POST', `/api/fetch/${result.id}`, {
                year_from: yearFrom,
                month_from: 1,
                year_to: now.getFullYear(),
                month_to: now.getMonth() + 1,
            });
        } catch (e) {
            console.warn('KITA 수집 실패:', e);
        }

        if (stockCode) {
            statusEl.textContent = '네이버에서 주가 데이터를 가져오는 중...';
            try {
                await api('POST', `/api/fetch-stock/${result.id}`);
            } catch (e) {
                console.warn('주가 수집 실패:', e);
            }
        }

        closeModal();
        await loadItems();
        document.getElementById('item-select').value = result.id;
        currentItemId = result.id;
        await loadData();
    } catch (e) {
        statusEl.textContent = '오류: ' + e.message;
    }
}

async function fetchLatest() {
    const btn = document.getElementById('btn-fetch-latest');
    btn.textContent = '가져오는 중...';
    btn.disabled = true;
    try {
        await api('POST', '/api/fetch-latest');
        if (currentItemId) await loadData();
    } catch (e) {
        alert('오류: ' + e.message);
    } finally {
        btn.textContent = '최신 데이터 가져오기';
        btn.disabled = false;
    }
}

// --- Helpers ---
function num(n) {
    return Number(n).toLocaleString('ko-KR');
}

function showAll() {
    document.getElementById('charts-section').style.display = '';
    document.getElementById('table-section').style.display = '';
}

function hideAll() {
    document.getElementById('charts-section').style.display = 'none';
    document.getElementById('stock-section').style.display = 'none';
    document.getElementById('table-section').style.display = 'none';
}
