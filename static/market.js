/* market.js - domestic daily briefing + long-term correlation */

const API = '';
let chart = null;
let currentTab = 'daily';

let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;
let monthData = [];
let calendarIndex = 'kospi';

function num(v) { return v == null ? '-' : Number(v).toLocaleString(); }
function pct(v) { return v == null ? '-' : `${Number(v).toFixed(1)}%`; }
function ymKey(r) { return `${r.year}-${String(r.month).padStart(2, '0')}`; }

async function fetchJSON(url) {
    const resp = await fetch(API + url);
    if (!resp.ok) {
        let detail = '';
        try {
            const d = await resp.json();
            detail = d.detail || JSON.stringify(d);
        } catch {}
        throw new Error(detail || `${resp.status} ${resp.statusText}`);
    }
    return resp.json();
}

async function postJSON(url, body) {
    const opts = { method: 'POST', headers: {} };
    if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const resp = await fetch(API + url, opts);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
        throw new Error(data.detail || `${resp.status} ${resp.statusText}`);
    }
    return data;
}

function switchTab(tab) {
    currentTab = tab;
    const isDaily = tab === 'daily';
    document.getElementById('tab-btn-daily').classList.toggle('active', isDaily);
    document.getElementById('tab-btn-longterm').classList.toggle('active', !isDaily);
    document.getElementById('tab-daily').classList.toggle('active', isDaily);
    document.getElementById('tab-longterm').classList.toggle('active', !isDaily);
}

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
    fromSel.onchange = toSel.onchange = loadLongTerm;
}

function updateDailyMonthLabel() {
    const label = document.getElementById('daily-month-label');
    if (label) label.textContent = `${currentYear}년 ${currentMonth}월`;
}

function changeDailyMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 12) { currentMonth = 1; currentYear += 1; }
    if (currentMonth < 1) { currentMonth = 12; currentYear -= 1; }
    loadDailyMonth();
}

async function loadDailyMonth() {
    updateDailyMonthLabel();
    const msg = document.getElementById('daily-msg');
    if (msg) msg.textContent = '불러오는 중...';
    try {
        monthData = await fetchJSON(`/api/market/daily?year=${currentYear}&month=${currentMonth}`);
        renderDailyAll();
        if (msg) msg.textContent = '';
    } catch (e) {
        monthData = [];
        renderDailyAll();
        if (msg) msg.textContent = `조회 실패: ${e.message}`;
    }
}

function renderDailyAll() {
    renderDailyCards();
    renderDailySummaryAndFactors();
    renderDailyCalendar();
}

function renderDailyCards() {
    const wrap = document.getElementById('daily-index-cards');
    if (!wrap) return;

    if (!monthData.length) {
        wrap.innerHTML = '<div class="no-data"><p>선택한 월에 데이터가 없습니다.</p><p>새로고침 버튼으로 데이터를 채워주세요.</p></div>';
        return;
    }

    const latest = monthData[monthData.length - 1];
    const kCh = Number(latest.kospi_change_pct || 0);
    const qCh = Number(latest.kosdaq_change_pct || 0);
    const kCls = kCh >= 0 ? 'up' : 'down';
    const qCls = qCh >= 0 ? 'up' : 'down';
    const kArrow = kCh >= 0 ? '▲' : '▼';
    const qArrow = qCh >= 0 ? '▲' : '▼';

    wrap.innerHTML = `
        <div class="index-card">
            <div class="label">KOSPI</div>
            <div>
                <span class="value">${Number(latest.kospi_close || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                <span class="change ${kCls}">${kArrow} ${Math.abs(kCh).toFixed(2)}%</span>
            </div>
            <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${latest.trading_date || '-'}</div>
        </div>
        <div class="index-card">
            <div class="label">KOSDAQ</div>
            <div>
                <span class="value">${Number(latest.kosdaq_close || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                <span class="change ${qCls}">${qArrow} ${Math.abs(qCh).toFixed(2)}%</span>
            </div>
            <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${latest.trading_date || '-'}</div>
        </div>
    `;
}

