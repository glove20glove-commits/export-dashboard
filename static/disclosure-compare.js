let watchlist = [];
let reportOptions = [];
let selectedStock = { code: "", name: "" };
let textFilter = "all";
let textKeyword = "";
let lastTextRows = [];
const TEXT_PAGE_SIZE = 300;
let textShownCount = TEXT_PAGE_SIZE;

function fmt(n) {
    const v = Number(n || 0);
    return v.toLocaleString();
}

function pct(v) {
    if (v === null || v === undefined) return "-";
    const n = Number(v);
    return `${n >= 0 ? "+" : ""}${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function escapeHtml(v) {
    return String(v || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

async function api(method, path) {
    const resp = await fetch(path, { method });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `API error ${resp.status}`);
    }
    return resp.json();
}

function setMsg(text) {
    document.getElementById("msg").textContent = text || "";
}

function setTextMsg(text) {
    document.getElementById("text-msg").textContent = text || "";
}

function resetCompareViews() {
    // financial compare reset
    document.getElementById("meta").textContent = "비교할 종목/보고서를 선택하세요.";
    document.getElementById("cnt-changed").textContent = "-";
    document.getElementById("cnt-left").textContent = "-";
    document.getElementById("cnt-right").textContent = "-";
    document.getElementById("tbody-changed").innerHTML = `<tr><td colspan="6" class="hint" style="text-align:center;padding:20px;">비교 결과가 없습니다.</td></tr>`;
    document.getElementById("tbody-left").innerHTML = `<tr><td colspan="3" class="hint" style="text-align:center;padding:20px;">없음</td></tr>`;
    document.getElementById("tbody-right").innerHTML = `<tr><td colspan="3" class="hint" style="text-align:center;padding:20px;">없음</td></tr>`;

    // text compare reset
    document.getElementById("text-meta").textContent = "텍스트 비교를 실행하면 결과가 표시됩니다.";
    document.getElementById("text-cnt-changed").textContent = "-";
    document.getElementById("text-cnt-added").textContent = "-";
    document.getElementById("text-cnt-removed").textContent = "-";
    document.getElementById("tbody-text-diff").innerHTML = `<tr><td colspan="3" class="hint" style="text-align:center;padding:20px;">텍스트 비교 결과가 없습니다.</td></tr>`;
    document.getElementById("text-render-info").textContent = "";
    document.getElementById("btn-text-more").style.display = "none";
    const keywordInput = document.getElementById("text-search-keyword");
    if (keywordInput) keywordInput.value = "";
    lastTextRows = [];
    textKeyword = "";
    textShownCount = TEXT_PAGE_SIZE;
    setTextFilter("all");
    setMsg("");
    setTextMsg("");
}

function setSelectedStock(code, name) {
    const prevCode = selectedStock.code;
    selectedStock.code = (code || "").padStart(6, "0");
    selectedStock.name = name || selectedStock.code;
    document.getElementById("stock-selected").textContent = `선택: ${selectedStock.name} (${selectedStock.code})`;
    document.getElementById("stock-query").value = selectedStock.name;
    if (prevCode && prevCode !== selectedStock.code) {
        resetCompareViews();
    }
}

function renderStockSuggestions(items) {
    const box = document.getElementById("stock-suggest");
    if (!items.length) {
        box.innerHTML = `<span class="hint">검색 결과가 없습니다.</span>`;
        return;
    }
    box.innerHTML = items.slice(0, 15).map(it => `
        <button class="stock-chip" onclick="pickDisclosureStock('${it.code}','${(it.name || "").replace(/'/g, "\\'")}')">
            ${it.name} <span class="mono">${it.code}</span>${it.market ? ` <span class="hint">(${it.market})</span>` : ""}
        </button>
    `).join(" ");
}

async function searchStocks() {
    const q = document.getElementById("stock-query").value.trim();
    if (!q) {
        document.getElementById("stock-suggest").innerHTML = `<span class="hint">종목명을 입력하고 검색하면 후보가 표시됩니다.</span>`;
        return;
    }
    const results = await api("GET", `/api/stock-monitor/search?name=${encodeURIComponent(q)}`);
    renderStockSuggestions(results || []);
}

async function loadWatchlist() {
    watchlist = await api("GET", "/api/disclosure-compare/watchlist");
}

function reportLabel(r) {
    return `${r.rcept_dt} | ${r.report_type} | ${r.report_nm}`;
}

async function loadReports() {
    const stockCode = selectedStock.code;
    if (!stockCode) {
        document.getElementById("left-report").innerHTML = "";
        document.getElementById("right-report").innerHTML = "";
        return;
    }
    setMsg("보고서 목록 조회 중...");
    const data = await api("GET", `/api/disclosure-compare/reports?stock_code=${encodeURIComponent(stockCode)}`);
    reportOptions = data.reports || [];
    const left = document.getElementById("left-report");
    const right = document.getElementById("right-report");
    const opts = reportOptions.map((r, i) => `<option value="${i}">${reportLabel(r)}</option>`).join("");
    left.innerHTML = opts;
    right.innerHTML = opts;
    if (reportOptions.length >= 2) {
        left.value = "0";
        right.value = "1";
    }
    setMsg(`보고서 ${reportOptions.length}건`);
}

function renderSummary(d) {
    document.getElementById("meta").textContent =
        `${d.stock_code} | 비교1: ${d.left.bsns_year} ${d.left.report_name} | 비교2: ${d.right.bsns_year} ${d.right.report_name}`;
    document.getElementById("cnt-changed").textContent = fmt(d.summary.changed_count);
    document.getElementById("cnt-left").textContent = fmt(d.summary.only_left_count);
    document.getElementById("cnt-right").textContent = fmt(d.summary.only_right_count);
}

function renderTables(d) {
    const changed = document.getElementById("tbody-changed");
    const onlyLeft = document.getElementById("tbody-left");
    const onlyRight = document.getElementById("tbody-right");

    changed.innerHTML = (d.changed || []).map(r => `
        <tr>
            <td>${r.sj_div || "-"}</td>
            <td>${r.account_nm || "-"}</td>
            <td class="right">${fmt(r.left_amount)}</td>
            <td class="right">${fmt(r.right_amount)}</td>
            <td class="right ${Number(r.diff) >= 0 ? "up" : "down"}">${Number(r.diff) >= 0 ? "+" : ""}${fmt(r.diff)}</td>
            <td class="right ${Number(r.diff_pct || 0) >= 0 ? "up" : "down"}">${pct(r.diff_pct)}</td>
        </tr>
    `).join("") || `<tr><td colspan="6" class="hint" style="text-align:center;padding:20px;">차이 항목이 없습니다.</td></tr>`;

    onlyLeft.innerHTML = (d.only_left || []).map(r => `
        <tr>
            <td>${r.sj_div || "-"}</td>
            <td>${r.account_nm || "-"}</td>
            <td class="right">${fmt(r.amount)}</td>
        </tr>
    `).join("") || `<tr><td colspan="3" class="hint" style="text-align:center;padding:20px;">없음</td></tr>`;

    onlyRight.innerHTML = (d.only_right || []).map(r => `
        <tr>
            <td>${r.sj_div || "-"}</td>
            <td>${r.account_nm || "-"}</td>
            <td class="right">${fmt(r.amount)}</td>
        </tr>
    `).join("") || `<tr><td colspan="3" class="hint" style="text-align:center;padding:20px;">없음</td></tr>`;
}

function renderTextCompare(d) {
    const summary = d.summary || {};
    document.getElementById("text-meta").textContent =
        `${d.stock_code} | 단위: ${d.unit === "sentence" ? "문장" : "문단"} | 비교 건수: ${fmt(summary.diff_count || 0)}`;
    document.getElementById("text-cnt-changed").textContent = fmt(summary.changed_count || 0);
    document.getElementById("text-cnt-added").textContent = fmt(summary.added_count || 0);
    document.getElementById("text-cnt-removed").textContent = fmt(summary.removed_count || 0);

    lastTextRows = d.rows || [];
    textShownCount = TEXT_PAGE_SIZE;
    renderTextRows();
}

function getFilterButtons() {
    return [
        document.getElementById("text-filter-all"),
        document.getElementById("text-filter-changed"),
        document.getElementById("text-filter-added"),
        document.getElementById("text-filter-removed"),
    ].filter(Boolean);
}

function setTextFilter(kind) {
    textFilter = kind;
    getFilterButtons().forEach(btn => {
        const active = btn.id === `text-filter-${kind}`;
        btn.classList.toggle("btn-primary", active);
    });
    textShownCount = TEXT_PAGE_SIZE;
    renderTextRows();
}

function getFilteredTextRows() {
    let rows = lastTextRows || [];
    if (textFilter === "added") {
        rows = rows.filter(r => (r.kind || "") === "removed");
    } else if (textFilter === "removed") {
        rows = rows.filter(r => (r.kind || "") === "added");
    } else if (textFilter !== "all") {
        rows = rows.filter(r => (r.kind || "") === textFilter);
    }

    const kw = (textKeyword || "").trim().toLowerCase();
    if (kw) {
        rows = rows.filter(r => {
            const left = String(r.left_text || "").toLowerCase();
            const right = String(r.right_text || "").toLowerCase();
            return left.includes(kw) || right.includes(kw);
        });
    }
    return rows;
}

function renderTextRows() {
    const tbody = document.getElementById("tbody-text-diff");
    const info = document.getElementById("text-render-info");
    const moreBtn = document.getElementById("btn-text-more");
    const rows = getFilteredTextRows();
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="3" class="hint" style="text-align:center;padding:20px;">표시할 텍스트 차이가 없습니다.</td></tr>`;
        info.textContent = "0건";
        moreBtn.style.display = "none";
        return;
    }
    const visibleRows = rows.slice(0, textShownCount);
    tbody.innerHTML = visibleRows.map(r => {
        const kind = r.kind || "changed";
        const label = kind === "removed" ? "추가" : kind === "added" ? "삭제" : "변경";
        const rowCls = kind === "removed" ? "added-row" : kind === "added" ? "removed-row" : "changed-row";
        return `
            <tr class="${rowCls}">
                <td>${label}</td>
                <td>${escapeHtml(r.left_text || "-")}</td>
                <td>${escapeHtml(r.right_text || "-")}</td>
            </tr>
        `;
    }).join("");
    info.textContent = `${fmt(visibleRows.length)} / ${fmt(rows.length)}건 표시`;
    if (visibleRows.length < rows.length) {
        moreBtn.style.display = "";
        moreBtn.textContent = `더보기 (${fmt(rows.length - visibleRows.length)}건 남음)`;
    } else {
        moreBtn.style.display = "none";
    }
}

