const API = '';
let currentCompanyId = null;
let stockChart = null;
let visitReturns = {};
let cachedVisits = [];

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    await loadCompanies();

    // Auto-select company from URL query param ?company=ID
    const urlParams = new URLSearchParams(window.location.search);
    const companyParam = urlParams.get('company');
    if (companyParam) {
        const sel = document.getElementById('company-select');
        sel.value = companyParam;
        sel.dispatchEvent(new Event('change'));
    } else {
        await loadUpcoming();
        loadYearlyStats();
        loadAllEvents();
    }

    document.getElementById('company-select').addEventListener('change', async (e) => {
        currentCompanyId = e.target.value ? parseInt(e.target.value) : null;
        if (currentCompanyId) {
            document.getElementById('btn-add-visit').style.display = '';
            document.getElementById('btn-add-event').style.display = '';
            document.getElementById('company-detail').style.display = '';
            document.getElementById('yearly-stats').style.display = 'none';
            document.getElementById('upcoming-section').style.display = 'none';
            document.getElementById('all-events-section').style.display = 'none';
            document.getElementById('all-visits-section').style.display = 'none';
            switchTab('visits');
        } else {
            document.getElementById('btn-add-visit').style.display = 'none';
            document.getElementById('btn-add-event').style.display = 'none';
            document.getElementById('company-detail').style.display = 'none';
            document.getElementById('upcoming-section').style.display = '';
            loadYearlyStats();
            loadAllEvents();
        }
    });

    document.querySelectorAll('.detail-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
});

// --- Helpers ---
function num(n) { return n != null ? Number(n).toLocaleString() : '-'; }
function fmtDate(d) {
    if (!d) return '-';
    if (d.length === 8) return `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`;
    return d;
}
function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
    return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

function sentimentIcon(s) {
    const icons = { '매우 좋음': '🤩', '좋음': '😊', '보통': '😐', '별로': '😕', '노관심': '🙅' };
    return icons[s] || '';
}

async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body && !(body instanceof FormData)) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    } else if (body instanceof FormData) {
        opts.body = body;
    }
    const resp = await fetch(API + path, opts);
    if (!resp.ok) throw new Error(`API ${resp.status}`);
    return resp.json();
}

// --- Modal ---
function showModal(id) { document.getElementById(id).style.display = 'flex'; }
function hideModal(id) { document.getElementById(id).style.display = 'none'; }
function closeModalOverlay(e) {
    if (e.target.classList.contains('modal-overlay')) e.target.style.display = 'none';
}

// --- Tab ---
function switchTab(tabName) {
    document.querySelectorAll('.detail-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    document.getElementById('tab-' + tabName).style.display = '';

    if (tabName === 'visits') loadVisits();
    else if (tabName === 'materials') loadMaterials();
    else if (tabName === 'events') loadEvents();
    else if (tabName === 'reports') loadReports();
    else if (tabName === 'consensus') loadConsensus();

    loadStockChart();
}

// --- Companies ---
async function loadCompanies() {
    const companies = await api('GET', '/api/visit/companies');
    const sel = document.getElementById('company-select');
    const cur = sel.value;
    sel.innerHTML = '<option value="">기업을 선택하세요</option>';
    companies.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.name + (c.stock_code ? ` (${c.stock_code})` : '');
        sel.appendChild(opt);
    });
    if (cur) sel.value = cur;
}

async function searchStockByName(query) {
    try {
        return await api('GET', `/api/visit/search-stock?name=${encodeURIComponent(query)}`);
    } catch {
        return [];
    }
}

async function addCompany() {
    const name = document.getElementById('f-company-name').value.trim();
    if (!name) return alert('회사명을 입력하세요');
    let stock_code = document.getElementById('f-company-stock').value.trim() || null;

    if (!stock_code) {
        try {
            const results = await searchStockByName(name);
            if (results.length > 0) {
                const exact = results.find(r => r.name === name);
                const match = exact || results[0];
                if (confirm(`"${match.name}" (${match.code}, ${match.market})을(를) 추가하시겠습니까?`)) {
                    stock_code = match.code;
                } else {
                    return;
                }
            } else {
                if (!confirm('해당 이름의 종목을 찾을 수 없습니다.\n종목코드 없이 추가하시겠습니까?\n\n종목코드를 직접 입력하려면 "취소"를 누르세요.')) {
                    return;
                }
            }
        } catch (e) {
            // Search failed, continue without stock code
        }
    }

    await api('POST', '/api/visit/companies', {
        name,
        stock_code,
        sector: document.getElementById('f-company-sector').value.trim() || null,
        notes: document.getElementById('f-company-notes').value.trim() || null,
    });
    hideModal('company-modal');
    document.getElementById('f-company-name').value = '';
    document.getElementById('f-company-stock').value = '';
    document.getElementById('f-company-sector').value = '';
    document.getElementById('f-company-notes').value = '';
    await loadCompanies();
}

// --- Calendar ---
let calYear, calMonth, calVisits = [];

function initCalendar() {
    const now = new Date();
    calYear = now.getFullYear();
    calMonth = now.getMonth();
    renderCalendar();
}

function calNav(delta) {
    calMonth += delta;
    if (calMonth < 0) { calMonth = 11; calYear--; }
    if (calMonth > 11) { calMonth = 0; calYear++; }
    renderCalendar();
}

