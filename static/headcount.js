const API = '';
let currentCompanyId = null;
let currentCompanyName = '';
let subscribersChart = null;
let hiresLossesChart = null;
let currentData = [];
let sortCol = null;
let sortAsc = true;

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    initYearSelectors();
    await loadOverview();

    document.getElementById('btn-add-company').addEventListener('click', openModal);
    document.getElementById('btn-fetch-all').addEventListener('click', fetchAll);
    document.getElementById('btn-back').addEventListener('click', showOverview);
    document.getElementById('btn-fetch-latest').addEventListener('click', fetchLatest);
    document.getElementById('btn-delete-company').addEventListener('click', deleteCompany);
    document.getElementById('btn-modal-cancel').addEventListener('click', closeModal);
    document.getElementById('btn-modal-save').addEventListener('click', saveNewCompany);
    document.getElementById('btn-search').addEventListener('click', searchCompany);
    document.getElementById('search-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') searchCompany();
    });
    document.getElementById('year-from').addEventListener('change', onFilterChange);
    document.getElementById('year-to').addEventListener('change', onFilterChange);

    document.querySelectorAll('#data-table th').forEach(th => {
        th.addEventListener('click', () => sortTable(th.dataset.sort));
    });
});

function initYearSelectors() {
    const now = new Date().getFullYear();
    const fromSel = document.getElementById('year-from');
    const toSel = document.getElementById('year-to');
    for (let y = 2015; y <= now; y++) {
        fromSel.add(new Option(y, y));
        toSel.add(new Option(y, y));
    }
    fromSel.value = '2020';
    toSel.value = String(now);
}