function renderDailySummaryAndFactors() {
    const summarySection = document.getElementById('daily-summary-section');
    const insightsSection = document.getElementById('daily-insights-section');
    const summary = document.getElementById('daily-summary');
    const factors = document.getElementById('daily-factors');

    if (!monthData.length) {
        if (summarySection) summarySection.style.display = 'none';
        if (insightsSection) insightsSection.style.display = '';
        if (summary) summary.textContent = '';
        if (factors) factors.innerHTML = '<li style="color:var(--text-secondary);">데이터가 없습니다.</li>';
        return;
    }

    const latest = monthData[monthData.length - 1];
    if (summarySection) summarySection.style.display = '';
    if (insightsSection) insightsSection.style.display = '';
    if (summary) {
        summary.textContent = latest.summary_text ||
            `KOSPI ${Number(latest.kospi_close || 0).toFixed(2)}pt (${Number(latest.kospi_change_pct || 0) >= 0 ? '+' : ''}${Number(latest.kospi_change_pct || 0).toFixed(2)}%), ` +
            `KOSDAQ ${Number(latest.kosdaq_close || 0).toFixed(2)}pt (${Number(latest.kosdaq_change_pct || 0) >= 0 ? '+' : ''}${Number(latest.kosdaq_change_pct || 0).toFixed(2)}%)`;
    }

    const rows = Array.isArray(latest.key_factors) ? latest.key_factors : [];
    if (factors) {
        factors.innerHTML = rows.length
            ? rows.map(x => `<li>${esc(String(x))}</li>`).join('')
            : '<li style="color:var(--text-secondary);">표시할 지표가 없습니다.</li>';
    }
}

function renderDailyCalendar() {
    const body = document.getElementById('calendar-body');
    if (!body) return;

    const firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    const dataMap = {};
    monthData.forEach(d => { dataMap[d.trading_date] = d; });

    let html = '';
    for (let i = 0; i < firstDay; i++) html += '<div class="cal-cell empty"></div>';

    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const data = dataMap[dateStr];
        const isToday = dateStr === todayStr;

        let indicator = '';
        if (data) {
            const pctVal = calendarIndex === 'kosdaq'
                ? Number(data.kosdaq_change_pct || 0)
                : Number(data.kospi_change_pct || 0);
            const cls = pctVal >= 0 ? 'up' : 'down';
            const arrow = pctVal >= 0 ? '▲' : '▼';
            indicator = `<div class="day-indicator ${cls}">${arrow} ${Math.abs(pctVal).toFixed(1)}%</div>`;
        }

        html += `
            <div class="cal-cell${isToday ? ' today' : ''}" onclick="${data ? `showDayDetail('${dateStr}')` : ''}" style="${data ? '' : 'opacity:0.45;cursor:default;'}">
                <div class="day-num">${day}</div>
                ${indicator}
            </div>`;
    }

    body.innerHTML = html;
}

function setCalendarIndex(kind) {
    calendarIndex = kind === 'kosdaq' ? 'kosdaq' : 'kospi';
    const kBtn = document.getElementById('cal-index-kospi');
    const qBtn = document.getElementById('cal-index-kosdaq');
    if (kBtn) kBtn.classList.toggle('active', calendarIndex === 'kospi');
    if (qBtn) qBtn.classList.toggle('active', calendarIndex === 'kosdaq');
    renderDailyCalendar();
}

