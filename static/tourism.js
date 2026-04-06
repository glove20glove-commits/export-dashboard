const API = '';
let currentCountryId = null;
let monthlyChart = null;
let yearlyChart = null;
let totalMonthlyChart = null;
let totalYearlyChart = null;
let currentData = [];
let sortCol = null;
let sortAsc = true;

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    initYearSelectors();
    await initOverview();

    document.getElementById('btn-add-country').addEventListener('click', openModal);
    document.getElementById('btn-fetch-all').addEventListener('click', fetchAll);
    document.getElementById('btn-back').addEventListener('click', showOverview);
    document.getElementById('btn-fetch-latest').addEventListener('click', fetchLatest);
    document.getElementById('btn-modal-cancel').addEventListener('click', closeModal);
    document.getElementById('btn-modal-save').addEventListener('click', saveNewCountry);
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
async function initOverview() {
    try {
        const countries = await api('GET', '/api/tourism/countries');
        if (countries.length === 0) {
            document.getElementById('overview-loading').textContent = '주요 10개국 등록 중...';
            await api('POST', '/api/tourism/init-top10');
        }
        await loadOverview();
        await loadTotal();
    } catch (e) {
        console.error('initOverview error:', e);
        document.getElementById('overview-loading').textContent = '데이터 로딩 실패: ' + e.message;
    }
}

async function loadOverview() {
    const overview = await api('GET', '/api/tourism/overview');
    document.getElementById('overview-loading').style.display = 'none';
    const wrap = document.getElementById('overview-table-wrap');
    wrap.style.display = '';

    const tbody = document.querySelector('#overview-table tbody');
    tbody.innerHTML = '';

    if (overview.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">등록된 국가가 없습니다.</td></tr>';
        return;
    }

    overview.forEach(c => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', () => openCountryDetail(c.id, c.nat_nm));
        const period = c.year && c.month ? `${c.year}-${c.month}` : '-';
        const rateClass = c.change_rate < 0 ? 'negative' : (c.change_rate > 0 ? 'positive' : '');
        const rateStr = c.total_months > 0
            ? `${c.change_rate >= 0 ? '+' : ''}${c.change_rate.toFixed(1)}`
            : '-';
        tr.innerHTML = `
            <td><strong>${c.nat_nm}</strong> <span style="color:#888;">(${c.nat_cd})</span></td>
            <td>${period}</td>
            <td>${c.visitors ? num(c.visitors) : '-'}</td>
            <td>${c.prev_visitors ? num(c.prev_visitors) : '-'}</td>
            <td class="${rateClass}">${rateStr}</td>
        `;
        tbody.appendChild(tr);
    });
}

// --- Total Visitors ---
async function loadTotal() {
    try {
        const data = await api('GET', '/api/tourism/total?year_from=2020');
        if (!data.length) {
            document.getElementById('total-loading').textContent = '데이터 없음';
            return;
        }
        document.getElementById('total-loading').style.display = 'none';
        document.getElementById('total-content').style.display = '';

        // Summary cards
        const latest = data[data.length - 1];
        document.getElementById('total-card-latest').textContent = num(latest.visitors);
        document.getElementById('total-card-period').textContent = `${latest.year}년 ${parseInt(latest.month)}월`;

        const rate = latest.change_rate;
        const yoyEl = document.getElementById('total-card-yoy');
        yoyEl.textContent = `${rate >= 0 ? '+' : ''}${rate.toFixed(1)}%`;
        yoyEl.className = `card-value ${rate >= 0 ? 'positive' : 'negative'}`;
        document.getElementById('total-card-yoy-prev').textContent = `전년: ${num(latest.prev_visitors)}명`;

        const currentYear = latest.year;
        const ytdData = data.filter(d => d.year === currentYear);
        const ytdTotal = ytdData.reduce((s, d) => s + d.visitors, 0);
        const ytdPrev = ytdData.reduce((s, d) => s + d.prev_visitors, 0);
        document.getElementById('total-card-ytd').textContent = num(ytdTotal);
        const ytdRate = ytdPrev > 0 ? ((ytdTotal - ytdPrev) / ytdPrev * 100) : 0;
        const ytdSub = document.getElementById('total-card-ytd-prev');
        ytdSub.textContent = `전년: ${num(ytdPrev)}명 (${ytdRate >= 0 ? '+' : ''}${ytdRate.toFixed(1)}%)`;
        ytdSub.className = `card-sub ${ytdRate >= 0 ? 'positive' : 'negative'}`;

        // Monthly chart
        const labels = data.map(d => d.year + '-' + d.month);
        const visitors = data.map(d => d.visitors);
        const prevVisitors = data.map(d => d.prev_visitors);

        if (totalMonthlyChart) totalMonthlyChart.destroy();
        totalMonthlyChart = new Chart(document.getElementById('chart-total-monthly'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: '방한인원',
                        data: visitors,
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37,99,235,0.1)',
                        fill: true, tension: 0.3, pointRadius: 2,
                    },
                    {
                        label: '전년 동기',
                        data: prevVisitors,
                        borderColor: '#94a3b8',
                        borderDash: [4, 4],
                        fill: false, tension: 0.3, pointRadius: 0,
                    },
                ],
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

        // Yearly chart
        const byYear = {};
        data.forEach(d => { byYear[d.year] = (byYear[d.year] || 0) + d.visitors; });
        const years = Object.keys(byYear).sort();
        const yearTotals = years.map(y => byYear[y]);

        if (totalYearlyChart) totalYearlyChart.destroy();
        totalYearlyChart = new Chart(document.getElementById('chart-total-yearly'), {
            type: 'bar',
            data: {
                labels: years,
                datasets: [{ label: '방한인원', data: yearTotals, backgroundColor: '#2563eb' }],
            },
            options: {
                responsive: true,
                scales: { y: { ticks: { callback: v => num(v) } } },
                plugins: {
                    tooltip: {
                        callbacks: { label: ctx => `${ctx.dataset.label}: ${num(ctx.raw)}명` },
                    },
                },
            },
        });
    } catch (e) {
        console.error('loadTotal error:', e);
        document.getElementById('total-loading').textContent = '전체 현황 로딩 실패';
    }
}