function renderCalendar() {
    const title = document.getElementById('cal-title');
    title.textContent = `${calYear}년 ${calMonth + 1}월`;

    const first = new Date(calYear, calMonth, 1);
    const startDay = first.getDay();
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();

    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

    // Build visit lookup for this month
    const visitMap = {};
    calVisits.forEach(v => {
        const d = v.visit_date;
        if (!visitMap[d]) visitMap[d] = [];
        visitMap[d].push(v);
    });

    let html = '';
    let day = 1 - startDay;
    for (let row = 0; row < 6; row++) {
        html += '<tr>';
        for (let col = 0; col < 7; col++, day++) {
            if (day < 1 || day > daysInMonth) {
                html += '<td></td>';
            } else {
                const dateStr = `${calYear}-${String(calMonth+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
                const visits = visitMap[dateStr];
                const isToday = dateStr === todayStr;
                const hasCompleted = visits && visits.some(v => v.status === 'completed');
                let cls = 'cal-day';
                if (isToday) cls += ' today';
                if (visits) cls += ' has-visit' + (hasCompleted ? ' completed' : '');
                const tooltip = visits ? `<span class="cal-tooltip">${visits.map(v => v.company_name).join(', ')}</span>` : '';
                html += `<td><span class="${cls}">${day}${tooltip}</span></td>`;
            }
        }
        html += '</tr>';
        if (day > daysInMonth) break;
    }
    document.getElementById('cal-body').innerHTML = html;
}

// --- Upcoming ---
async function loadUpcoming() {
    // Fetch all visits for calendar
    try {
        const all = await api('GET', '/api/visit/all-visits');
        calVisits = all;
    } catch { calVisits = []; }
    initCalendar();

    const visits = await api('GET', '/api/visit/upcoming');
    const el = document.getElementById('upcoming-list');
    if (!visits.length) {
        el.innerHTML = '<p class="empty-msg">등록된 일정이 없습니다</p>';
        return;
    }
    el.innerHTML = visits.map(v => `
        <div class="upcoming-item">
            <span><strong>${v.visit_date}</strong> ${v.visit_time || ''}</span>
            <span><strong>${v.company_name}</strong></span>
            <span>${v.purpose || '-'}</span>
            <button class="btn btn-secondary" style="font-size:0.75rem;padding:3px 8px;" onclick="editVisit(${v.id}, '${v.visit_date}', '${v.visit_time || ''}', '${(v.purpose || '').replace(/'/g, "\\'")}', '${(v.attendees || '').replace(/'/g, "\\'")}')">수정</button>
        </div>
    `).join('');
}

// --- All Events Table ---
let allEventsCache = [];
let allEventsFilter = 'all';

async function loadAllEvents() {
    try {
        allEventsCache = await api('GET', '/api/visit/all-events');
        renderAllEvents();
    } catch (e) {
        console.error('Failed to load all events:', e);
    }
}

function filterAllEvents(filter, btn) {
    allEventsFilter = filter;
    document.querySelectorAll('.event-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderAllEvents();
}

function renderAllEvents() {
    const section = document.getElementById('all-events-section');
    const tbody = document.getElementById('all-events-tbody');
    const filtered = allEventsFilter === 'all'
        ? allEventsCache
        : allEventsCache.filter(e => e.event_type === allEventsFilter);

    if (!allEventsCache.length) {
        section.style.display = 'none';
        return;
    }
    section.style.display = '';

    const typeLabels = { issue: '이슈', momentum: '모멘텀', followup: '팔로업' };
    const typeColors = { issue: '#ef4444', momentum: '#10b981', followup: '#f59e0b' };

    if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:16px;">해당 유형의 데이터가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(e => `
        <tr>
            <td style="text-align:left;white-space:nowrap;">${e.event_date}</td>
            <td style="text-align:left;font-weight:600;">${e.company_name}</td>
            <td style="text-align:left;"><span class="event-type-tag" style="background:${typeColors[e.event_type] || '#64748b'};">${typeLabels[e.event_type] || e.event_type}</span></td>
            <td style="text-align:left;font-weight:500;">${e.title}</td>
            <td style="text-align:left;color:var(--text-muted);font-size:0.8rem;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${e.description || '-'}</td>
        </tr>
    `).join('');
}

// --- All Visit Results Table ---
let allVisitResultsCache = [];
let allVisitResultsFilter = 'all';

function renderAllVisitResults() {
    const section = document.getElementById('all-visits-section');
    const tbody = document.getElementById('all-visits-tbody');
    const completed = allVisitResultsCache.filter(v => v.status === 'completed');

    if (!completed.length) {
        section.style.display = 'none';
        return;
    }
    section.style.display = '';

    const filtered = allVisitResultsFilter === 'all'
        ? completed
        : completed.filter(v => v.summary === allVisitResultsFilter);

    if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:16px;">해당 결과가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(v => `
        <tr>
            <td style="text-align:left;white-space:nowrap;">${v.visit_date}</td>
            <td style="text-align:left;font-weight:600;">${v.company_name}</td>
            <td style="text-align:center;font-size:1.3rem;" title="${v.summary || ''}">${sentimentIcon(v.summary) || '-'}</td>
            <td style="text-align:left;color:var(--text-muted);font-size:0.85rem;">${v.purpose || '-'}</td>
        </tr>
    `).join('');
}

function filterAllVisitResults(filter, btn) {
    allVisitResultsFilter = filter;
    btn.closest('.event-filter-tabs').querySelectorAll('.event-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderAllVisitResults();
}

// --- Yearly Stats ---
async function loadYearlyStats() {
    try {
        const allVisits = await api('GET', '/api/visit/all-visits');

        // Update visit results table
        allVisitResultsCache = allVisits;
        renderAllVisitResults();

        const completed = allVisits.filter(v => v.status === 'completed');
        if (!completed.length) {
            document.getElementById('yearly-stats').style.display = 'none';
            return;
        }

        // Group by year
        const byYear = {};
        completed.forEach(v => {
            const year = v.visit_date.slice(0, 4);
            if (!byYear[year]) byYear[year] = [];
            byYear[year].push(v);
        });

        const years = Object.keys(byYear).sort();

        // Get unique companies with stock_code
        const companies = {};
        completed.forEach(v => {
            if (v.stock_code && !companies[v.company_id]) {
                companies[v.company_id] = { name: v.company_name, stock_code: v.stock_code };
            }
        });

        // Fetch stock data for each company
        const stockByCompany = {};
        await Promise.all(Object.keys(companies).map(async (cid) => {
            try {
                const data = await api('GET', `/api/visit/stock/${cid}`);
                if (data.length) stockByCompany[cid] = data;
            } catch {}
        }));

        // Compute returns per year (all visits + best)
        const yearStats = {};
        years.forEach(year => {
            const visits = byYear[year];
            const uniqueCompanies = new Set(visits.map(v => v.company_id));
            yearStats[year] = { count: visits.length, companies: uniqueCompanies.size, best: null, allReturns: [] };

            visits.forEach(v => {
                const stockData = stockByCompany[v.company_id];
                if (!stockData || !stockData.length) return;

                const sorted = stockData.slice().sort((a, b) => fmtDate(a.date).localeCompare(fmtDate(b.date)));
                const currentPrice = sorted[sorted.length - 1].close;

                let startIdx = -1;
                for (let i = 0; i < sorted.length; i++) {
                    if (fmtDate(sorted[i].date) >= v.visit_date) { startIdx = i; break; }
                }
                if (startIdx === -1) return;
                const visitPrice = sorted[startIdx].close;
                if (!visitPrice || visitPrice <= 0) return;

                let maxPrice = visitPrice;
                for (let i = startIdx + 1; i < sorted.length; i++) {
                    if (sorted[i].close > maxPrice) maxPrice = sorted[i].close;
                }
                const maxReturn = (maxPrice - visitPrice) / visitPrice * 100;
                const currentReturn = (currentPrice - visitPrice) / visitPrice * 100;

                const entry = {
                    name: v.company_name,
                    visitDate: v.visit_date,
                    maxReturn,
                    currentReturn,
                    sentiment: v.summary || '',
                };
                yearStats[year].allReturns.push(entry);

                if (!yearStats[year].best || maxReturn > yearStats[year].best.maxReturn) {
                    yearStats[year].best = entry;
                }
            });

            yearStats[year].allReturns.sort((a, b) => b.maxReturn - a.maxReturn);
        });

        // Store for modal access
        window._yearReturnData = yearStats;

        // Render
        const container = document.getElementById('yearly-stats-cards');
        container.innerHTML = years.map(year => {
            const s = yearStats[year];
            const clickable = s.allReturns.length > 0;
            const bestHtml = s.best
                ? `<div class="ys-best" ${clickable ? `onclick="showYearReturns('${year}')" style="cursor:pointer;"` : ''}>
                    <span class="ys-best-label">Best</span>
                    <span class="ys-best-name">${s.best.name}</span>
                    <span class="ys-best-return ${s.best.maxReturn >= 0 ? 'positive' : 'negative'}">${s.best.maxReturn >= 0 ? '+' : ''}${s.best.maxReturn.toFixed(1)}%</span>
                   </div>
                   <div class="ys-current" ${clickable ? `onclick="showYearReturns('${year}')" style="cursor:pointer;"` : ''}>현재 수익률: <span class="${s.best.currentReturn >= 0 ? 'positive' : 'negative'}">${s.best.currentReturn >= 0 ? '+' : ''}${s.best.currentReturn.toFixed(1)}%</span></div>`
                : '<div class="ys-best"><span class="ys-no-data">주가 데이터 없음</span></div>';
            return `
                <div class="ys-card">
                    <div class="ys-year">${year}</div>
                    <div class="ys-count"><span class="ys-count-label">탐방 횟수 : </span>${s.count}<span class="ys-unit">회</span></div>
                    <div class="ys-companies">${s.companies}개 기업</div>
                    ${bestHtml}
                </div>
            `;
        }).join('');
        document.getElementById('yearly-stats').style.display = '';
    } catch (e) {
        console.error('Failed to load yearly stats:', e);
    }
}

function showYearReturns(year) {
    const stats = window._yearReturnData && window._yearReturnData[year];
    if (!stats || !stats.allReturns.length) return;

    const tbody = stats.allReturns.map(r => {
        const maxCls = r.maxReturn >= 0 ? 'positive' : 'negative';
        const curCls = r.currentReturn >= 0 ? 'positive' : 'negative';
        return `<tr>
            <td style="text-align:left;font-weight:500;">${r.name}</td>
            <td style="text-align:center;">${r.visitDate}</td>
            <td class="${maxCls}" style="font-weight:700;">${r.maxReturn >= 0 ? '+' : ''}${r.maxReturn.toFixed(1)}%</td>
            <td class="${curCls}" style="font-weight:700;">${r.currentReturn >= 0 ? '+' : ''}${r.currentReturn.toFixed(1)}%</td>
            <td style="text-align:center;font-size:1.3rem;">${sentimentIcon(r.sentiment) || '-'}</td>
        </tr>`;
    }).join('');

    const modal = document.getElementById('year-return-modal');
    document.getElementById('year-return-title').textContent = `${year}년 탐방 수익률`;
    document.getElementById('year-return-tbody').innerHTML = tbody;
    modal.style.display = 'flex';
}

// --- Visits ---
async function loadVisits() {
    if (!currentCompanyId) return;
    cachedVisits = await api('GET', `/api/visit/companies/${currentCompanyId}/visits`);
    renderVisitCards();
}

function renderVisitCards() {
    const el = document.getElementById('visits-list');
    if (!cachedVisits.length) {
        el.innerHTML = '<p class="empty-msg">탐방 이력이 없습니다</p>';
        return;
    }
    el.innerHTML = cachedVisits.map(v => {
        const ret = visitReturns[v.id];
        const retBadge = ret ? `<span class="return-badge ${ret.return_rate >= 0 ? 'positive' : 'negative'}" onclick="showReturnDetail(${v.id})" title="탐방 후 최고 수익률 (클릭시 차트에서 상세)">${ret.return_rate >= 0 ? '+' : ''}${ret.return_rate.toFixed(1)}%</span>` : '';
        const retInfo = ret ? `<div class="return-detail-mini">탐방일 종가 ${num(ret.visit_price)}원 → 최고 ${num(ret.max_price)}원 (${ret.max_date}) | 현재 ${num(ret.current_price)}원 (${ret.current_return >= 0 ? '+' : ''}${ret.current_return.toFixed(1)}%)</div>` : '';
        return `
            <div class="visit-card ${v.status}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <div>
                        <strong>${v.visit_date}</strong> ${v.visit_time || ''}
                        <span class="badge badge-${v.status === 'completed' ? 'momentum' : v.status === 'cancelled' ? 'issue' : 'visit'}">${v.status === 'completed' ? '완료' : v.status === 'cancelled' ? '취소' : '예정'}</span>
                        ${retBadge}
                    </div>
                    <div style="display:flex;gap:6px;">
                        ${v.status === 'scheduled' ? `<button class="btn btn-secondary" style="font-size:0.75rem;padding:3px 8px;" onclick="editVisit(${v.id}, '${v.visit_date}', '${v.visit_time || ''}', '${(v.purpose || '').replace(/'/g, "\\'")}', '${(v.attendees || '').replace(/'/g, "\\'")}')">수정</button><button class="btn btn-secondary" style="font-size:0.75rem;padding:3px 8px;" onclick="completeVisit(${v.id})">완료</button>` : ''}
                        <button class="btn btn-danger" onclick="deleteVisit(${v.id})">삭제</button>
                    </div>
                </div>
                <div style="font-size:0.85rem;color:var(--text-muted);">
                    ${v.purpose ? `<div>목적: ${v.purpose}</div>` : ''}
                    ${v.attendees ? `<div>참석자: ${v.attendees}</div>` : ''}
                    ${v.summary ? `<div style="margin-top:6px;color:var(--text);">${sentimentIcon(v.summary)} ${v.summary}</div>` : ''}
                    ${retInfo}
                </div>
            </div>
        `;
    }).join('');
}

function computeVisitReturns(stockData, visits) {
    visitReturns = {};
    if (!stockData.length || !visits.length) return;
    const sorted = stockData.slice().sort((a, b) => fmtDate(a.date).localeCompare(fmtDate(b.date)));
    const currentPrice = sorted[sorted.length - 1].close;

    visits.filter(v => v.status !== 'cancelled').forEach(v => {
        let startIdx = -1;
        for (let i = 0; i < sorted.length; i++) {
            if (fmtDate(sorted[i].date) >= v.visit_date) { startIdx = i; break; }
        }
        if (startIdx === -1) return;
        const visitPrice = sorted[startIdx].close;
        if (!visitPrice || visitPrice <= 0) return;

        let maxPrice = visitPrice, maxDate = fmtDate(sorted[startIdx].date);
        for (let i = startIdx + 1; i < sorted.length; i++) {
            if (sorted[i].close > maxPrice) {
                maxPrice = sorted[i].close;
                maxDate = fmtDate(sorted[i].date);
            }
        }
        visitReturns[v.id] = {
            visit_date: v.visit_date, visit_price: visitPrice,
            max_price: maxPrice, max_date: maxDate,
            return_rate: (maxPrice - visitPrice) / visitPrice * 100,
            current_price: currentPrice,
            current_return: (currentPrice - visitPrice) / visitPrice * 100,
        };
    });
}

function showReturnDetail(visitId) {
    const ret = visitReturns[visitId];
    if (!ret || !stockChart) return;
    document.getElementById('chart-section').scrollIntoView({ behavior: 'smooth' });
    const ann = stockChart.options.plugins.annotation.annotations;
    Object.keys(ann).forEach(k => { if (k.startsWith('ret_')) delete ann[k]; });

    ann['ret_box'] = {
        type: 'box', xMin: ret.visit_date, xMax: ret.max_date,
        backgroundColor: 'rgba(37,99,235,0.06)', borderColor: 'rgba(37,99,235,0.2)', borderWidth: 1,
    };
    ann['ret_visit'] = {
        type: 'line', yMin: ret.visit_price, yMax: ret.visit_price,
        xMin: ret.visit_date, xMax: ret.max_date,
        borderColor: '#64748b', borderWidth: 1, borderDash: [3, 3],
        label: { display: true, content: `탐방일: ${num(ret.visit_price)}원`, position: 'start', backgroundColor: 'rgba(100,116,139,0.85)', color: 'white', font: { size: 10 } },
    };
    ann['ret_max'] = {
        type: 'line', yMin: ret.max_price, yMax: ret.max_price,
        xMin: ret.visit_date, xMax: ret.max_date,
        borderColor: '#10b981', borderWidth: 1.5, borderDash: [3, 3],
        label: { display: true, content: `최고가: ${num(ret.max_price)}원 (${ret.return_rate >= 0 ? '+' : ''}${ret.return_rate.toFixed(1)}%)`, position: 'end', backgroundColor: 'rgba(16,185,129,0.85)', color: 'white', font: { size: 10 } },
    };
    stockChart.update();
}

let editingVisitId = null;

async function addVisit() {
    const date = document.getElementById('f-visit-date').value;
    if (!date) return alert('탐방일을 선택하세요');
    if (editingVisitId) {
        await api('PUT', `/api/visit/visits/${editingVisitId}`, {
            visit_date: date,
            visit_time: document.getElementById('f-visit-time').value || null,
            purpose: document.getElementById('f-visit-purpose').value.trim() || null,
            attendees: document.getElementById('f-visit-attendees').value.trim() || null,
        });
        editingVisitId = null;
    } else {
        if (!currentCompanyId) return alert('기업을 선택하세요');
        await api('POST', '/api/visit/visits', {
            company_id: currentCompanyId,
            visit_date: date,
            visit_time: document.getElementById('f-visit-time').value || null,
            purpose: document.getElementById('f-visit-purpose').value.trim() || null,
            attendees: document.getElementById('f-visit-attendees').value.trim() || null,
        });
    }
    hideModal('visit-modal');
    await loadVisits();
    await loadUpcoming();
    await loadStockChart();
}

function openNewVisitModal() {
    editingVisitId = null;
    document.getElementById('visit-modal-title').textContent = '탐방 일정 등록';
    document.getElementById('visit-modal-submit').textContent = '등록';
    document.getElementById('f-visit-date').value = '';
    document.getElementById('f-visit-time').value = '';
    document.getElementById('f-visit-purpose').value = '';
    document.getElementById('f-visit-attendees').value = '';
    showModal('visit-modal');
}

function editVisit(visitId, date, time, purpose, attendees) {
    editingVisitId = visitId;
    document.getElementById('visit-modal-title').textContent = '탐방 일정 수정';
    document.getElementById('visit-modal-submit').textContent = '수정';
    document.getElementById('f-visit-date').value = date;
    document.getElementById('f-visit-time').value = time;
    document.getElementById('f-visit-purpose').value = purpose;
    document.getElementById('f-visit-attendees').value = attendees;
    showModal('visit-modal');
}

let completingVisitId = null;
let selectedSentiment = null;

function completeVisit(visitId) {
    completingVisitId = visitId;
    selectedSentiment = null;
    document.querySelectorAll('.sentiment-btn').forEach(b => b.classList.remove('selected'));
    document.getElementById('f-complete-file').value = '';
    document.getElementById('f-complete-note').value = '';
    showModal('sentiment-modal');
}

function selectSentiment(btn) {
    document.querySelectorAll('.sentiment-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedSentiment = btn.dataset.sentiment;
}

async function submitCompletion() {
    if (!completingVisitId || !selectedSentiment) return alert('느낌을 선택하세요');

    // 1. Complete visit with sentiment
    await api('PUT', `/api/visit/visits/${completingVisitId}`, { status: 'completed', summary: selectedSentiment });

    // 2. Upload files if any
    const fileInput = document.getElementById('f-complete-file');
    if (fileInput.files.length && currentCompanyId) {
        for (const file of fileInput.files) {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('visit_id', completingVisitId);
            await api('POST', `/api/visit/materials/${currentCompanyId}`, fd);
        }
    }

    // 3. Save text note if any
    const note = document.getElementById('f-complete-note').value;
    if (note.trim() && currentCompanyId) {
        await api('POST', `/api/visit/materials/${currentCompanyId}/text`, {
            title: `탐방 메모 (${selectedSentiment})`,
            text_content: note,
            visit_id: completingVisitId,
        });
    }

    completingVisitId = null;
    selectedSentiment = null;
    hideModal('sentiment-modal');
    await loadVisits();
    await loadUpcoming();
    await loadYearlyStats();
    // Refresh materials if tab is active
    if (document.getElementById('tab-materials').style.display !== 'none') {
        await loadMaterials();
    }
}

async function deleteVisit(visitId) {
    if (!confirm('이 일정을 삭제하시겠습니까?')) return;
    await api('DELETE', `/api/visit/visits/${visitId}`);
    await loadVisits();
    await loadUpcoming();
    await loadStockChart();
}

// --- Materials (탐방 결과) ---
async function loadMaterials() {
    if (!currentCompanyId) return;
    const materials = await api('GET', `/api/visit/companies/${currentCompanyId}/materials`);
    const el = document.getElementById('materials-list');
    if (!materials.length) {
        el.innerHTML = '<p class="empty-msg">등록된 탐방 결과가 없습니다</p>';
        return;
    }
    el.innerHTML = materials.map(m => {
        const isText = !!m.text_content;
        const isImage = m.mime_type && m.mime_type.startsWith('image/');
        const isPdf = m.mime_type && m.mime_type.includes('pdf');
        let preview = '';
        if (isText) {
            preview = `<div class="material-preview text-preview">${escapeHtml(m.text_content)}</div>`;
        } else if (isImage) {
            preview = `<div class="material-preview"><img src="/api/visit/materials/${m.id}/download?inline=true" alt="${m.filename}" style="max-width:100%;max-height:400px;border-radius:6px;"></div>`;
        } else if (isPdf) {
            preview = `<div class="material-preview"><iframe src="/api/visit/materials/${m.id}/download?inline=true" style="width:100%;height:500px;border:1px solid var(--border);border-radius:6px;"></iframe></div>`;
        }
        return `
            <div class="material-card">
                <div class="material-header">
                    <div>
                        <span class="file-icon">${isText ? '📝' : getFileIcon(m.mime_type)}</span>
                        ${isText ? `<strong>${m.filename}</strong>` : `<a href="/api/visit/materials/${m.id}/download" class="file-name">${m.filename}</a>`}
                        ${m.file_size ? `<span class="file-size">${fmtSize(m.file_size)}</span>` : ''}
                        <span class="file-size">${m.uploaded_at ? m.uploaded_at.slice(0,10) : ''}</span>
                        ${m.description && !isText ? `<span class="file-size">${m.description}</span>` : ''}
                    </div>
                    <button class="btn btn-danger" onclick="deleteMaterial(${m.id})">삭제</button>
                </div>
                ${preview}
            </div>
        `;
    }).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getFileIcon(mime) {
    if (!mime) return '📄';
    if (mime.includes('pdf')) return '📕';
    if (mime.includes('image')) return '🖼';
    if (mime.includes('excel') || mime.includes('spreadsheet')) return '📊';
    if (mime.includes('word') || mime.includes('document')) return '📝';
    if (mime.includes('presentation') || mime.includes('powerpoint')) return '📑';
    return '📄';
}

async function uploadMaterial() {
    const fileInput = document.getElementById('f-material-file');
    if (!fileInput.files.length || !currentCompanyId) return alert('파일을 선택하세요');
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    const desc = document.getElementById('f-material-desc').value.trim();
    if (desc) fd.append('description', desc);
    await api('POST', `/api/visit/materials/${currentCompanyId}`, fd);
    hideModal('material-modal');
    fileInput.value = '';
    document.getElementById('f-material-desc').value = '';
    await loadMaterials();
}

async function saveTextNote() {
    if (!currentCompanyId) return;
    const content = document.getElementById('f-textnote-content').value;
    if (!content.trim()) return alert('내용을 입력하세요');
    const title = document.getElementById('f-textnote-title').value.trim() || null;
    await api('POST', `/api/visit/materials/${currentCompanyId}/text`, { title, text_content: content });
    hideModal('textnote-modal');
    document.getElementById('f-textnote-title').value = '';
    document.getElementById('f-textnote-content').value = '';
    await loadMaterials();
}

async function deleteMaterial(id) {
    if (!confirm('삭제하시겠습니까?')) return;
    await api('DELETE', `/api/visit/materials/${id}`);
    await loadMaterials();
}

// --- Events ---
async function loadEvents() {
    if (!currentCompanyId) return;
    const events = await api('GET', `/api/visit/companies/${currentCompanyId}/events`);
    const el = document.getElementById('events-list');
    if (!events.length) {
        el.innerHTML = '<p class="empty-msg">등록된 이슈/모멘텀이 없습니다</p>';
        return;
    }
    const typeLabels = { issue: '이슈', momentum: '모멘텀', followup: '팔로업' };
    el.innerHTML = events.map(e => `
        <div class="visit-card" style="border-left-color:${eventColor(e.event_type)};">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <div>
                    <span class="badge badge-${e.event_type}">${typeLabels[e.event_type] || e.event_type}</span>
                    <strong>${e.event_date}</strong> ${e.title}
                </div>
                <button class="btn btn-danger" onclick="deleteEvent(${e.id})">삭제</button>
            </div>
            ${e.description ? `<div style="font-size:0.85rem;color:var(--text-muted);">${e.description}</div>` : ''}
            ${e.alarm_date ? `<div style="font-size:0.8rem;color:var(--primary);margin-top:4px;">알람: ${e.alarm_date}</div>` : ''}
        </div>
    `).join('');
}

function eventColor(type) {
    return { issue: '#ef4444', momentum: '#10b981', followup: '#f59e0b', visit: '#2563eb' }[type] || '#64748b';
}

async function addEvent() {
    const date = document.getElementById('f-event-date').value;
    const title = document.getElementById('f-event-title').value.trim();
    if (!date || !title || !currentCompanyId) return alert('날짜와 제목을 입력하세요');
    await api('POST', '/api/visit/events', {
        company_id: currentCompanyId,
        event_date: date,
        event_type: document.getElementById('f-event-type').value,
        title,
        description: document.getElementById('f-event-desc').value.trim() || null,
        alarm_date: document.getElementById('f-event-alarm').value || null,
    });
    hideModal('event-modal');
    document.getElementById('f-event-date').value = '';
    document.getElementById('f-event-title').value = '';
    document.getElementById('f-event-desc').value = '';
    document.getElementById('f-event-alarm').value = '';
    await loadEvents();
    await loadAllEvents();
    await loadStockChart();
}

async function deleteEvent(id) {
    if (!confirm('이 이벤트를 삭제하시겠습니까?')) return;
    await api('DELETE', `/api/visit/events/${id}`);
    await loadEvents();
    await loadAllEvents();
    await loadStockChart();
}

// --- Reports ---
async function loadReports() {
    if (!currentCompanyId) return;
    const reports = await api('GET', `/api/visit/companies/${currentCompanyId}/reports`);
    const el = document.getElementById('reports-list');
    if (!reports.length) {
        el.innerHTML = '<p class="empty-msg">등록된 리포트가 없습니다</p>';
        return;
    }
    el.innerHTML = reports.map(r => `
        <div class="visit-card" style="border-left-color:#8b5cf6;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div>
                    <strong>${r.report_date}</strong>
                    ${r.source ? `<span style="color:var(--text-muted);font-size:0.85rem;"> · ${r.source}</span>` : ''}
                    ${r.rating ? `<span class="badge" style="background:${ratingColor(r.rating)};color:white;">${r.rating}</span>` : ''}
                </div>
                <button class="btn btn-danger" onclick="deleteReport(${r.id})">삭제</button>
            </div>
            ${r.title ? `<div style="font-weight:600;margin-bottom:4px;">${r.title}</div>` : ''}
            ${r.target_price ? `<div style="font-size:0.9rem;color:var(--primary);">목표주가: <strong>${num(r.target_price)}원</strong></div>` : ''}
            ${r.summary ? `<div style="font-size:0.85rem;color:var(--text-muted);margin-top:6px;white-space:pre-wrap;">${r.summary}</div>` : ''}
            ${r.original_filename ? `<div style="margin-top:6px;"><a href="/api/visit/reports/${r.id}/download" style="font-size:0.85rem;">📕 ${r.original_filename}</a></div>` : ''}
        </div>
    `).join('');
}

function ratingColor(r) {
    return { Buy: '#10b981', Hold: '#f59e0b', Sell: '#ef4444' }[r] || '#64748b';
}

async function uploadReport() {
    const date = document.getElementById('f-report-date').value;
    if (!date || !currentCompanyId) return alert('리포트 날짜를 선택하세요');
    const fd = new FormData();
    fd.append('report_date', date);
    const source = document.getElementById('f-report-source').value.trim();
    if (source) fd.append('source', source);
    const title = document.getElementById('f-report-title').value.trim();
    if (title) fd.append('title', title);
    const target = document.getElementById('f-report-target').value;
    if (target) fd.append('target_price', target);
    const rating = document.getElementById('f-report-rating').value;
    if (rating) fd.append('rating', rating);
    const summary = document.getElementById('f-report-summary').value.trim();
    if (summary) fd.append('summary', summary);
    const fileInput = document.getElementById('f-report-file');
    if (fileInput.files.length) fd.append('file', fileInput.files[0]);
    await api('POST', `/api/visit/reports/${currentCompanyId}`, fd);
    hideModal('report-modal');
    // Clear fields
    ['f-report-date','f-report-source','f-report-title','f-report-target','f-report-summary'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('f-report-rating').value = '';
    document.getElementById('f-report-file').value = '';
    await loadReports();
    await loadStockChart();
}

async function deleteReport(id) {
    if (!confirm('이 리포트를 삭제하시겠습니까?')) return;
    await api('DELETE', `/api/visit/reports/${id}`);
    await loadReports();
    await loadStockChart();
}

// --- Consensus ---
async function loadConsensus() {
    if (!currentCompanyId) return;
    const data = await api('GET', `/api/visit/consensus/${currentCompanyId}`);
    const el = document.getElementById('consensus-table-wrap');
    if (!data.length) {
        el.innerHTML = '<p class="empty-msg">컨센서스 데이터가 없습니다. "네이버에서 가져오기" 또는 "수동 입력"을 사용하세요.</p>';
        return;
    }

    // Group by period, sort
    const annual = data.filter(d => d.period_type === 'annual').sort((a,b) => a.period.localeCompare(b.period));
    const quarterly = data.filter(d => d.period_type === 'quarterly').sort((a,b) => a.period.localeCompare(b.period));
    const periods = [...annual, ...quarterly];

    if (!periods.length) {
        el.innerHTML = '<p class="empty-msg">데이터 없음</p>';
        return;
    }

    const rows = [
        { label: '매출액', key: 'revenue', unit: '억원' },
        { label: '영업이익', key: 'operating_profit', unit: '억원' },
        { label: '순이익', key: 'net_income', unit: '억원' },
        { label: 'EPS', key: 'eps', unit: '원' },
        { label: 'PER', key: 'per', unit: '배' },
    ];

    let html = '<table class="consensus-table"><thead><tr><th></th>';
    periods.forEach(p => {
        const label = p.period + (p.is_estimate ? '(E)' : '(A)');
        html += `<th>${label}</th>`;
    });
    html += '</tr></thead><tbody>';

    rows.forEach(row => {
        html += `<tr><td>${row.label} <span class="cons-unit">(${row.unit})</span></td>`;
        periods.forEach(p => {
            const val = p[row.key];
            const isEst = p.is_estimate ? ' estimate' : '';
            if (val == null) {
                html += `<td class="${isEst}">-</td>`;
            } else {
                const rounded = Math.round(val * 10) / 10;
                const isNeg = rounded < 0;
                const display = isNeg ? `(${Math.abs(rounded).toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})})` : rounded.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
                html += `<td class="${isEst}${isNeg ? ' negative' : ''}">${display}</td>`;
            }
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    el.innerHTML = html;
}

async function fetchConsensus() {
    if (!currentCompanyId) return;
    try {
        const result = await api('POST', `/api/visit/consensus/${currentCompanyId}/fetch`);
        alert(`${result.fetched}건의 컨센서스 데이터를 가져왔습니다.`);
        await loadConsensus();
    } catch (e) {
        alert('컨센서스 가져오기 실패: ' + e.message);
    }
}

async function addConsensus() {
    if (!currentCompanyId) return;
    const period = document.getElementById('f-cons-period').value.trim();
    if (!period) return alert('기간을 입력하세요');

    const body = {
        period_type: document.getElementById('f-cons-type').value,
        period,
        is_estimate: parseInt(document.getElementById('f-cons-estimate').value),
    };
    const numFields = [['f-cons-revenue','revenue'],['f-cons-op','operating_profit'],['f-cons-net','net_income'],['f-cons-eps','eps'],['f-cons-per','per']];
    numFields.forEach(([id, key]) => {
        const v = document.getElementById(id).value;
        if (v) body[key] = parseFloat(v);
    });

    await api('POST', `/api/visit/consensus/${currentCompanyId}`, body);
    hideModal('consensus-modal');
    ['f-cons-period','f-cons-revenue','f-cons-op','f-cons-net','f-cons-eps','f-cons-per'].forEach(id => document.getElementById(id).value = '');
    await loadConsensus();
}

// --- Stock Chart with Annotations ---
async function loadStockChart() {
    if (!currentCompanyId) return;
    const chartSection = document.getElementById('chart-section');

    let company;
    try {
        company = await api('GET', `/api/visit/companies/${currentCompanyId}`);
    } catch { return; }

    if (!company.stock_code) {
        chartSection.style.display = 'none';
        return;
    }

    // Fetch data in parallel
    const [stockData, visits, events, reports] = await Promise.all([
        api('GET', `/api/visit/stock/${currentCompanyId}`).catch(() => []),
        api('GET', `/api/visit/companies/${currentCompanyId}/visits`).catch(() => []),
        api('GET', `/api/visit/companies/${currentCompanyId}/events`).catch(() => []),
        api('GET', `/api/visit/companies/${currentCompanyId}/reports`).catch(() => []),
    ]);

    if (!stockData.length) {
        chartSection.style.display = 'none';
        return;
    }
    chartSection.style.display = '';

    // Compute visit returns and update visit cards
    computeVisitReturns(stockData, visits);
    if (document.getElementById('tab-visits').style.display !== 'none') {
        renderVisitCards();
    }

    const labels = stockData.map(d => fmtDate(d.date));
    const prices = stockData.map(d => d.close);
    const volumes = stockData.map(d => d.volume);

    // Build annotations
    const annotations = {};
    const labelDates = new Set(labels);

    // Helper: find closest label index for a date
    function dateToLabel(dateStr) {
        const d = dateStr.replace(/-/g, '');
        return `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`;
    }

    // Visit annotations (blue)
    visits.filter(v => v.status !== 'cancelled').forEach((v, i) => {
        const lbl = v.visit_date;
        annotations['visit_' + i] = {
            type: 'line', xMin: lbl, xMax: lbl,
            borderColor: '#2563eb', borderWidth: 2, borderDash: [6, 3],
            label: { display: true, content: '탐방' + (v.purpose ? ': ' + v.purpose.slice(0, 12) : ''), position: 'start', backgroundColor: 'rgba(37,99,235,0.85)', color: 'white', font: { size: 10 } },
        };
    });

    // Event annotations
    const eventStyles = {
        issue: { color: '#ef4444', label: '이슈' },
        momentum: { color: '#10b981', label: '모멘텀' },
        followup: { color: '#f59e0b', label: '팔로업' },
    };
    events.forEach((e, i) => {
        const style = eventStyles[e.event_type] || { color: '#64748b', label: e.event_type };
        annotations['event_' + i] = {
            type: 'line', xMin: e.event_date, xMax: e.event_date,
            borderColor: style.color, borderWidth: 2,
            borderDash: e.event_type === 'followup' ? [4, 4] : [],
            label: { display: true, content: e.title.slice(0, 15), position: i % 2 === 0 ? 'center' : 'end', backgroundColor: style.color + 'dd', color: 'white', font: { size: 10 } },
        };
    });

    // Target price (latest report with target)
    const withTarget = reports.filter(r => r.target_price).sort((a, b) => b.report_date.localeCompare(a.report_date));
    if (withTarget.length) {
        const latest = withTarget[0];
        annotations['target'] = {
            type: 'line', yMin: latest.target_price, yMax: latest.target_price,
            borderColor: '#8b5cf6', borderWidth: 1.5, borderDash: [10, 5],
            label: { display: true, content: `목표가: ${num(latest.target_price)}원` + (latest.source ? ` (${latest.source})` : ''), position: 'end', backgroundColor: 'rgba(139,92,246,0.85)', color: 'white', font: { size: 10 } },
        };
    }

    // Render chart
    if (stockChart) stockChart.destroy();
    const ctx = document.getElementById('chart-stock').getContext('2d');
    stockChart = new Chart(ctx, {
        data: {
            labels,
            datasets: [
                { type: 'line', label: '종가 (원)', data: prices, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.05)', fill: true, yAxisID: 'y', tension: 0.1, pointRadius: 0, borderWidth: 2 },
                { type: 'bar', label: '거래량', data: volumes, backgroundColor: 'rgba(100,116,139,0.25)', yAxisID: 'y1' },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: { position: 'left', title: { display: true, text: '주가 (원)' }, ticks: { callback: v => num(v) } },
                y1: { position: 'right', title: { display: true, text: '거래량' }, grid: { drawOnChartArea: false }, ticks: { callback: v => num(v) } },
                x: { ticks: { maxTicksLimit: 12, maxRotation: 45 } },
            },
            plugins: {
                annotation: { annotations },
                legend: { display: true, position: 'top' },
            },
        },
    });
}