async function refreshDaily() {
    const btn = document.getElementById('btn-refresh-daily');
    const msg = document.getElementById('daily-msg');
    btn.disabled = true;
    btn.textContent = '새로고침 중...';
    if (msg) msg.textContent = '';

    try {
        const result = await postJSON('/api/market/refresh-daily');
        await loadDailyMonth();
        if (currentTab === 'longterm') await loadLongTerm();
        const backfilled = Number(result?.backfilled_count || 0);
        if (msg) {
            msg.textContent = backfilled > 0
                ? `업데이트 완료 (누락 ${backfilled}건 보완)`
                : '업데이트 완료';
        }
    } catch (e) {
        if (msg) msg.textContent = `실패: ${e.message}`;
        alert('국내 시장 새로고침 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '지금 새로고침';
    }
}

async function showDayDetail(tradingDate) {
    const modal = document.getElementById('day-modal');
    const detail = document.getElementById('day-detail');
    if (!modal || !detail) return;

    detail.innerHTML = '<p style="text-align:center;">로딩 중...</p>';
    modal.style.display = 'flex';

    try {
        const data = await fetchJSON(`/api/market/daily/${tradingDate}`);
        const kCh = Number(data.kospi_change_pct || 0);
        const qCh = Number(data.kosdaq_change_pct || 0);
        const kCls = kCh >= 0 ? 'up' : 'down';
        const qCls = qCh >= 0 ? 'up' : 'down';

        let html = `<h3>${tradingDate} 국내 시장 브리핑</h3>`;
        html += `<div class="index-cards" style="margin-bottom:16px;">
            <div class="index-card">
                <div class="label">KOSPI</div>
                <div><span class="value" style="font-size:22px;">${Number(data.kospi_close || 0).toFixed(2)}</span>
                <span class="change ${kCls}">${kCh >= 0 ? '▲' : '▼'} ${Math.abs(kCh).toFixed(2)}%</span></div>
            </div>
            <div class="index-card">
                <div class="label">KOSDAQ</div>
                <div><span class="value" style="font-size:22px;">${Number(data.kosdaq_close || 0).toFixed(2)}</span>
                <span class="change ${qCls}">${qCh >= 0 ? '▲' : '▼'} ${Math.abs(qCh).toFixed(2)}%</span></div>
            </div>
        </div>`;

        if (data.summary_text) {
            html += `<div class="summary-box" style="margin-bottom:12px;">${esc(data.summary_text)}</div>`;
        }

        const factors = Array.isArray(data.key_factors) ? data.key_factors : [];
        if (factors.length) {
            html += '<div><h4 style="margin:0 0 8px 0; font-size:14px; color:var(--text-secondary);">핵심 지표</h4><ul class="factor-list">';
            html += factors.map(f => `<li>${esc(String(f))}</li>`).join('');
            html += '</ul></div>';
        }

        detail.innerHTML = html;
    } catch (e) {
        detail.innerHTML = `<p style="color:var(--text-secondary);">데이터를 불러올 수 없습니다: ${esc(e.message)}</p>`;
    }
}

function closeDayModal() {
    const modal = document.getElementById('day-modal');
    if (modal) modal.style.display = 'none';
}

window.showDayDetail = showDayDetail;
window.closeDayModal = closeDayModal;

// --- Long-term section (legacy) ---
async function loadLongTerm() {
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

function renderChart(kospi, semi, total) {
    const kospiMap = {}; kospi.forEach(d => { kospiMap[ymKey(d)] = d.close_price; });
    const semiAmtMap = {}; const semiRateMap = {};
    semi.forEach(d => { semiAmtMap[ymKey(d)] = Math.round(d.export_amt / 1000); semiRateMap[ymKey(d)] = d.export_rate; });
    const totalRateMap = {}; total.forEach(d => { totalRateMap[ymKey(d)] = d.export_rate; });

    const allMonths = [...new Set([...Object.keys(kospiMap), ...Object.keys(semiAmtMap), ...Object.keys(totalRateMap)])].sort();
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
                { type: 'bar', label: '반도체 수출 (백만불)', data: semiData, yAxisID: 'y', backgroundColor: 'rgba(37,99,235,0.4)', borderColor: '#2563eb', borderWidth: 1, order: 4 },
                { type: 'line', label: 'KOSPI (pt)', data: kospiData, yAxisID: 'y1', borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', borderWidth: 2, pointRadius: 2, tension: 0.3, fill: false, order: 1 },
                { type: 'line', label: '반도체 수출 증감률 (%)', data: semiRateData, yAxisID: 'y2', borderColor: '#f59e0b', borderWidth: 2, pointRadius: 2, tension: 0.3, borderDash: [5, 3], fill: false, order: 2 },
                { type: 'line', label: '총수출 증감률 (%)', data: totalRateData, yAxisID: 'y2', borderColor: '#10b981', borderWidth: 2, pointRadius: 2, tension: 0.3, fill: false, order: 3 },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { usePointStyle: true, pointStyle: 'circle', padding: 16 } },
            },
            scales: {
                x: {
                    ticks: {
                        callback(val) { const lbl = this.getLabelForValue(val); return lbl.endsWith('-01') ? lbl.slice(0, 4) : ''; },
                        maxRotation: 0,
                    },
                    grid: { display: false },
                },
                y: { position: 'left', title: { display: true, text: '반도체 수출 (백만불)', color: '#2563eb' }, ticks: { color: '#2563eb', callback: v => num(v) }, grid: { color: 'rgba(0,0,0,0.06)' } },
                y1: { position: 'right', title: { display: true, text: 'KOSPI (pt)', color: '#ef4444' }, ticks: { color: '#ef4444', callback: v => num(v) }, grid: { drawOnChartArea: false } },
                y2: { position: 'right', title: { display: true, text: '증감률 (%)', color: '#10b981' }, ticks: { color: '#10b981', callback: v => `${v}%` }, grid: { drawOnChartArea: false }, offset: true },
            },
        },
    });
}