// --- Country Detail ---
async function openCountryDetail(countryId, countryName) {
    currentCountryId = countryId;
    document.getElementById('overview-section').style.display = 'none';
    document.getElementById('detail-section').style.display = '';
    document.getElementById('detail-title').textContent = `${countryName} 방한 현황`;
    try {
        await loadData();
    } catch (e) {
        console.error('loadData error:', e);
        alert('데이터 로딩 실패: ' + e.message);
    }
}

function showOverview() {
    currentCountryId = null;
    document.getElementById('detail-section').style.display = 'none';
    document.getElementById('overview-section').style.display = '';
    hideDetail();
    loadOverview();
    loadTotal();
}

async function onFilterChange() {
    if (currentCountryId) await loadData();
}

async function loadData() {
    const yearFrom = document.getElementById('year-from').value;
    const yearTo = document.getElementById('year-to').value;
    const data = await api('GET', `/api/tourism/data/${currentCountryId}?year_from=${yearFrom}&year_to=${yearTo}`);
    currentData = data;
    showDetail();
    updateSummary(data);
    updateMonthlyChart(data);
    updateYearlyChart(data);
    updateTable(data);
}

// --- Summary Cards ---
function updateSummary(data) {
    const section = document.getElementById('summary-section');
    if (!data.length) { section.style.display = 'none'; return; }
    section.style.display = '';

    const latest = data[data.length - 1];
    document.getElementById('card-latest').textContent = num(latest.visitors);
    document.getElementById('card-latest-period').textContent = `${latest.year}년 ${parseInt(latest.month)}월`;

    const rate = latest.change_rate;
    const yoyEl = document.getElementById('card-yoy');
    yoyEl.textContent = `${rate >= 0 ? '+' : ''}${rate.toFixed(1)}%`;
    yoyEl.className = `card-value ${rate >= 0 ? 'positive' : 'negative'}`;
    document.getElementById('card-yoy-prev').textContent = `전년: ${num(latest.prev_visitors)}명`;
    document.getElementById('card-yoy-prev').className = 'card-sub';

    const currentYear = latest.year;
    const ytdData = data.filter(d => d.year === currentYear);
    const ytdTotal = ytdData.reduce((s, d) => s + d.visitors, 0);
    const ytdPrev = ytdData.reduce((s, d) => s + d.prev_visitors, 0);
    document.getElementById('card-ytd').textContent = num(ytdTotal);
    const ytdRate = ytdPrev > 0 ? ((ytdTotal - ytdPrev) / ytdPrev * 100) : 0;
    const ytdSub = document.getElementById('card-ytd-prev');
    ytdSub.textContent = `전년: ${num(ytdPrev)}명 (${ytdRate >= 0 ? '+' : ''}${ytdRate.toFixed(1)}%)`;
    ytdSub.className = `card-sub ${ytdRate >= 0 ? 'positive' : 'negative'}`;
}

