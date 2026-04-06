const API = '';

const state = {
    selected: null,
};
let unlockChart = null;

const els = {
    stockQuery: document.getElementById('stock-query'),
    btnSearch: document.getElementById('btn-search'),
    btnRefresh: document.getElementById('btn-refresh'),
    btnSyncDart: document.getElementById('btn-sync-dart'),
    selectedStock: document.getElementById('selected-stock'),
    msg: document.getElementById('msg'),
    suggest: document.getElementById('stock-suggest'),
    sumTotal: document.getElementById('sum-total'),
    sumExercised: document.getElementById('sum-exercised'),
    sumRemaining: document.getElementById('sum-remaining'),
    sumUnlocked: document.getElementById('sum-unlocked'),
    summaryExtra: document.getElementById('summary-extra'),
    tbodyLockups: document.getElementById('tbody-lockups'),
    tbodyEvents: document.getElementById('tbody-events'),
    tbodyKisMilestones: document.getElementById('tbody-kis-milestones'),
    unlockBadges: document.getElementById('unlock-badges'),
    inHolder: document.getElementById('in-holder'),
    inHolderType: document.getElementById('in-holder-type'),
    inUnlock: document.getElementById('in-unlock'),
    inQty: document.getElementById('in-qty'),
    inNote: document.getElementById('in-note'),
    btnAddLockup: document.getElementById('btn-add-lockup'),
    inExDate: document.getElementById('in-ex-date'),
    inExQty: document.getElementById('in-ex-qty'),
    inExNote: document.getElementById('in-ex-note'),
    btnAddEx: document.getElementById('btn-add-ex'),
    unlockChart: document.getElementById('unlock-chart'),
};

function fmtNum(v) {
    const n = Number(v || 0);
    return Number.isFinite(n) ? n.toLocaleString('ko-KR') : '-';
}

function fmtPct(v) {
    const n = Number(v);
    return Number.isFinite(n) ? `${n.toFixed(2)}%` : '-';
}

async function api(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(API + path, opts);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `요청 실패 (${resp.status})`);
    return data;
}

function setMsg(msg, isErr = false) {
    els.msg.textContent = msg || '';
    els.msg.style.color = isErr ? '#dc2626' : '';
}

function setSelected(stock) {
    state.selected = stock;
    if (!stock) {
        els.selectedStock.textContent = '선택: -';
        return;
    }
    const name = stock.stock_name || stock.name || '-';
    const code = stock.stock_code || stock.code || '-';
    els.selectedStock.textContent = `선택: ${name} (${code})`;
}

function renderSuggest(items) {
    if (!items || !items.length) {
        els.suggest.innerHTML = '<span class="hint">검색 결과가 없습니다.</span>';
        return;
    }
    els.suggest.innerHTML = items.map(it => {
        const code = it.stock_code || it.code || '';
        const name = it.stock_name || it.name || '';
        return `<button class="btn btn-secondary btn-suggest" data-code="${code}" data-name="${name}" style="margin-right:6px;margin-top:6px;">${name} (${code})</button>`;
    }).join('');
    document.querySelectorAll('.btn-suggest').forEach(btn => {
        btn.addEventListener('click', () => {
            setSelected({ stock_code: btn.dataset.code, stock_name: btn.dataset.name });
            loadStatus();
        });
    });
}

async function searchStock() {
    const q = (els.stockQuery.value || '').trim();
    if (!q) {
        setMsg('종목명을 입력해 주세요.', true);
        return;
    }
    setMsg('검색 중...');
    try {
        const items = await api('GET', `/api/overhang/search?name=${encodeURIComponent(q)}`);
        renderSuggest(items || []);
        setMsg('');
    } catch (e) {
        setMsg(e.message, true);
    }
}

function renderSummary(summary) {
    els.sumTotal.textContent = fmtNum(summary.ipo_overhang_total_qty);
    els.sumExercised.textContent = fmtNum(summary.exercised_to_date_qty_effective || summary.exercised_to_date_qty);
    els.sumRemaining.textContent = fmtNum(summary.remaining_overhang_qty_effective || summary.remaining_overhang_qty);
    els.sumUnlocked.textContent = fmtNum(summary.currently_unlocked_remaining_qty_effective || summary.currently_unlocked_remaining_qty);
    if (summary.is_recent_ipo_under_6m && Number(summary.kis_assumed_exercise_qty || 0) > 0) {
        const listingDate = summary.listing_date || '-';
        els.summaryExtra.textContent =
            `상장 6개월 미만으로 판단되어 KIS 기관 누적 순매도 ${fmtNum(summary.kis_institution_cum_net_sell_qty)}주를 추정 행사 반영 수량으로 포함했습니다. (상장일 ${listingDate})`;
    } else if (summary.is_recent_ipo_under_6m) {
        const listingDate = summary.listing_date || '-';
        els.summaryExtra.textContent = `상장 6개월 미만 종목입니다. KIS 기관 누적 순매도 추정치를 함께 점검합니다. (상장일 ${listingDate})`;
    } else {
        els.summaryExtra.textContent = '';
    }
}