function renderSummary(kospi, semi, total) {
    const container = document.getElementById('summary-cards');
    const cards = [];

    if (kospi.length) {
        const latest = kospi[kospi.length - 1];
        const prev = kospi.length >= 2 ? kospi[kospi.length - 2] : null;
        const change = prev ? ((latest.close_price - prev.close_price) / prev.close_price * 100).toFixed(1) : '-';
        const color = change > 0 ? '#ef4444' : change < 0 ? '#2563eb' : '#6b7280';
        cards.push(`<div class="card"><div class="card-label">KOSPI (${ymKey(latest)})</div><div class="card-value">${Number(latest.close_price).toFixed(2)}</div><div style="color:${color}; font-size:13px;">전월 대비 ${change}%</div></div>`);
    }
    if (semi.length) {
        const latest = semi[semi.length - 1];
        const amt = Math.round(latest.export_amt / 1000);
        cards.push(`<div class="card"><div class="card-label">반도체 수출 (${ymKey(latest)})</div><div class="card-value">${num(amt)} 백만불</div><div style="color:${latest.export_rate >= 0 ? '#10b981' : '#ef4444'}; font-size:13px;">YoY ${pct(latest.export_rate)}</div></div>`);
    }
    if (total.length) {
        const latest = total[total.length - 1];
        const color = latest.export_rate >= 0 ? '#10b981' : '#ef4444';
        cards.push(`<div class="card"><div class="card-label">총수출 증감률 (${ymKey(latest)})</div><div class="card-value" style="color:${color}">${pct(latest.export_rate)}</div></div>`);
    }
    container.innerHTML = cards.join('');
}

