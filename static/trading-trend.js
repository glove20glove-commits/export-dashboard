let records = [];
let selectedStock = { code: "", name: "" };
let stockSearchTimer = null;

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

function todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function fmtNum(v, digits = 0) {
    const n = Number(v || 0);
    return n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

function bindEvents() {
    document.getElementById('btn-add').addEventListener('click', onAdd);
    document.getElementById('btn-reset').addEventListener('click', resetForm);
    document.getElementById('btn-search-stock').addEventListener('click', searchStocks);
    document.getElementById('btn-search').addEventListener('click', loadRecords);
    document.getElementById('btn-sync').addEventListener('click', syncFromDart);
    document.getElementById('q-days').addEventListener('change', loadRecords);
    document.getElementById('f-company').addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            await searchStocks();
        }
    });
    document.getElementById('f-company').addEventListener('input', () => {
        const value = document.getElementById('f-company').value.trim();
        if (!value || value !== selectedStock.name) {
            clearSelectedStock();
        }
        scheduleStockSearch();
        updateResolveHint();
    });
    document.getElementById('f-code').addEventListener('input', () => {
        if (!document.getElementById('f-code').value.trim()) {
            clearSelectedStock();
        }
        updateResolveHint();
    });
}

function clearSelectedStock() {
    if (selectedStock.code && document.getElementById('f-code').value.trim() === selectedStock.code) {
        document.getElementById('f-code').value = '';
    }
    selectedStock = { code: "", name: "" };
    document.getElementById('f-stock-selected').textContent = '선택: -';
    document.getElementById('f-stock-suggest').innerHTML = '';
    updateResolveHint();
}

function resetForm() {
    document.getElementById('f-date').value = todayISO();
    document.getElementById('f-company').value = '';
    document.getElementById('f-code').value = '';
    document.getElementById('f-party').value = '';
    document.getElementById('f-relation').value = '';
    document.getElementById('f-shares').value = '0';
    document.getElementById('f-ratio').value = '0';
    document.getElementById('f-price').value = '0';
    document.getElementById('f-amount').value = '0';
    document.getElementById('f-source-title').value = '';
    document.getElementById('f-source-url').value = '';
    document.getElementById('f-note').value = '';
    clearSelectedStock();
}

function updateResolveHint(text) {
    const el = document.getElementById('f-stock-resolve');
    if (!el) return;
    if (text) {
        el.textContent = text;
        return;
    }
    const companyName = document.getElementById('f-company').value.trim();
    const manualCode = document.getElementById('f-code').value.trim();
    if (manualCode) {
        el.textContent = `저장 전 종목코드 자동확정: 직접 입력 ${manualCode}`;
    } else if (selectedStock.code) {
        el.textContent = `저장 전 종목코드 자동확정: ${selectedStock.name} (${selectedStock.code})`;
    } else if (companyName) {
        el.textContent = `저장 전 종목코드 자동확정: ${companyName} 검색 대기`;
    } else {
        el.textContent = '저장 전 종목코드 자동확정: 대기';
    }
}

function setSelectedStock(code, name) {
    selectedStock = {
        code: String(code || '').padStart(6, '0'),
        name: name || '',
    };
    document.getElementById('f-company').value = selectedStock.name;
    document.getElementById('f-code').value = selectedStock.code;
    document.getElementById('f-stock-selected').textContent = `선택: ${selectedStock.name} (${selectedStock.code})`;
    updateResolveHint();
}

async function applyStockFilter(code, name) {
    document.getElementById('q-keyword').value = name || '';
    document.getElementById('q-code').value = code ? String(code).padStart(6, '0') : '';
    await loadRecords();
}

function renderStockSuggestions(items) {
    const box = document.getElementById('f-stock-suggest');
    if (!items.length) {
        box.innerHTML = '<span class="hint">검색 결과가 없습니다.</span>';
        return;
    }
    box.innerHTML = items.slice(0, 15).map(it => `
        <button class="stock-chip" type="button" onclick="pickTradingTrendStock('${it.code}','${(it.name || '').replace(/'/g, "\\'")}')">
            ${esc(it.name)} <span class="mono">${esc(it.code)}</span>${it.market ? ` <span class="hint">(${esc(it.market)})</span>` : ''}
        </button>
    `).join('');
}