function getSelectedReports() {
    const stockCode = selectedStock.code;
    const li = Number(document.getElementById("left-report").value);
    const ri = Number(document.getElementById("right-report").value);
    if (!stockCode) {
        throw new Error("종목을 먼저 선택하세요.");
    }
    if (!Number.isFinite(li) || !Number.isFinite(ri) || !reportOptions[li] || !reportOptions[ri]) {
        throw new Error("비교할 보고서 2개를 선택하세요.");
    }
    if (li === ri) {
        throw new Error("서로 다른 보고서를 선택해 주세요.");
    }
    return { stockCode, left: reportOptions[li], right: reportOptions[ri] };
}

async function compareNow() {
    const { stockCode, left, right } = getSelectedReports();
    setMsg("비교 중...");
    const q = new URLSearchParams({
        stock_code: stockCode,
        left_bsns_year: String(left.bsns_year),
        left_reprt_code: String(left.reprt_code),
        right_bsns_year: String(right.bsns_year),
        right_reprt_code: String(right.reprt_code),
    });
    const d = await api("GET", `/api/disclosure-compare/compare?${q.toString()}`);
    renderSummary(d);
    renderTables(d);
    setMsg("완료");
}

async function textCompareNow() {
    const { stockCode, left, right } = getSelectedReports();
    const unit = document.getElementById("text-unit").value || "paragraph";
    setTextMsg("텍스트 비교 중...");
    const q = new URLSearchParams({
        stock_code: stockCode,
        left_rcept_no: String(left.rcept_no),
        right_rcept_no: String(right.rcept_no),
        unit,
    });
    const d = await api("GET", `/api/disclosure-compare/text-compare?${q.toString()}`);
    renderTextCompare(d);
    setTextMsg("완료");
}

