let currentQuarter = '';
let selectedStockCode = '';
let selectedStockName = '';
let watchlistRows = [];
let currentRow = null;
let allOverviewRows = [];
let currentSortByAll = 'revenue';
let allSelectedStockCode = '';

let watchManageMode = false;
let watchQuery = '';
const WATCH_MATCH_LIMIT = 20;

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

function fmt(v, digits = 0) {
    const n = Number(v || 0);
    return n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

function yoyHtml(v) {
    if (v === null || v === undefined) return '-';
    const cls = Number(v) >= 0 ? 'up' : 'down';
    const sign = Number(v) >= 0 ? '+' : '';
    return `<span class="yoy ${cls}">${sign}${fmt(v, 2)}%</span>`;
}

function toMini(arr, key) {
    return arr.map(r => `${r.quarter_key}: ${fmt(r[key])}`).join('\n');
}

function switchTab(tabName) {
    const isAll = tabName === 'all';
    const isDetail = tabName === 'detail';
    document.getElementById('tab-btn-all').classList.toggle('active', isAll);
    document.getElementById('tab-btn-detail').classList.toggle('active', isDetail);
    document.getElementById('tab-all').classList.toggle('active', isAll);
    document.getElementById('tab-detail').classList.toggle('active', isDetail);
}

function getSelectedIndex() {
    return watchlistRows.findIndex(w => w.stock_code === selectedStockCode);
}

function updateNavButtons() {
    const prevBtn = document.getElementById('btn-prev-stock');
    const nextBtn = document.getElementById('btn-next-stock');
    const idx = getSelectedIndex();
    const hasItems = watchlistRows.length > 0 && idx >= 0;
    prevBtn.disabled = !hasItems || idx === 0;
    nextBtn.disabled = !hasItems || idx >= watchlistRows.length - 1;
}

function renderWatchlist() {
    const el = document.getElementById('watchlist');
    const summaryEl = document.getElementById('watch-summary');
    const query = (watchQuery || '').trim().toLowerCase();
    const filtered = watchlistRows.filter(w =>
        (w.stock_name || '').toLowerCase().includes(query) || (w.stock_code || '').includes(query)
    );
    const selected = watchlistRows.find(w => w.stock_code === selectedStockCode);

    summaryEl.textContent = `등록 ${watchlistRows.length.toLocaleString()}개 · ${watchManageMode ? '관리모드 ON' : '관리모드 OFF'} · 검색어 입력 시 최대 ${WATCH_MATCH_LIMIT}개 표시`;

    if (!watchlistRows.length) {
        el.textContent = '등록된 종목이 없습니다. 종목코드/종목명을 추가하세요.';
        return;
    }

    if (!query) {
        if (!selected) {
            el.textContent = '검색어를 입력해 종목을 찾으세요.';
            return;
        }
        const code = esc(selected.stock_code);
        const name = esc(selected.stock_name);
        const delBtn = watchManageMode
            ? `<button class="btn btn-secondary" style="padding:2px 7px;" onclick="delWatch('${code}')">삭제</button>`
            : '';
        el.innerHTML = `<span style="display:inline-flex;align-items:center;gap:4px;margin:2px 6px 2px 0;">
            <button class="stock-chip active" onclick="openStock('${code}','${name}')"><span class="mono">${code}</span> ${name}</button>
            ${delBtn}
        </span>`;
        return;
    }

    if (!filtered.length) {
        el.textContent = '검색 결과가 없습니다.';
        return;
    }

    const rowsHtml = filtered.slice(0, WATCH_MATCH_LIMIT).map(w => {
        const code = esc(w.stock_code);
        const name = esc(w.stock_name);
        const active = selectedStockCode === w.stock_code ? 'active' : '';
        const delBtn = watchManageMode
            ? `<button class="btn btn-secondary" style="padding:2px 7px;" onclick="delWatch('${code}')">삭제</button>`
            : '';
        return `<span style="display:inline-flex;align-items:center;gap:4px;margin:2px 6px 2px 0;">
            <button class="stock-chip ${active}" onclick="openStock('${code}','${name}')"><span class="mono">${code}</span> ${name}</button>
            ${delBtn}
        </span>`;
    }).join('');
    const moreHint = filtered.length > WATCH_MATCH_LIMIT
        ? `<div class="hint" style="margin-top:6px;">검색 결과 ${filtered.length.toLocaleString()}개 중 ${WATCH_MATCH_LIMIT}개만 표시 중입니다. 검색어를 더 구체화해 주세요.</div>`
        : '';
    el.innerHTML = rowsHtml + moreHint;
}

function renderAllSortState() {
    document.querySelectorAll('.sortable-all').forEach(el => {
        if (el.dataset.sort === currentSortByAll) el.classList.add('active');
        else el.classList.remove('active');
    });
}

function renderAllOverviewTable() {
    const tbody = document.getElementById('tbody-all');
    if (!allOverviewRows.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-secondary);padding:24px;">전종목 데이터가 없습니다.</td></tr>';
        return;
    }

    tbody.innerHTML = allOverviewRows.map(r => {
        const active = allSelectedStockCode === r.stock_code ? 'active' : '';
        return `
            <tr>
                <td><button class="stock-chip stock-chip-all ${active}" onclick="selectAllStock('${esc(r.stock_code)}')"><span class="name">${esc(r.stock_name)}</span><span class="code mono">${esc(r.stock_code)}</span></button></td>
                <td class="right">${fmt(r.revenue)}</td>
                <td class="right">${yoyHtml(r.revenue_yoy)}</td>
                <td class="right">${fmt(r.operating_profit)}</td>
                <td class="right">${yoyHtml(r.operating_profit_yoy)}</td>
                <td class="right">${fmt(r.net_income)}</td>
                <td class="right">${yoyHtml(r.net_income_yoy)}</td>
                <td>
                    <textarea id="reason-all-${r.stock_code}" class="reason-box">${esc(r.reason_text || '')}</textarea>
                    <div style="margin-top:6px;"><button class="btn btn-secondary" style="padding:4px 8px;" onclick="saveReason('${r.stock_code}','all')">저장</button></div>
                </td>
            </tr>
        `;
    }).join('');
}