async function searchStocks() {
    const q = document.getElementById('f-company').value.trim();
    const box = document.getElementById('f-stock-suggest');
    if (!q) {
        box.innerHTML = '<span class="hint">종목명을 입력하고 검색하면 후보가 표시됩니다.</span>';
        updateResolveHint();
        return;
    }
    try {
        updateResolveHint(`${q} 검색 중...`);
        const results = await api('GET', `/api/stock-monitor/search?name=${encodeURIComponent(q)}`);
        renderStockSuggestions(results || []);
        const items = Array.isArray(results) ? results : [];
        const exact = items.find(it => String(it.name || '').trim() === q);
        if (exact && exact.code) {
            updateResolveHint(`저장 전 종목코드 자동확정: ${exact.name} (${String(exact.code).padStart(6, '0')})`);
            if (items.length === 1) {
                setSelectedStock(exact.code, exact.name || q);
                await applyStockFilter(exact.code, exact.name || q);
                box.innerHTML = '';
            }
        } else if (items.length) {
            const first = items[0];
            updateResolveHint(`저장 전 종목코드 자동확정 후보: ${first.name} (${String(first.code || '').padStart(6, '0')})`);
        } else {
            updateResolveHint(`저장 전 종목코드 자동확정: ${q} 검색 결과 없음`);
        }
    } catch (e) {
        box.innerHTML = `<span class="hint">검색 실패: ${esc(e.message)}</span>`;
        updateResolveHint(`저장 전 종목코드 자동확정 실패: ${e.message}`);
    }
}

function scheduleStockSearch() {
    if (stockSearchTimer) {
        clearTimeout(stockSearchTimer);
    }
    const q = document.getElementById('f-company').value.trim();
    if (!q) {
        document.getElementById('f-stock-suggest').innerHTML = '';
        return;
    }
    stockSearchTimer = setTimeout(() => {
        searchStocks().catch(() => {});
    }, 250);
}

async function resolveStockCodeIfNeeded() {
    const companyName = document.getElementById('f-company').value.trim();
    const manualCode = document.getElementById('f-code').value.trim();
    if (manualCode) {
        return manualCode;
    }
    if (selectedStock.code) {
        return selectedStock.code;
    }
    if (!companyName) {
        return '';
    }
    const results = await api('GET', `/api/stock-monitor/search?name=${encodeURIComponent(companyName)}`);
    const items = Array.isArray(results) ? results : [];
    if (!items.length) {
        updateResolveHint(`저장 전 종목코드 자동확정: ${companyName} 검색 결과 없음`);
        return '';
    }
    const exact = items.find(it => String(it.name || '').trim() === companyName) || items[0];
    if (exact && exact.code) {
        setSelectedStock(exact.code, exact.name || companyName);
        return String(exact.code).padStart(6, '0');
    }
    return '';
}

async function onAdd() {
    let resolvedCode = '';
    try {
        updateResolveHint('저장 전 종목코드 자동확정 중...');
        resolvedCode = await resolveStockCodeIfNeeded();
    } catch (e) {
        alert(`종목 검색 실패: ${e.message}`);
        return;
    }

    const payload = {
        trade_date: document.getElementById('f-date').value,
        company_name: document.getElementById('f-company').value.trim(),
        stock_code: resolvedCode,
        related_party: document.getElementById('f-party').value.trim(),
        relation_type: document.getElementById('f-relation').value.trim(),
        change_shares: Number(document.getElementById('f-shares').value || 0),
        change_ratio: Number(document.getElementById('f-ratio').value || 0),
        avg_price: Number(document.getElementById('f-price').value || 0),
        amount_krw: Number(document.getElementById('f-amount').value || 0),
        source_title: document.getElementById('f-source-title').value.trim(),
        source_url: document.getElementById('f-source-url').value.trim(),
        note: document.getElementById('f-note').value.trim(),
    };

    if (!payload.trade_date || !payload.company_name || !payload.related_party) {
        alert('공시일, 종목명, 특수관계인은 필수입니다.');
        return;
    }
    if (!payload.stock_code) {
        alert('종목코드를 찾지 못했습니다. 검색 결과에서 종목을 선택하거나 종목코드를 직접 입력해 주세요.');
        updateResolveHint(`저장 전 종목코드 자동확정: ${payload.company_name} 확인 필요`);
        return;
    }

    try {
        await api('POST', '/api/trading-trend/items', payload);
        resetForm();
        await loadRecords();
    } catch (e) {
        alert(`저장 실패: ${e.message}`);
    }
}