async function pickDisclosureStock(code, name) {
    setSelectedStock(code, name);
    document.getElementById("stock-suggest").innerHTML = "";
    await loadReports();
}

function bindEvents() {
    document.getElementById("btn-search-stock").addEventListener("click", searchStocks);
    document.getElementById("stock-query").addEventListener("keydown", async (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            await searchStocks();
        }
    });
    document.getElementById("btn-compare").addEventListener("click", async () => {
        try {
            await compareNow();
        } catch (e) {
            setMsg(`비교 실패: ${e.message}`);
        }
    });
    document.getElementById("btn-text-compare").addEventListener("click", async () => {
        try {
            await textCompareNow();
        } catch (e) {
            setTextMsg(`텍스트 비교 실패: ${e.message}`);
        }
    });
    document.getElementById("text-filter-all").addEventListener("click", () => setTextFilter("all"));
    document.getElementById("text-filter-changed").addEventListener("click", () => setTextFilter("changed"));
    document.getElementById("text-filter-added").addEventListener("click", () => setTextFilter("added"));
    document.getElementById("text-filter-removed").addEventListener("click", () => setTextFilter("removed"));
    document.getElementById("text-search-keyword").addEventListener("input", (e) => {
        textKeyword = e.target.value || "";
        textShownCount = TEXT_PAGE_SIZE;
        renderTextRows();
    });
    document.getElementById("btn-text-search-clear").addEventListener("click", () => {
        const input = document.getElementById("text-search-keyword");
        if (input) input.value = "";
        textKeyword = "";
        textShownCount = TEXT_PAGE_SIZE;
        renderTextRows();
    });
    document.getElementById("btn-text-more").addEventListener("click", () => {
        textShownCount += TEXT_PAGE_SIZE;
        renderTextRows();
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    resetCompareViews();
    try {
        await loadWatchlist();
        await loadReports();
    } catch (e) {
        setMsg(`초기 로딩 실패: ${e.message}`);
    }
});

window.pickDisclosureStock = pickDisclosureStock;