// --- Charts ---
function updateMonthlyChart(data) {
    const labels = data.map(d => d.year + '-' + d.month);
    const visitors = data.map(d => d.visitors);

    if (monthlyChart) monthlyChart.destroy();
    monthlyChart = new Chart(document.getElementById('chart-monthly'), {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '방한인원',
                data: visitors,
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

function updateYearlyChart(data) {
    const byYear = {};
    data.forEach(d => {
        byYear[d.year] = (byYear[d.year] || 0) + d.visitors;
    });
    const labels = Object.keys(byYear).sort();
    const totals = labels.map(y => byYear[y]);

    if (yearlyChart) yearlyChart.destroy();
    yearlyChart = new Chart(document.getElementById('chart-yearly'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label: '방한인원', data: totals, backgroundColor: '#2563eb' }],
        },
        options: {
            responsive: true,
            scales: { y: { ticks: { callback: v => num(v) } } },
            plugins: {
                tooltip: {
                    callbacks: { label: ctx => `${ctx.dataset.label}: ${num(ctx.raw)}명` },
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
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${d.year}-${d.month}</td>
            <td>${num(d.visitors)}</td>
            <td class="${d.change_rate < 0 ? 'negative' : ''}">${d.change_rate.toFixed(1)}</td>
        `;
        tbody.appendChild(tr);

        if (mobileWrap) {
            const rateColor = d.change_rate < 0 ? '#dc2626' : (d.change_rate > 0 ? '#16a34a' : 'var(--text)');
            const card = document.createElement('div');
            card.className = 'mobile-card';
            card.innerHTML = `
                <div class="m-head">
                    <div class="m-title">${d.year}-${d.month}</div>
                </div>
                <div class="m-grid">
                    <div class="m-k">방한인원</div><div class="m-v">${num(d.visitors)}</div>
                    <div class="m-k">전년비</div><div class="m-v" style="color:${rateColor};">${d.change_rate.toFixed(1)}%</div>
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
    if (sortCol === col) { sortAsc = !sortAsc; }
    else { sortCol = col; sortAsc = true; }

    document.querySelectorAll('#data-table th').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.dataset.sort === col) th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
    });

    currentData.sort((a, b) => {
        let va, vb;
        if (col === 'yearMonth') { va = a.year + a.month; vb = b.year + b.month; }
        else { va = a[col]; vb = b[col]; }
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
    });
    updateTable(currentData);
}

// --- Modal ---
let countryListLoaded = false;

function openModal() {
    document.getElementById('modal-overlay').style.display = 'flex';
    document.getElementById('modal-status').textContent = '';
    if (!countryListLoaded) loadCountryList();
}

function closeModal() {
    document.getElementById('modal-overlay').style.display = 'none';
}

async function loadCountryList() {
    try {
        const list = await api('GET', '/api/tourism/country-list');
        const sel = document.getElementById('new-country-select');
        sel.innerHTML = '<option value="">국가를 선택하세요</option>';
        list.forEach(c => {
            sel.add(new Option(`${c.nat_nm} (${c.nat_cd})`, JSON.stringify(c)));
        });
        countryListLoaded = true;
    } catch (e) {
        document.getElementById('modal-status').textContent = '국가 목록 불러오기 실패';
    }
}

async function saveNewCountry() {
    const raw = document.getElementById('new-country-select').value;
    if (!raw) {
        document.getElementById('modal-status').textContent = '국가를 선택해주세요.';
        return;
    }

    const country = JSON.parse(raw);
    const statusEl = document.getElementById('modal-status');
    const yearFrom = parseInt(document.getElementById('new-year-from').value);
    const now = new Date();

    statusEl.textContent = '국가 추가 중...';

    try {
        const result = await api('POST', '/api/tourism/countries', {
            nat_cd: country.nat_cd,
            nat_nm: country.nat_nm,
            tar_cd: country.tar_cd,
        });

        statusEl.textContent = '관광 데이터랩에서 데이터를 가져오는 중...';
        try {
            await api('POST', `/api/tourism/fetch/${result.id}`, {
                year_from: yearFrom,
                month_from: 1,
                year_to: now.getFullYear(),
                month_to: now.getMonth() + 1,
            });
        } catch (e) {
            console.warn('데이터 수집 실패:', e);
        }

        closeModal();
        await loadOverview();
    } catch (e) {
        statusEl.textContent = '오류: ' + e.message;
    }
}

async function fetchAll() {
    const btn = document.getElementById('btn-fetch-all');
    btn.textContent = '가져오는 중...';
    btn.disabled = true;
    try {
        const now = new Date();
        await api('POST', '/api/tourism/fetch-all', {
            year_from: now.getFullYear(),
            month_from: 1,
            year_to: now.getFullYear(),
            month_to: now.getMonth() + 1,
        });
        await loadOverview();
        await loadTotal();
    } catch (e) {
        alert('오류: ' + e.message);
    } finally {
        btn.textContent = '전체 데이터 가져오기';
        btn.disabled = false;
    }
}

async function fetchLatest() {
    if (!currentCountryId) return;
    const btn = document.getElementById('btn-fetch-latest');
    btn.textContent = '가져오는 중...';
    btn.disabled = true;
    try {
        const now = new Date();
        await api('POST', `/api/tourism/fetch/${currentCountryId}`, {
            year_from: now.getFullYear(),
            month_from: 1,
            year_to: now.getFullYear(),
            month_to: now.getMonth() + 1,
        });
        await loadData();
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
