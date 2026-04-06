const API = '';
let currentItemId = null;
let monthlyChart = null;
let yearlyChart = null;
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
    const items = await api('GET', '/api/industry/items');
    const sel = document.getElementById('item-select');
    sel.innerHTML = '<option value="">산업을 선택하세요</option>';
    items.forEach(item => {
        const label = item.label || `${item.item_type} ${item.item_code}`;
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
    updateTable(data);
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
                    fill: true,
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

    if (yearlyChart) yearlyChart.destroy();
    yearlyChart = new Chart(document.getElementById('chart-yearly'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: '수출', data: exports, backgroundColor: '#2563eb' },
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

// --- Table ---
function updateTable(data) {
    const tbody = document.querySelector('#data-table tbody');
    const mobile = document.getElementById('industry-mobile-cards');
    tbody.innerHTML = '';
    data.forEach(d => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${d.year}-${d.month}</td>
            <td>${num(d.export_amt)}</td>
            <td class="${d.export_rate < 0 ? 'negative' : ''}">${d.export_rate.toFixed(1)}</td>
        `;
        tbody.appendChild(tr);
    });

    if (mobile) {
        if (!data.length) {
            mobile.innerHTML = '<div class="mobile-empty">월별 데이터가 없습니다.</div>';
        } else {
            mobile.innerHTML = data.map(d => `
                <article class="mobile-card">
                    <div class="m-head"><div class="m-title">${d.year}-${d.month}</div></div>
                    <div class="m-grid">
                        <div class="m-k">수출액(천불)</div><div class="m-v">${num(d.export_amt)}</div>
                        <div class="m-k">수출증감률(%)</div><div class="m-v ${d.export_rate < 0 ? 'negative' : 'positive'}">${Number(d.export_rate || 0).toFixed(1)}</div>
                    </div>
                </article>
            `).join('');
        }
    }
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
    const name = document.getElementById('new-industry-name').value.trim();
    const code = document.getElementById('new-item-code').value.trim();
    if (!name || !code) {
        document.getElementById('modal-status').textContent = '산업명과 품목 코드를 입력해주세요.';
        return;
    }

    const statusEl = document.getElementById('modal-status');
    statusEl.textContent = '산업 추가 중...';

    const itemType = document.getElementById('new-item-type').value;
    const yearFrom = parseInt(document.getElementById('new-year-from').value);
    const now = new Date();

    try {
        const result = await api('POST', '/api/industry/items', {
            item_code: code,
            item_type: itemType,
            label: name,
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
    document.getElementById('table-section').style.display = 'none';
}
