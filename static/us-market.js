/**
 * 미국 시장 모니터링 프론트엔드
 */

let currentYear, currentMonth;
let monthData = [];
let chartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth() + 1;

    document.getElementById('btn-refresh').addEventListener('click', refreshNow);
    document.getElementById('btn-prev').addEventListener('click', () => changeMonth(-1));
    document.getElementById('btn-next').addEventListener('click', () => changeMonth(1));

    loadMonth();
});

// ── API 헬퍼 ──
async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const resp = await fetch(path, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `API error: ${resp.status}`);
    }
    return resp.json();
}

// ── 월 변경 ──
function changeMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 12) { currentMonth = 1; currentYear++; }
    if (currentMonth < 1) { currentMonth = 12; currentYear--; }
    loadMonth();
}

// ── 월간 데이터 로드 ──
async function loadMonth() {
    updateMonthLabel();
    try {
        monthData = await api('GET', `/api/us-market/daily?year=${currentYear}&month=${currentMonth}`);
        renderAll();
    } catch (e) {
        console.error('Failed to load month data:', e);
        monthData = [];
        renderAll();
    }
}

function updateMonthLabel() {
    document.getElementById('month-label').textContent = `${currentYear}년 ${currentMonth}월`;
    document.getElementById('calendar-title').textContent = `${currentYear}년 ${currentMonth}월 캘린더`;
}

// ── 전체 렌더링 ──
function renderAll() {
    renderIndexCards();
    renderInsights();
    renderCalendar();
    renderChart();
}

// ── 지수 카드 ──
function renderIndexCards() {
    const container = document.getElementById('index-cards');
    if (!monthData.length) {
        container.innerHTML = '<div class="no-data"><p>이번 달 데이터가 없습니다.</p><p>새로고침 버튼을 눌러 데이터를 가져오세요.</p></div>';
        hideInsights();
        return;
    }

    const latest = monthData[monthData.length - 1];
    const sp500Cls = latest.sp500_change_pct >= 0 ? 'up' : 'down';
    const nasdaqCls = latest.nasdaq_change_pct >= 0 ? 'up' : 'down';
    const sp500Arrow = latest.sp500_change_pct >= 0 ? '▲' : '▼';
    const nasdaqArrow = latest.nasdaq_change_pct >= 0 ? '▲' : '▼';

    container.innerHTML = `
        <div class="index-card">
            <div class="label">S&P 500 (SPY)</div>
            <div>
                <span class="value">${latest.sp500_close.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                <span class="change ${sp500Cls}">${sp500Arrow} ${Math.abs(latest.sp500_change_pct).toFixed(2)}%</span>
            </div>
            <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${latest.trading_date}</div>
        </div>
        <div class="index-card">
            <div class="label">NASDAQ (QQQ)</div>
            <div>
                <span class="value">${latest.nasdaq_close.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                <span class="change ${nasdaqCls}">${nasdaqArrow} ${Math.abs(latest.nasdaq_change_pct).toFixed(2)}%</span>
            </div>
            <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${latest.trading_date}</div>
        </div>
    `;
}

// ── 인사이트 (요약 + 요인 + 섹터) ──
function hideInsights() {
    document.getElementById('summary-section').style.display = 'none';
    document.getElementById('earnings-section').style.display = 'none';
    document.getElementById('insights-section').style.display = 'none';
    const mobileSection = document.getElementById('mobile-insights-section');
    if (mobileSection) mobileSection.style.display = 'none';
}