async function removeItem(id) {
    if (!confirm('이 기록을 삭제할까요?')) return;
    try {
        await api('DELETE', `/api/trading-trend/items/${id}`);
        await loadRecords();
    } catch (e) {
        alert(`삭제 실패: ${e.message}`);
    }
}

function renderSummary() {
    const cards = document.getElementById('summary-cards');
    const total = records.length;
    const totalAmount = records.reduce((acc, r) => acc + Number(r.amount_krw || 0), 0);
    const totalShares = records.reduce((acc, r) => acc + Number(r.change_shares || 0), 0);
    const uniqueCompanies = new Set(records.map(r => `${r.company_name}|${r.stock_code || ''}`)).size;

    cards.innerHTML = `
        <div class="card"><div class="k">모니터링 건수</div><div class="v">${fmtNum(total)}</div></div>
        <div class="card"><div class="k">종목 수</div><div class="v">${fmtNum(uniqueCompanies)}</div></div>
        <div class="card"><div class="k">총 매수주식수</div><div class="v">${fmtNum(totalShares)}</div></div>
        <div class="card"><div class="k">총 매수금액(원)</div><div class="v">${fmtNum(totalAmount)}</div></div>
    `;
}

function renderTable() {
    const tbody = document.getElementById('tbody');
    if (!records.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="muted" style="text-align:center;padding:30px 8px;">조건에 맞는 데이터가 없습니다.</td></tr>';
        return;
    }

    tbody.innerHTML = records.map(r => {
        const source = r.source_url
            ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_title || '링크')}</a>`
            : esc(r.source_title || '-');

        return `
            <tr>
                <td class="mono">${esc(r.trade_date)}</td>
                <td>
                    <div><strong>${esc(r.company_name)}</strong></div>
                    <div class="mono muted">${esc(r.stock_code || '-')}</div>
                </td>
                <td>
                    <div>${esc(r.related_party)}</div>
                    <div class="muted">${esc(r.relation_type || '-')}</div>
                </td>
                <td class="right">${fmtNum(r.change_shares)}</td>
                <td class="right pos">${Number(r.change_ratio || 0) >= 0 ? '+' : ''}${fmtNum(r.change_ratio, 3)}%p</td>
                <td class="right">${fmtNum(r.amount_krw)}</td>
                <td>${source}</td>
                <td>${esc(r.note || '-')}</td>
                <td><button class="btn btn-secondary" style="padding:4px 8px;" onclick="removeItem(${r.id})">삭제</button></td>
            </tr>
        `;
    }).join('');

}

async function loadRecords() {
    const days = document.getElementById('q-days').value;
    const keyword = document.getElementById('q-keyword').value.trim();
    const code = document.getElementById('q-code').value.trim();
    const params = new URLSearchParams({ days });
    if (keyword) params.set('keyword', keyword);
    if (code) params.set('stock_code', code);

    try {
        records = await api('GET', `/api/trading-trend/items?${params.toString()}`);
    } catch (e) {
        alert(`조회 실패: ${e.message}`);
        records = [];
    }
    renderSummary();
    renderTable();
}

async function syncFromDart() {
    const days = document.getElementById('q-days').value || '30';
    const btn = document.getElementById('btn-sync');
    btn.disabled = true;
    btn.textContent = '동기화 중...';
    try {
        const r = await api('POST', `/api/trading-trend/refresh?days=${encodeURIComponent(days)}`);
        alert(`동기화 완료: 신규 ${r.inserted || 0}건 / 갱신 ${r.updated || 0}건 / 중복 ${r.skipped || 0}건 / 후보 ${r.total || 0}건`);
        await loadRecords();
    } catch (e) {
        alert(`동기화 실패: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'DART 동기화';
    }
}

async function pickTradingTrendStock(code, name) {
    setSelectedStock(code, name);
    document.getElementById('f-stock-suggest').innerHTML = '';
    await applyStockFilter(code, name);
}

document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    resetForm();
    await loadRecords();
});

window.removeItem = removeItem;
window.pickTradingTrendStock = pickTradingTrendStock;