function renderLockups(rows, totalQty) {
    if (!rows || !rows.length) {
        els.tbodyLockups.innerHTML = '<tr><td colspan="11" class="hint">등록된 락업 데이터가 없습니다.</td></tr>';
        return;
    }
    const total = Number(totalQty || 0);
    let cum = 0;
    els.tbodyLockups.innerHTML = rows.map(r => {
        const qty = Number(r.quantity || 0);
        cum += qty;
        const rowPct = total > 0 ? (qty / total) * 100 : NaN;
        const cumPct = total > 0 ? (cum / total) * 100 : NaN;
        return `
        <tr>
            <td>${r.holder_name || '-'}</td>
            <td>${r.holder_type || '-'}</td>
            <td>${r.lockup_end_date || '-'}</td>
            <td class="right">${fmtNum(qty)}</td>
            <td class="right">${fmtPct(rowPct)}</td>
            <td class="right">${fmtPct(cumPct)}</td>
            <td class="right">${fmtNum(r.consumed_by_exercise)}</td>
            <td class="right">${fmtNum(r.remaining_qty)}</td>
            <td class="right">${fmtNum(r.available_now_qty)}</td>
            <td class="right">${fmtNum(r.upcoming_qty)}</td>
            <td><button class="btn btn-secondary btn-del-lockup" data-id="${r.id}">삭제</button></td>
        </tr>
    `;
    }).join('');
    document.querySelectorAll('.btn-del-lockup').forEach(btn => {
        btn.addEventListener('click', async () => {
            try {
                await api('DELETE', `/api/overhang/lockups/${btn.dataset.id}`);
                await loadStatus();
            } catch (e) {
                setMsg(e.message, true);
            }
        });
    });
}

function renderEvents(rows) {
    if (!rows || !rows.length) {
        els.tbodyEvents.innerHTML = '<tr><td colspan="5" class="hint">등록된 행사 이력이 없습니다.</td></tr>';
        return;
    }
    const parseNote = (note) => {
        const text = String(note || '');
        const reporter = (text.match(/보고자:([^/]+)/) || [])[1]?.trim() || '-';
        const reason = (text.match(/사유:([^/]+)/) || [])[1]?.trim() || '-';
        return { reporter, reason };
    };
    els.tbodyEvents.innerHTML = rows.map(r => `
        <tr>
            <td>${r.exercise_date || '-'}</td>
            <td class="right">${fmtNum(r.quantity)}</td>
            <td>${parseNote(r.note).reporter}</td>
            <td>${parseNote(r.note).reason}</td>
            <td><button class="btn btn-secondary btn-del-ex" data-id="${r.id}">삭제</button></td>
        </tr>
    `).join('');
    document.querySelectorAll('.btn-del-ex').forEach(btn => {
        btn.addEventListener('click', async () => {
            try {
                await api('DELETE', `/api/overhang/exercises/${btn.dataset.id}`);
                await loadStatus();
            } catch (e) {
                setMsg(e.message, true);
            }
        });
    });
}

function renderKisMilestones(rows) {
    if (!rows || !rows.length) {
        els.tbodyKisMilestones.innerHTML = '<tr><td colspan="6" class="hint">비교 가능한 KIS 기간 데이터가 없습니다.</td></tr>';
        return;
    }
    els.tbodyKisMilestones.innerHTML = rows.map(r => `
        <tr>
            <td>${r.label || '-'}</td>
            <td>${r.cutoff_date || '-'}</td>
            <td class="right">${fmtNum(r.unlocked_overhang_qty)}</td>
            <td class="right">${fmtNum(r.kis_cum_net_sell_qty)}</td>
            <td class="right">${fmtPct(r.coverage_pct)}</td>
            <td class="right">${fmtNum(r.unmatched_qty)}</td>
        </tr>
    `).join('');
}

function renderUnlockBadges(rows, totalQty) {
    if (!rows || !rows.length) {
        els.unlockBadges.innerHTML = '<span class="hint">락업 날짜별 데이터가 없습니다.</span>';
        return;
    }
    const total = Number(totalQty || 0);
    let cum = 0;
    els.unlockBadges.innerHTML = rows.map(r => {
        const qty = Number(r.qty || 0);
        cum += qty;
        const rowPct = total > 0 ? (qty / total) * 100 : NaN;
        const cumPct = total > 0 ? (cum / total) * 100 : NaN;
        return (
        `<span class="card" style="display:inline-flex;align-items:center;gap:8px;padding:8px 10px;">` +
        `<span class="k">${r.unlock_date}</span><strong>${fmtNum(qty)}주</strong>` +
        `<span class="hint">(${fmtPct(rowPct)} / 누적 ${fmtPct(cumPct)})</span></span>`
    );
    }).join('');
}

