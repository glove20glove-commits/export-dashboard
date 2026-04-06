let watchlist = [];
let sortKey = "1w";
let sortOrder = "desc";
let selectedSingle = { code: "", name: "" };

async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    const resp = await fetch(path, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `API error: ${resp.status}`);
    }
    return resp.json();
}

function fmt(v, digits = 2) {
    if (v === null || v === undefined) return "-";
    return Number(v).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function cls(v) {
    if (v === null || v === undefined) return "";
    return Number(v) >= 0 ? "pos" : "neg";
}

function rate(v) {
    if (v === null || v === undefined) return "-";
    const n = Number(v);
    return `${n >= 0 ? "+" : ""}${fmt(n, 2)}%`;
}

function switchTab(tab) {
    const s = tab === "single";
    document.getElementById("tab-btn-single").classList.toggle("active", s);
    document.getElementById("tab-btn-all").classList.toggle("active", !s);
    document.getElementById("tab-single").classList.toggle("active", s);
    document.getElementById("tab-all").classList.toggle("active", !s);
}

function setSelectedSingle(code, name) {
    selectedSingle.code = (code || "").padStart(6, "0");
    selectedSingle.name = name || selectedSingle.code;
    document.getElementById("single-selected").textContent = `선택: ${selectedSingle.name} (${selectedSingle.code})`;
    document.getElementById("single-stock-query").value = selectedSingle.name;
}

function renderSuggestions(items) {
    const box = document.getElementById("single-stock-suggest");
    if (!items.length) {
        box.innerHTML = `<span class="hint">검색 결과가 없습니다.</span>`;
        return;
    }
    box.innerHTML = items.slice(0, 15).map(it => `
        <button class="stock-chip" onclick="pickSingle('${it.code}','${(it.name || "").replace(/'/g, "\\'")}')">
            ${it.name} <span class="mono">${it.code}</span>${it.market ? ` <span class="hint">(${it.market})</span>` : ""}
        </button>
    `).join(" ");
}

async function searchSingleStocks() {
    const q = document.getElementById("single-stock-query").value.trim();
    if (!q) {
        document.getElementById("single-stock-suggest").innerHTML = `<span class="hint">종목명을 입력하고 검색하면 후보가 표시됩니다.</span>`;
        return;
    }
    const results = await api("GET", `/api/stock-monitor/search?name=${encodeURIComponent(q)}`);
    renderSuggestions(results || []);
}

async function loadWatchlist() {
    watchlist = await api("GET", "/api/stock-monitor/watchlist");
}

function drawChart(canvas, points) {
    const ctx = canvas.getContext("2d");
    const w = canvas.width = canvas.clientWidth || 800;
    const h = canvas.height = 160;
    ctx.clearRect(0, 0, w, h);
    if (!points || points.length < 2) return;

    const vals = points.map(p => Number(p.close));
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const pad = 20;
    const x = i => pad + (w - pad * 2) * (i / (points.length - 1));
    const y = v => {
        if (max === min) return h / 2;
        return h - pad - ((v - min) / (max - min)) * (h - pad * 2);
    };
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((p, i) => {
        const xx = x(i), yy = y(Number(p.close));
        if (i === 0) ctx.moveTo(xx, yy);
        else ctx.lineTo(xx, yy);
    });
    ctx.stroke();
}

async function loadSingle() {
    const code = selectedSingle.code;
    if (!code) {
        document.getElementById("single-asof").textContent = "종목을 먼저 선택하세요.";
        return;
    }
    const d = await api("GET", `/api/stock-monitor/detail?stock_code=${encodeURIComponent(code)}`);
    document.getElementById("single-asof").textContent = `기준일: ${d.as_of_date} (전일 종가 ${fmt(d.latest_close, 0)})`;
    const r = d.returns || {};
    document.getElementById("single-metrics").innerHTML = `
        <div class="metric"><div>1년</div><div class="v ${cls(r["1y"])}">${rate(r["1y"])}</div></div>
        <div class="metric"><div>6개월</div><div class="v ${cls(r["6m"])}">${rate(r["6m"])}</div></div>
        <div class="metric"><div>1개월</div><div class="v ${cls(r["1m"])}">${rate(r["1m"])}</div></div>
        <div class="metric"><div>1주일</div><div class="v ${cls(r["1w"])}">${rate(r["1w"])}</div></div>
    `;
    drawChart(document.getElementById("single-chart"), d.trend || []);
}

function renderSortState() {
    document.querySelectorAll("th.sortable").forEach(th => {
        const active = th.dataset.key === sortKey;
        th.classList.toggle("active", active);
        th.textContent = th.textContent.replace(" ↑", "").replace(" ↓", "");
        if (active) th.textContent += sortOrder === "desc" ? " ↓" : " ↑";
    });
    document.querySelectorAll(".period-btn").forEach(btn => {
        if (!btn.dataset.base) btn.dataset.base = btn.textContent.replace(" ↑", "").replace(" ↓", "");
        const active = btn.dataset.key === sortKey;
        btn.classList.toggle("active", active);
        btn.textContent = btn.dataset.base + (active ? (sortOrder === "desc" ? " ↓" : " ↑") : "");
    });
}

async function loadAll() {
    const rows = await api("GET", `/api/stock-monitor/overview?sort_by=${encodeURIComponent(sortKey)}&order=${encodeURIComponent(sortOrder)}`);
    const tbody = document.getElementById("all-tbody");
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="hint" style="text-align:center;padding:22px;">데이터가 없습니다. 전종목 수익률 갱신을 먼저 실행하세요.</td></tr>`;
        return;
    }
    tbody.innerHTML = rows.map(r => `
        <tr>
            <td><button class="stock-chip" onclick="goSingle('${r.stock_code}','${(r.stock_name || "").replace(/'/g, "\\'")}')">${r.stock_name} <span class="mono">${r.stock_code}</span></button></td>
            <td>${r.as_of_date || "-"}</td>
            <td class="right">${fmt(r.latest_close, 0)}</td>
            <td class="right ${cls(r.ret_5y)}">${rate(r.ret_5y)}</td>
            <td class="right ${cls(r.ret_3y)}">${rate(r.ret_3y)}</td>
            <td class="right ${cls(r.ret_1y)}">${rate(r.ret_1y)}</td>
            <td class="right ${cls(r.ret_6m)}">${rate(r.ret_6m)}</td>
            <td class="right ${cls(r.ret_1m)}">${rate(r.ret_1m)}</td>
            <td class="right ${cls(r.ret_1w)}">${rate(r.ret_1w)}</td>
        </tr>
    `).join("");
    renderSortState();
}

async function refreshAllBatches() {
    const msg = document.getElementById("all-msg");
    msg.textContent = "갱신 시작...";
    const wl = await api("GET", "/api/stock-monitor/watchlist");
    const total = wl.length;
    let start = 0;
    let upserted = 0;
    while (start < total) {
        const r = await api("POST", `/api/stock-monitor/refresh?start=${start}&limit=120`);
        upserted += Number(r.upserted || 0);
        start += 120;
        msg.textContent = `갱신 중... ${Math.min(start, total)}/${total} (저장 ${upserted})`;
    }
    msg.textContent = `갱신 완료: ${upserted}개 종목`;
    await loadAll();
}

async function pickSingle(code, name) {
    setSelectedSingle(code, name);
    document.getElementById("single-stock-suggest").innerHTML = "";
}

async function goSingle(code, name = "") {
    switchTab("single");
    setSelectedSingle(code, name || code);
    await loadSingle();
}

function bindEvents() {
    document.getElementById("tab-btn-single").addEventListener("click", () => switchTab("single"));
    document.getElementById("tab-btn-all").addEventListener("click", async () => {
        switchTab("all");
        await loadAll();
    });
    document.getElementById("btn-search-single").addEventListener("click", searchSingleStocks);
    document.getElementById("single-stock-query").addEventListener("keydown", async (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            await searchSingleStocks();
        }
    });
    document.getElementById("btn-load-single").addEventListener("click", loadSingle);
    document.getElementById("btn-refresh-all").addEventListener("click", refreshAllBatches);
    document.querySelectorAll("th.sortable").forEach(th => {
        th.addEventListener("click", async () => {
            const key = th.dataset.key;
            if (sortKey === key) sortOrder = (sortOrder === "desc" ? "asc" : "desc");
            else { sortKey = key; sortOrder = "desc"; }
            await loadAll();
        });
    });
    document.querySelectorAll(".period-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const key = btn.dataset.key;
            if (sortKey === key) sortOrder = (sortOrder === "desc" ? "asc" : "desc");
            else { sortKey = key; sortOrder = "desc"; }
            await loadAll();
        });
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    document.getElementById("single-selected").textContent = "선택: -";
    renderSortState();
    await loadWatchlist();
    await loadSingle();
});

window.goSingle = goSingle;
window.pickSingle = pickSingle;