function renderInsights() {
    if (!monthData.length) { hideInsights(); return; }

    const latest = monthData[monthData.length - 1];

    // 요약
    const summarySection = document.getElementById('summary-section');
    if (latest.summary_text) {
        document.getElementById('summary-box').textContent = latest.summary_text;
        summarySection.style.display = '';
    } else {
        summarySection.style.display = 'none';
    }

    // 실적발표
    const earningsSection = document.getElementById('earnings-section');
    if (latest.earnings_text) {
        document.getElementById('earnings-text').textContent = latest.earnings_text;
        earningsSection.style.display = '';
    } else {
        earningsSection.style.display = 'none';
    }

    // 주요 요인
    const insightsSection = document.getElementById('insights-section');
    const mobileInsightsSection = document.getElementById('mobile-insights-section');
    const factors = latest.key_factors || [];

    if (!factors.length) {
        insightsSection.style.display = 'none';
        if (mobileInsightsSection) mobileInsightsSection.style.display = 'none';
        return;
    }
    insightsSection.style.display = '';
    if (mobileInsightsSection) mobileInsightsSection.style.display = '';

    // 요인
    const factorList = document.getElementById('key-factors');
    const mobileFactorList = document.getElementById('mobile-key-factors');
    if (factors.length) {
        factorList.innerHTML = factors.map(f => `<li>${esc(typeof f === 'string' ? f : f.toString())}</li>`).join('');
        if (mobileFactorList) {
            mobileFactorList.innerHTML = factors.map(f => `<div class="m-sub" style="padding:5px 0;border-bottom:1px solid var(--border);">${esc(typeof f === 'string' ? f : f.toString())}</div>`).join('');
        }
    } else {
        factorList.innerHTML = '<li style="color:var(--text-secondary);">정보 없음</li>';
        if (mobileFactorList) mobileFactorList.innerHTML = '<div class="m-sub">정보 없음</div>';
    }
}