function renderUnlockChart(rows, totalQty) {
    const canvas = els.unlockChart;
    if (!canvas || typeof Chart === 'undefined') return;
    if (unlockChart) {
        unlockChart.destroy();
        unlockChart = null;
    }
    const labels = (rows || []).map(r => r.unlock_date || '-');
    const qtyData = (rows || []).map(r => Number(r.qty || 0));
    const total = Number(totalQty || 0);
    let run = 0;
    const cumPctData = qtyData.map(v => {
        run += v;
        return total > 0 ? Number(((run / total) * 100).toFixed(2)) : 0;
    });

    unlockChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    type: 'bar',
                    label: '출회 가능 수량',
                    data: qtyData,
                    backgroundColor: 'rgba(37, 99, 235, 0.55)',
                    borderColor: 'rgba(37, 99, 235, 0.95)',
                    borderWidth: 1,
                    yAxisID: 'y',
                },
                {
                    type: 'line',
                    label: '누적 비중(%)',
                    data: cumPctData,
                    borderColor: 'rgba(220, 38, 38, 0.9)',
                    backgroundColor: 'rgba(220, 38, 38, 0.25)',
                    borderWidth: 2,
                    tension: 0.2,
                    pointRadius: 2,
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
            },
            scales: {
                y: {
                    position: 'left',
                    ticks: {
                        callback: (v) => Number(v).toLocaleString('ko-KR'),
                    },
                    title: { display: true, text: '수량(주)' },
                },
                y1: {
                    position: 'right',
                    min: 0,
                    max: 100,
                    grid: { drawOnChartArea: false },
                    ticks: {
                        callback: (v) => `${v}%`,
                    },
                    title: { display: true, text: '누적 비중(%)' },
                },
            },
        },
    });
}

async function loadStatus() {
    if (!state.selected || !state.selected.stock_code) {
        setMsg('검색 후 종목을 선택해 주세요.', true);
        return;
    }
    setMsg('조회 중...');
    try {
        const data = await api('GET', `/api/overhang/${state.selected.stock_code}`);
        if (data.stock_name) setSelected({ stock_code: data.stock_code, stock_name: data.stock_name });
        renderSummary(data.summary || {});
        const totalQty = Number((data.summary || {}).ipo_overhang_total_qty || 0);
        renderLockups(data.lockups || [], totalQty);
        renderEvents(data.exercise_events || []);
        renderKisMilestones(data.kis_milestones || []);
        const unlockRows = data.available_by_unlock_date || [];
        renderUnlockBadges(unlockRows, totalQty);
        renderUnlockChart(unlockRows, totalQty);
        setMsg(`기준일: ${(data.summary || {}).as_of_date || '-'}`);
    } catch (e) {
        setMsg(e.message, true);
    }
}

async function addLockup() {
    if (!state.selected) {
        setMsg('종목을 먼저 선택해 주세요.', true);
        return;
    }
    const payload = {
        stock_code: state.selected.stock_code,
        stock_name: state.selected.stock_name,
        holder_name: (els.inHolder.value || '').trim(),
        holder_type: (els.inHolderType.value || '').trim(),
        lockup_end_date: (els.inUnlock.value || '').trim(),
        quantity: Number(els.inQty.value || 0),
        source_note: (els.inNote.value || '').trim(),
    };
    try {
        await api('POST', '/api/overhang/lockups', payload);
        els.inHolder.value = '';
        els.inHolderType.value = '';
        els.inUnlock.value = '';
        els.inQty.value = '';
        els.inNote.value = '';
        await loadStatus();
    } catch (e) {
        setMsg(e.message, true);
    }
}

async function addExercise() {
    if (!state.selected) {
        setMsg('종목을 먼저 선택해 주세요.', true);
        return;
    }
    const payload = {
        stock_code: state.selected.stock_code,
        stock_name: state.selected.stock_name,
        exercise_date: (els.inExDate.value || '').trim(),
        quantity: Number(els.inExQty.value || 0),
        note: (els.inExNote.value || '').trim(),
    };
    try {
        await api('POST', '/api/overhang/exercises', payload);
        els.inExDate.value = '';
        els.inExQty.value = '';
        els.inExNote.value = '';
        await loadStatus();
    } catch (e) {
        setMsg(e.message, true);
    }
}

async function syncFromDart() {
    if (!state.selected) {
        setMsg('종목을 먼저 선택해 주세요.', true);
        return;
    }
    setMsg('DART 자동수집 중...');
    try {
        const out = await api('POST', '/api/overhang/sync-dart', {
            stock_code: state.selected.stock_code,
            stock_name: state.selected.stock_name,
        });
        const msg = `자동수집 완료: 락업 +${out.inserted_lockups}건, 행사 +${out.inserted_exercises}건`;
        setMsg(msg);
        await loadStatus();
    } catch (e) {
        setMsg(e.message, true);
    }
}

els.btnSearch.addEventListener('click', searchStock);
els.btnRefresh.addEventListener('click', loadStatus);
els.btnSyncDart.addEventListener('click', syncFromDart);
els.btnAddLockup.addEventListener('click', addLockup);
els.btnAddEx.addEventListener('click', addExercise);
els.stockQuery.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') searchStock();
});