// --- API ---
async function api(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(API + path, opts);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

// --- Overview ---
async function loadOverview() {
    try {
        const overview = await api('GET', '/api/nps/overview');
        document.getElementById('overview-loading').style.display = 'none';
        const wrap = document.getElementById('overview-table-wrap');
        wrap.style.display = '';

        const tbody = document.querySelector('#overview-table tbody');
        tbody.innerHTML = '';

        if (overview.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">등록된 사업장이 없습니다. "사업장 추가" 버튼으로 추가해주세요.</td></tr>';
            return;
        }

        overview.forEach(c => {
            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.addEventListener('click', () => openDetail(c.id, c.name));
            const period = c.year && c.month ? `${c.year}-${c.month}` : '-';
            const momClass = c.mom_change < 0 ? 'negative' : (c.mom_change > 0 ? 'positive' : '');
            const momStr = c.total_months > 1
                ? `${c.mom_change >= 0 ? '+' : ''}${num(c.mom_change)}`
                : '-';
            const yoyClass = c.yoy_change < 0 ? 'negative' : (c.yoy_change > 0 ? 'positive' : '');
            const yoyStr = c.yoy_change !== 0
                ? `${c.yoy_change >= 0 ? '+' : ''}${num(c.yoy_change)}`
                : '-';
            tr.innerHTML = `
                <td style="text-align:left;"><strong>${c.name}</strong></td>
                <td>${period}</td>
                <td>${c.subscribers ? num(c.subscribers) : '-'}</td>
                <td class="${momClass}">${momStr}</td>
                <td class="${yoyClass}">${yoyStr}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('loadOverview error:', e);
        document.getElementById('overview-loading').textContent = '데이터 로딩 실패: ' + e.message;
    }
}

// --- Detail ---
async function openDetail(companyId, companyName) {
    currentCompanyId = companyId;
    currentCompanyName = companyName;
    document.getElementById('overview-section').style.display = 'none';
    document.getElementById('detail-section').style.display = '';
    document.getElementById('detail-title').textContent = `${companyName} 인원 현황`;
    try {
        await loadData();
    } catch (e) {
        console.error('loadData error:', e);
        alert('데이터 로딩 실패: ' + e.message);
    }
}

function showOverview() {
    currentCompanyId = null;
    document.getElementById('detail-section').style.display = 'none';
    document.getElementById('overview-section').style.display = '';
    hideDetail();
    loadOverview();
}

async function onFilterChange() {
    if (currentCompanyId) await loadData();
}

async function loadData() {
    const yearFrom = document.getElementById('year-from').value;
    const yearTo = document.getElementById('year-to').value;
    const data = await api('GET', `/api/nps/data/${currentCompanyId}?year_from=${yearFrom}&year_to=${yearTo}`);
    currentData = data;
    showDetail();
    updateSummary(data);
    updateSubscribersChart(data);
    updateHiresLossesChart(data);
    updateTable(data);
}

// --- Summary Cards ---
function updateSummary(data) {
    const section = document.getElementById('summary-section');
    if (!data.length) { section.style.display = 'none'; return; }
    section.style.display = '';

    const latest = data[data.length - 1];
    document.getElementById('card-current').textContent = num(latest.subscribers);
    document.getElementById('card-current-period').textContent = `${latest.year}년 ${parseInt(latest.month)}월`;

    // Month-over-month
    const prev = data.length >= 2 ? data[data.length - 2] : null;
    const momEl = document.getElementById('card-mom');
    if (prev) {
        const diff = latest.subscribers - prev.subscribers;
        momEl.textContent = `${diff >= 0 ? '+' : ''}${num(diff)}명`;
        momEl.className = `card-value ${diff >= 0 ? 'positive' : 'negative'}`;
        document.getElementById('card-mom-detail').textContent =
            `입사 ${num(latest.new_hires)} / 퇴사 ${num(latest.losses)}`;
    } else {
        momEl.textContent = '-';
        momEl.className = 'card-value';
        document.getElementById('card-mom-detail').textContent = '';
    }

    // Year-over-year
    const yoyRow = data.find(d =>
        d.year === String(parseInt(latest.year) - 1) && d.month === latest.month
    );
    const yoyEl = document.getElementById('card-yoy');
    if (yoyRow) {
        const diff = latest.subscribers - yoyRow.subscribers;
        const rate = yoyRow.subscribers > 0
            ? ((diff / yoyRow.subscribers) * 100).toFixed(1)
            : '0.0';
        yoyEl.textContent = `${diff >= 0 ? '+' : ''}${num(diff)}명`;
        yoyEl.className = `card-value ${diff >= 0 ? 'positive' : 'negative'}`;
        document.getElementById('card-yoy-detail').textContent =
            `전년: ${num(yoyRow.subscribers)}명 (${rate >= 0 ? '+' : ''}${rate}%)`;
    } else {
        yoyEl.textContent = '-';
        yoyEl.className = 'card-value';
        document.getElementById('card-yoy-detail').textContent = '';
    }
}

// --- Charts ---
function updateSubscribersChart(data) {
    const labels = data.map(d => d.year + '-' + d.month);
    const subscribers = data.map(d => d.subscribers);

    if (subscribersChart) subscribersChart.destroy();
    subscribersChart = new Chart(document.getElementById('chart-subscribers'), {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '가입자수',
                data: subscribers,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37,99,235,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
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
                    callbacks: { label: ctx => `${ctx.dataset.label}: ${num(ctx.raw)}명` },
                },
            },
        },
    });
}

function updateHiresLossesChart(data) {
    const labels = data.map(d => d.year + '-' + d.month);
    const hires = data.map(d => d.new_hires);
    const losses = data.map(d => -d.losses); // negative for visual
    const net = data.map(d => d.new_hires - d.losses);

    if (hiresLossesChart) hiresLossesChart.destroy();
    hiresLossesChart = new Chart(document.getElementById('chart-hires-losses'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: '입사',
                    data: hires,
                    backgroundColor: 'rgba(16,185,129,0.7)',
                },
                {
                    label: '퇴사',
                    data: losses,
                    backgroundColor: 'rgba(239,68,68,0.7)',
                },
                {
                    label: '순증감',
                    data: net,
                    type: 'line',
                    borderColor: '#2563eb',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    stacked: true,
                    ticks: {
                        maxTicksLimit: 15,
                        callback: function(val) {
                            const label = this.getLabelForValue(val);
                            return label.endsWith('-01') ? label.substring(0, 4) : '';
                        },
                    },
                },
                y: {
                    stacked: true,
                    ticks: { callback: v => num(v) },
                },
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const val = ctx.dataset.label === '퇴사' ? -ctx.raw : ctx.raw;
                            return `${ctx.dataset.label}: ${num(Math.abs(val))}명`;
                        },
                    },
                },
            },
        },
    });
}

// --- Table ---
function updateTable(data) {
    const tbody = document.querySelector('#data-table tbody');
    const mobileWrap = document.getElementById('detail-mobile-cards');
    tbody.innerHTML = '';
    if (mobileWrap) mobileWrap.innerHTML = '';
    data.forEach(d => {
        const net = d.new_hires - d.losses;
        const netClass = net < 0 ? 'negative' : (net > 0 ? 'positive' : '');
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${d.year}-${d.month}</td>
            <td>${num(d.subscribers)}</td>
            <td>${num(d.new_hires)}</td>
            <td>${num(d.losses)}</td>
            <td class="${netClass}">${net >= 0 ? '+' : ''}${num(net)}</td>
        `;
        tbody.appendChild(tr);

        if (mobileWrap) {
            const card = document.createElement('div');
            card.className = 'mobile-card';
            card.innerHTML = `
                <div class="m-head">
                    <div class="m-title">${d.year}-${d.month}</div>
                </div>
                <div class="m-grid">
                    <div class="m-k">가입자수</div><div class="m-v">${num(d.subscribers)}</div>
                    <div class="m-k">입사</div><div class="m-v">${num(d.new_hires)}</div>
                    <div class="m-k">퇴사</div><div class="m-v">${num(d.losses)}</div>
                    <div class="m-k">순증감</div><div class="m-v ${netClass}">${net >= 0 ? '+' : ''}${num(net)}</div>
                </div>
            `;
            mobileWrap.appendChild(card);
        }
    });

    if (mobileWrap && data.length === 0) {
        mobileWrap.innerHTML = '<div class="mobile-empty">표시할 데이터가 없습니다.</div>';
    }
}

function sortTable(col) {
    if (!col) return;
    if (sortCol === col) { sortAsc = !sortAsc; }
    else { sortCol = col; sortAsc = true; }

    document.querySelectorAll('#data-table th').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.dataset.sort === col) th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
    });

    currentData.sort((a, b) => {
        let va, vb;
        if (col === 'yearMonth') { va = a.year + a.month; vb = b.year + b.month; }
        else if (col === 'net') { va = a.new_hires - a.losses; vb = b.new_hires - b.losses; }
        else { va = a[col]; vb = b[col]; }
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
    document.getElementById('search-input').value = '';
    document.getElementById('search-results-group').style.display = 'none';
    document.getElementById('search-input').focus();
}

function closeModal() {
    document.getElementById('modal-overlay').style.display = 'none';
}

async function searchCompany() {
    const name = document.getElementById('search-input').value.trim();
    if (!name) return;

    const statusEl = document.getElementById('modal-status');
    statusEl.textContent = '검색 중...';

    try {
        const results = await api('GET', `/api/nps/search?name=${encodeURIComponent(name)}`);
        const sel = document.getElementById('search-results');
        sel.innerHTML = '';

        if (results.length === 0) {
            statusEl.textContent = '검색 결과가 없습니다.';
            document.getElementById('search-results-group').style.display = 'none';
            return;
        }

        results.forEach(r => {
            const opt = new Option(
                `${r.name} (${r.biz_no || '-'}) [${r.type || ''}]`,
                JSON.stringify(r),
            );
            sel.add(opt);
        });

        document.getElementById('search-results-group').style.display = '';
        statusEl.textContent = `${results.length}건 검색됨`;
    } catch (e) {
        statusEl.textContent = '검색 실패: ' + e.message;
    }
}

async function saveNewCompany() {
    const sel = document.getElementById('search-results');
    if (!sel.value) {
        document.getElementById('modal-status').textContent = '사업장을 선택해주세요.';
        return;
    }

    const company = JSON.parse(sel.value);
    const statusEl = document.getElementById('modal-status');
    statusEl.textContent = '사업장 등록 중...';

    try {
        const result = await api('POST', '/api/nps/companies', {
            seq: company.seq,
            name: company.name,
            biz_no: company.biz_no,
        });

        statusEl.textContent = '국민연금 데이터 가져오는 중... (시간이 걸릴 수 있습니다)';
        try {
            await api('POST', `/api/nps/fetch/${result.id}`);
        } catch (e) {
            console.warn('데이터 수집 실패:', e);
        }

        closeModal();
        await loadOverview();
    } catch (e) {
        statusEl.textContent = '오류: ' + e.message;
    }
}

// --- Actions ---
async function fetchAll() {
    const btn = document.getElementById('btn-fetch-all');
    btn.textContent = '가져오는 중...';
    btn.disabled = true;
    try {
        await api('POST', '/api/nps/fetch-all');
        await loadOverview();
    } catch (e) {
        alert('오류: ' + e.message);
    } finally {
        btn.textContent = '전체 데이터 가져오기';
        btn.disabled = false;
    }
}

async function fetchLatest() {
    if (!currentCompanyId) return;
    const btn = document.getElementById('btn-fetch-latest');
    btn.textContent = '가져오는 중...';
    btn.disabled = true;
    try {
        await api('POST', `/api/nps/fetch/${currentCompanyId}`);
        await loadData();
    } catch (e) {
        alert('오류: ' + e.message);
    } finally {
        btn.textContent = '데이터 갱신';
        btn.disabled = false;
    }
}

async function deleteCompany() {
    if (!currentCompanyId) return;
    if (!confirm(`"${currentCompanyName}" 사업장을 삭제하시겠습니까? 모든 데이터가 삭제됩니다.`)) return;
    try {
        await api('DELETE', `/api/nps/companies/${currentCompanyId}`);
        showOverview();
    } catch (e) {
        alert('삭제 실패: ' + e.message);
    }
}

// --- Helpers ---
function num(n) {
    return Number(n).toLocaleString('ko-KR');
}

function showDetail() {
    document.getElementById('summary-section').style.display = '';
    document.getElementById('charts-section').style.display = '';
    document.getElementById('table-section').style.display = '';
}

function hideDetail() {
    document.getElementById('summary-section').style.display = 'none';
    document.getElementById('charts-section').style.display = 'none';
    document.getElementById('table-section').style.display = 'none';
}