function renderTable(kospi, semi, total) {
    const kospiMap = {}; kospi.forEach(d => { kospiMap[ymKey(d)] = d.close_price; });
    const semiAmtMap = {}; const semiRateMap = {};
    semi.forEach(d => { semiAmtMap[ymKey(d)] = Math.round(d.export_amt / 1000); semiRateMap[ymKey(d)] = d.export_rate; });
    const totalRateMap = {}; total.forEach(d => { totalRateMap[ymKey(d)] = d.export_rate; });

    const allMonths = [...new Set([...Object.keys(kospiMap), ...Object.keys(semiAmtMap), ...Object.keys(totalRateMap)])].sort().reverse();
    const tbody = document.getElementById('data-tbody');
    const mobile = document.getElementById('data-mobile-cards');
    tbody.innerHTML = allMonths.map(m => {
        const k = kospiMap[m];
        const s = semiAmtMap[m];
        const sr = semiRateMap[m];
        const tr = totalRateMap[m];
        return `<tr><td>${m}</td><td>${k != null ? Number(k).toFixed(2) : '-'}</td><td>${s != null ? num(s) : '-'}</td><td class="${sr >= 0 ? 'positive' : 'negative'}">${sr != null ? pct(sr) : '-'}</td><td class="${tr >= 0 ? 'positive' : 'negative'}">${tr != null ? pct(tr) : '-'}</td></tr>`;
    }).join('');

    if (mobile) {
        mobile.innerHTML = allMonths.length ? allMonths.map(m => {
            const k = kospiMap[m];
            const s = semiAmtMap[m];
            const sr = semiRateMap[m];
            const tr = totalRateMap[m];
            return `
                <article class="mobile-card">
                    <div class="m-head">
                        <div class="m-title">${m}</div>
                    </div>
                    <div class="m-grid">
                        <div class="m-k">KOSPI</div><div class="m-v">${k != null ? Number(k).toFixed(2) : '-'}</div>
                        <div class="m-k">반도체 수출(백만불)</div><div class="m-v">${s != null ? num(s) : '-'}</div>
                        <div class="m-k">반도체 증감률</div><div class="m-v ${sr >= 0 ? 'positive' : 'negative'}">${sr != null ? pct(sr) : '-'}</div>
                        <div class="m-k">총수출 증감률</div><div class="m-v ${tr >= 0 ? 'positive' : 'negative'}">${tr != null ? pct(tr) : '-'}</div>
                    </div>
                </article>
            `;
        }).join('') : '<div class="mobile-empty">월별 데이터가 없습니다.</div>';
    }
}

function bindLongTermButtons() {
    document.getElementById('btn-fetch-kospi').onclick = async () => {
        const btn = document.getElementById('btn-fetch-kospi');
        btn.disabled = true;
        btn.textContent = '가져오는 중...';
        try {
            const data = await postJSON('/api/market/fetch-index?code=KOSPI&count=120');
            alert(`KOSPI ${data.fetched}개월 데이터 저장 완료`);
            await loadLongTerm();
            await loadDailyMonth();
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
            const data = await postJSON(`/api/market/fetch-exports?year_from=${yFrom}&year_to=${yTo}`);
            alert(`반도체 수출 ${data.fetched}개월 데이터 저장 (${data.skipped}개월 스킵)`);
            await loadLongTerm();
            await loadDailyMonth();
        } catch (e) {
            alert('반도체 수출 데이터 가져오기 실패: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '반도체수출 가져오기';
        }
    };

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
            if (!resp.ok) throw new Error(data.detail || resp.statusText);
            alert(`총수출 증감률 ${data.imported}개월 임포트 완료`);
            document.getElementById('import-textarea').value = '';
            await loadLongTerm();
            await loadDailyMonth();
        } catch (e) {
            alert('임포트 실패: ' + e.message);
        }
    };
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('tab-btn-daily').addEventListener('click', () => switchTab('daily'));
    document.getElementById('tab-btn-longterm').addEventListener('click', () => switchTab('longterm'));
    document.getElementById('btn-refresh-daily').addEventListener('click', refreshDaily);
    document.getElementById('btn-prev-month').addEventListener('click', () => changeDailyMonth(-1));
    document.getElementById('btn-next-month').addEventListener('click', () => changeDailyMonth(1));
    document.getElementById('cal-index-kospi').addEventListener('click', () => setCalendarIndex('kospi'));
    document.getElementById('cal-index-kosdaq').addEventListener('click', () => setCalendarIndex('kosdaq'));

    initYearSelectors();
    bindLongTermButtons();

    try {
        await Promise.all([loadDailyMonth(), loadLongTerm()]);
    } catch (e) {
        const msg = document.getElementById('daily-msg');
        if (msg) msg.textContent = `초기 로딩 실패: ${e.message}`;
    }
});