function selectAllStock(stockCode) {
    allSelectedStockCode = (stockCode || '').padStart(6, '0');
    renderAllOverviewTable();
}

async function loadAllOverview() {
    if (!currentQuarter) {
        allOverviewRows = [];
        renderAllOverviewTable();
        return;
    }
    allOverviewRows = await api('GET', `/api/quarterly-performance/overview?quarter_key=${encodeURIComponent(currentQuarter)}&sort_by=${encodeURIComponent(currentSortByAll)}`);
    if (!allSelectedStockCode && allOverviewRows.length) allSelectedStockCode = allOverviewRows[0].stock_code;
    renderAllSortState();
    renderAllOverviewTable();
}

async function loadWatchlist() {
    watchlistRows = await api('GET', '/api/quarterly-performance/watchlist');
    if (selectedStockCode && !watchlistRows.find(w => w.stock_code === selectedStockCode)) {
        selectedStockCode = '';
        selectedStockName = '';
    }
    if (!selectedStockCode && watchlistRows.length) {
        selectedStockCode = watchlistRows[0].stock_code;
        selectedStockName = watchlistRows[0].stock_name;
    }
    renderWatchlist();
    updateNavButtons();
}

function toggleWatchManageMode() {
    watchManageMode = !watchManageMode;
    const btn = document.getElementById('btn-watch-manage');
    btn.textContent = watchManageMode ? '관리모드 ON' : '관리모드 OFF';
    renderWatchlist();
}

async function delWatch(code) {
    if (!confirm(`${code} 종목을 삭제할까요?`)) return;
    await api('DELETE', `/api/quarterly-performance/watchlist/${code}`);
    await loadWatchlist();
    await loadSelectedStockDetail();
    if (document.getElementById('tab-all').classList.contains('active')) {
        await loadAllOverview();
    }
}

async function addWatch() {
    const code = document.getElementById('w-code').value.trim();
    const name = document.getElementById('w-name').value.trim();
    if (!code || !name) {
        alert('종목코드와 종목명을 입력하세요.');
        return;
    }
    await api('POST', '/api/quarterly-performance/watchlist', { stock_code: code, stock_name: name });
    document.getElementById('w-code').value = '';
    document.getElementById('w-name').value = '';
    await loadWatchlist();
    await loadQuarters();
    await openStock(code.padStart(6, '0'), name);
}