// ── 캘린더 ──
function renderCalendar() {
    const body = document.getElementById('calendar-body');
    const firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

    // 날짜별 데이터 맵
    const dataMap = {};
    monthData.forEach(d => { dataMap[d.trading_date] = d; });

    let html = '';

    // 빈 셀 (월 시작 요일 전)
    for (let i = 0; i < firstDay; i++) {
        html += '<div class="cal-cell empty"></div>';
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${currentYear}-${String(currentMonth).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const data = dataMap[dateStr];
        const isToday = dateStr === todayStr;

        let indicator = '';
        if (data) {
            const pct = data.sp500_change_pct;
            const cls = pct >= 0 ? 'up' : 'down';
            const arrow = pct >= 0 ? '▲' : '▼';
            indicator = `<div class="day-indicator ${cls}">${arrow} ${Math.abs(pct).toFixed(1)}%</div>`;
        }

        html += `
            <div class="cal-cell${isToday ? ' today' : ''}${data ? '' : ''}"
                 onclick="${data ? `showDayDetail('${dateStr}')` : ''}"
                 style="${data ? '' : 'opacity:0.5;cursor:default;'}">
                <div class="day-num">${day}</div>
                ${indicator}
            </div>`;
    }

    body.innerHTML = html;
}

// ── 날짜 상세 모달 ──
async function showDayDetail(tradingDate) {
    const modal = document.getElementById('day-modal');
    const detail = document.getElementById('day-detail');

    detail.innerHTML = '<p style="text-align:center;">로딩 중...</p>';
    modal.style.display = 'flex';

    try {
        const data = await api('GET', `/api/us-market/daily/${tradingDate}`);
        const sp500Cls = data.sp500_change_pct >= 0 ? 'up' : 'down';
        const nasdaqCls = data.nasdaq_change_pct >= 0 ? 'up' : 'down';

        let html = `<h3>${tradingDate} 미국 시장 브리핑</h3>`;

        // 지수
        html += `<div class="index-cards" style="margin-bottom:16px;">
            <div class="index-card">
                <div class="label">S&P 500 (SPY)</div>
                <div><span class="value" style="font-size:22px;">${data.sp500_close}</span>
                <span class="change ${sp500Cls}">${data.sp500_change_pct >= 0 ? '▲' : '▼'} ${Math.abs(data.sp500_change_pct).toFixed(2)}%</span></div>
            </div>
            <div class="index-card">
                <div class="label">NASDAQ (QQQ)</div>
                <div><span class="value" style="font-size:22px;">${data.nasdaq_close}</span>
                <span class="change ${nasdaqCls}">${data.nasdaq_change_pct >= 0 ? '▲' : '▼'} ${Math.abs(data.nasdaq_change_pct).toFixed(2)}%</span></div>
            </div>
        </div>`;

        // 요약
        if (data.summary_text) {
            html += `<div class="modal-section"><h4>시장 요약</h4><p>${esc(data.summary_text)}</p></div>`;
        }

        // 실적발표
        if (data.earnings_text) {
            html += `<div class="earnings-box"><h4>실적 발표 / 컨퍼런스콜</h4><p>${esc(data.earnings_text)}</p></div>`;
        }

        // 변동 요인
        const factors = data.key_factors || [];
        if (factors.length) {
            html += `<div class="modal-section"><h4>주요 변동 요인</h4><ul class="factor-list">`;
            factors.forEach(f => { html += `<li>${esc(typeof f === 'string' ? f : f.toString())}</li>`; });
            html += '</ul></div>';
        }

        // 섹터
        const strong = data.sectors_strong || [];
        const weak = data.sectors_weak || [];
        if (strong.length || weak.length) {
            html += '<div class="modal-section"><h4>섹터 성과</h4>';
            if (strong.length) {
                html += '<div style="margin-bottom:8px;font-size:12px;color:var(--text-secondary);">강세</div>';
                strong.forEach(s => {
                    const name = typeof s === 'object' ? s.name : s;
                    const pct = typeof s === 'object' ? s.change_pct : 0;
                    html += `<div class="sector-item"><span>${esc(name)}</span><span class="sector-pct up">+${Math.abs(pct).toFixed(2)}%</span></div>`;
                });
            }
            if (weak.length) {
                html += '<div style="margin-top:12px;margin-bottom:8px;font-size:12px;color:var(--text-secondary);">약세</div>';
                weak.forEach(s => {
                    const name = typeof s === 'object' ? s.name : s;
                    const pct = typeof s === 'object' ? s.change_pct : 0;
                    html += `<div class="sector-item"><span>${esc(name)}</span><span class="sector-pct down">${pct.toFixed(2)}%</span></div>`;
                });
            }
            html += '</div>';
        }

        detail.innerHTML = html;
    } catch (e) {
        detail.innerHTML = `<p style="color:var(--text-secondary);">데이터를 불러올 수 없습니다: ${esc(e.message)}</p>`;
    }
}

function closeDayModal() {
    document.getElementById('day-modal').style.display = 'none';
}

// ── 차트 ──
function renderChart() {
    if (!monthData.length) return;

    const labels = monthData.map(d => d.trading_date.substring(5));
    const sp500 = monthData.map(d => d.sp500_close);
    const nasdaq = monthData.map(d => d.nasdaq_close);

    if (chartInstance) chartInstance.destroy();

    const ctx = document.getElementById('chart-indices').getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'S&P 500 (SPY)',
                    data: sp500,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37,99,235,.1)',
                    fill: true,
                    tension: 0.3,
                    yAxisID: 'y',
                },
                {
                    label: 'NASDAQ (QQQ)',
                    data: nasdaq,
                    borderColor: '#dc2626',
                    backgroundColor: 'rgba(220,38,38,.1)',
                    fill: true,
                    tension: 0.3,
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: {
                y: { type: 'linear', position: 'left', title: { display: true, text: 'S&P 500 (SPY)' } },
                y1: { type: 'linear', position: 'right', title: { display: true, text: 'NASDAQ (QQQ)' }, grid: { drawOnChartArea: false } },
            },
        },
    });
}

// ── 수동 새로고침 ──
async function refreshNow() {
    const btn = document.getElementById('btn-refresh');
    btn.disabled = true;
    btn.textContent = '새로고침 중...';
    try {
        const result = await api('POST', '/api/us-market/refresh');
        await loadMonth();
        const backfilled = Number(result?.backfilled_count || 0);
        let msg = '미국 시장 데이터가 업데이트되었습니다.';
        if (backfilled > 0) {
            msg += ` 누락 과거일 ${backfilled}건도 자동 보완했습니다.`;
        }
        if (result?.warning) {
            msg += `\n\n참고: ${result.warning}`;
        }
        alert(msg);
    } catch (e) {
        alert('새로고침 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '지금 새로고침';
    }
}

// ── 유틸 ──
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