async function refreshData() {
    const btn = document.getElementById('btn-refresh');
    const msg = document.getElementById('sync-msg');
    btn.disabled = true;
    btn.textContent = '동기화 요청 중...';
    msg.textContent = '';
    try {
        const startResp = await fetch('/api/quarterly-performance/refresh/async?auto_reason=true&start=0', { method: 'POST' });
        if (!startResp.ok && startResp.status !== 409) {
            const err = await startResp.json().catch(() => ({}));
            throw new Error(err.detail || `API error: ${startResp.status}`);
        }
        btn.textContent = '동기화 진행 중...';
        if (startResp.status === 409) {
            msg.textContent = '이미 동기화가 실행 중입니다. 진행 상황을 확인합니다...';
        } else {
            msg.textContent = '백그라운드 동기화가 시작되었습니다.';
        }

        let done = false;
        let pollErrors = 0;
        while (!done) {
            await new Promise(r => setTimeout(r, 4000));
            try {
                const st = await api('GET', '/api/quarterly-performance/refresh/status');
                pollErrors = 0;
                done = !st.running;
                if (done) {
                    if (st.error) {
                        msg.textContent = `동기화 실패: ${st.error}`;
                    } else {
                        const up = st.result?.upserted_data || 0;
                        const rs = st.result?.upserted_reasons || 0;
                        msg.textContent = `동기화 완료: 실적 ${up}건, 이유 ${rs}건`;
                    }
                }
            } catch (e) {
                pollErrors += 1;
                msg.textContent = `상태 확인 재시도 중... (${pollErrors})`;
                if (pollErrors >= 5) {
                    throw new Error(`상태 조회 실패: ${e.message}`);
                }
            }
        }

        await loadQuarters();
        await loadSelectedStockDetail();
        if (document.getElementById('tab-all').classList.contains('active')) {
            await loadAllOverview();
        }
    } catch (e) {
        alert(`동기화 실패: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '실적 동기화';
    }
}

async function loadQuarters() {
    const qs = await api('GET', '/api/quarterly-performance/quarters');
    const sel = document.getElementById('quarter-select');
    const selAll = document.getElementById('quarter-select-all');
    sel.innerHTML = qs.map(q => `<option value="${q}">${q}</option>`).join('');
    selAll.innerHTML = qs.map(q => `<option value="${q}">${q}</option>`).join('');
    if (!qs.length) {
        currentQuarter = '';
        currentRow = null;
        allOverviewRows = [];
        renderTable();
        renderAllOverviewTable();
        return;
    }
    if (!currentQuarter || !qs.includes(currentQuarter)) {
        currentQuarter = qs[0];
    }
    sel.value = currentQuarter;
    selAll.value = currentQuarter;
}

async function loadSelectedStockDetail() {
    const selectedLabel = document.getElementById('selected-stock');
    if (!selectedStockCode) {
        selectedLabel.textContent = '선택된 종목이 없습니다.';
        currentRow = null;
        renderTable();
        return;
    }
    if (!currentQuarter) {
        selectedLabel.textContent = '분기 데이터가 없습니다.';
        currentRow = null;
        renderTable();
        return;
    }
    selectedLabel.innerHTML = `선택 종목: <strong>${esc(selectedStockName)}</strong> <span class="mono">${esc(selectedStockCode)}</span>`;
    try {
        currentRow = await api('GET', `/api/quarterly-performance/stock-detail?quarter_key=${encodeURIComponent(currentQuarter)}&stock_code=${encodeURIComponent(selectedStockCode)}`);
    } catch (e) {
        currentRow = null;
    }
    renderTable();
}

async function openStock(code, name) {
    selectedStockCode = (code || '').padStart(6, '0');
    selectedStockName = name || selectedStockCode;
    renderWatchlist();
    updateNavButtons();
    switchTab('detail');
    await loadSelectedStockDetail();
}

async function moveStock(step) {
    const idx = getSelectedIndex();
    if (idx < 0) return;
    const target = watchlistRows[idx + step];
    if (!target) return;
    await openStock(target.stock_code, target.stock_name);
}

async function saveReason(code, scope = 'detail') {
    const taId = scope === 'all' ? `reason-all-${code}` : `reason-${code}`;
    let ta = document.getElementById(taId);
    if (!ta && scope === 'all') ta = document.getElementById(`reason-all-m-${code}`);
    if (!ta && scope === 'detail') ta = document.getElementById(`reason-m-${code}`);
    const reason = ta ? ta.value.trim() : '';
    await api('PUT', '/api/quarterly-performance/reason', {
        stock_code: code,
        quarter_key: currentQuarter,
        reason_text: reason,
    });
    if (selectedStockCode === code) {
        await loadSelectedStockDetail();
    }
    if (scope === 'all' || document.getElementById('tab-all').classList.contains('active')) {
        await loadAllOverview();
    }
}

function renderTable() {
    const tbody = document.getElementById('tbody');
    if (!currentRow) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--text-secondary);padding:28px;">종목을 클릭하면 상세 데이터가 표시됩니다.</td></tr>';
        return;
    }

    const r = currentRow;
    const rev4 = toMini(r.recent_4q || [], 'revenue');
    const op4 = toMini(r.recent_4q || [], 'operating_profit');
    const ni4 = toMini(r.recent_4q || [], 'net_income');

    tbody.innerHTML = `
        <tr>
            <td><strong>${esc(r.stock_name)}</strong><br><span class="mono hint">${esc(r.stock_code)}</span></td>
            <td class="mini">${esc(rev4)}</td>
            <td class="mini">${esc(op4)}</td>
            <td class="mini">${esc(ni4)}</td>
            <td class="right">${fmt(r.revenue)}</td>
            <td class="right">${yoyHtml(r.revenue_yoy)}</td>
            <td class="right">${fmt(r.operating_profit)}</td>
            <td class="right">${yoyHtml(r.operating_profit_yoy)}</td>
            <td class="right">${fmt(r.net_income)}</td>
            <td class="right">${yoyHtml(r.net_income_yoy)}</td>
            <td>
                <textarea id="reason-${r.stock_code}" class="reason-box">${esc(r.reason_text || '')}</textarea>
                <div style="margin-top:6px;"><button class="btn btn-secondary" style="padding:4px 8px;" onclick="saveReason('${r.stock_code}','detail')">저장</button></div>
            </td>
        </tr>
    `;
}

function bindEvents() {
    document.getElementById('btn-add-watch').addEventListener('click', addWatch);
    document.getElementById('btn-watch-manage').addEventListener('click', toggleWatchManageMode);
    document.getElementById('btn-refresh').addEventListener('click', refreshData);
    document.getElementById('watch-search').addEventListener('input', (e) => {
        watchQuery = e.target.value || '';
        renderWatchlist();
    });
    document.getElementById('quarter-select').addEventListener('change', async (e) => {
        currentQuarter = e.target.value;
        document.getElementById('quarter-select-all').value = currentQuarter;
        await loadSelectedStockDetail();
    });
    document.getElementById('quarter-select-all').addEventListener('change', async (e) => {
        currentQuarter = e.target.value;
        document.getElementById('quarter-select').value = currentQuarter;
        await loadAllOverview();
    });
    document.getElementById('tab-btn-all').addEventListener('click', async () => {
        switchTab('all');
        await loadAllOverview();
    });
    document.getElementById('tab-btn-detail').addEventListener('click', async () => {
        switchTab('detail');
        await loadSelectedStockDetail();
    });
    document.getElementById('btn-prev-stock').addEventListener('click', async () => {
        await moveStock(-1);
    });
    document.getElementById('btn-next-stock').addEventListener('click', async () => {
        await moveStock(1);
    });
    document.querySelectorAll('.sortable-all').forEach(el => {
        el.addEventListener('click', async () => {
            currentSortByAll = el.dataset.sort;
            await loadAllOverview();
        });
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    await loadWatchlist();
    await loadQuarters();
    await loadAllOverview();
    await loadSelectedStockDetail();
    updateNavButtons();
});

window.delWatch = delWatch;
window.saveReason = saveReason;
window.openStock = openStock;
window.selectAllStock = selectAllStock;
