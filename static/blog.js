/**
 * 블로그 모니터링 프론트엔드
 * - 유튜브 모니터링(youtube.js)과 동일한 패턴
 */

let feeds = [];
let articles = [];
let sortCol = 'published_at';
let sortAsc = false;
let recentSortCol = 'published_at';
let recentSortAsc = false;

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('btn-add').addEventListener('click', addFeed);
    document.getElementById('blog-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') addFeed();
    });
    document.getElementById('feed-filter').addEventListener('change', loadArticles);
    document.getElementById('limit-select').addEventListener('change', loadArticles);

    // Sort handlers
    document.querySelectorAll('#data-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => sortTable('all', th.dataset.sort));
    });
    document.querySelectorAll('#recent-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => sortTable('recent', th.dataset.sort));
    });

    await loadFeeds();
    await loadArticles();
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

// ── 블로그 피드 ──
async function loadFeeds() {
    try {
        feeds = await api('GET', '/api/blog/feeds');
        renderFeeds();
        updateFilterOptions();
    } catch (e) {
        console.error('Failed to load feeds:', e);
    }
}

function renderFeeds() {
    const container = document.getElementById('feed-cards');
    if (!feeds.length) {
        container.innerHTML = '<p style="color:var(--text-secondary);padding:12px;">등록된 블로그가 없습니다. 위에서 블로그를 추가해주세요.</p>';
        return;
    }
    container.innerHTML = feeds.map(f => `
        <div class="card" style="cursor:default;min-width:220px;">
            <div class="card-label" style="display:flex;justify-content:space-between;align-items:center;">
                <span>${esc(f.title || f.url)}</span>
                <span style="display:flex;gap:4px;">
                    <button class="btn btn-secondary" style="padding:2px 8px;font-size:12px;"
                            onclick="fetchFeed(${f.id})" title="새 글 확인">&#x21bb;</button>
                    <button class="btn btn-danger" style="padding:2px 8px;font-size:12px;"
                            onclick="deleteFeed(${f.id})" title="삭제">&times;</button>
                </span>
            </div>
            <div class="card-value" style="font-size:13px;">
                <a href="${esc(f.url)}" target="_blank"
                   style="color:var(--primary);text-decoration:none;word-break:break-all;">
                    ${esc(f.url.length > 50 ? f.url.substring(0, 50) + '...' : f.url)}
                </a>
            </div>
            <div class="card-sub" style="display:flex;gap:8px;align-items:center;">
                ${f.feed_url
                    ? '<span style="color:var(--success);font-size:11px;">● RSS</span>'
                    : '<span style="color:var(--text-muted);font-size:11px;">● 스크래핑</span>'
                }
                <span>${f.last_checked ? '최근 확인: ' + fmtDate(f.last_checked) : '미확인'}</span>
            </div>
        </div>
    `).join('');
}

function updateFilterOptions() {
    const sel = document.getElementById('feed-filter');
    const current = sel.value;
    sel.innerHTML = '<option value="">전체</option>';
    feeds.forEach(f => {
        sel.innerHTML += `<option value="${f.id}">${esc(f.title || f.url)}</option>`;
    });
    sel.value = current;
}

async function addFeed() {
    const input = document.getElementById('blog-input');
    const url = input.value.trim();
    if (!url) return;

    const btn = document.getElementById('btn-add');
    btn.disabled = true;
    btn.textContent = '등록 중...';
    try {
        await api('POST', '/api/blog/feeds', { url });
        input.value = '';
        await loadFeeds();
        await loadArticles();
    } catch (e) {
        alert('블로그 등록 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '등록';
    }
}

async function deleteFeed(feedId) {
    if (!confirm('이 블로그를 삭제하시겠습니까?')) return;
    try {
        await api('DELETE', `/api/blog/feeds/${feedId}`);
        await loadFeeds();
        await loadArticles();
    } catch (e) {
        alert('삭제 실패: ' + e.message);
    }
}

async function fetchFeed(feedId) {
    try {
        const btn = event.target;
        btn.disabled = true;
        const result = await api('POST', `/api/blog/feeds/${feedId}/fetch`);
        await loadFeeds();
        await loadArticles();
        if (result.new > 0) {
            alert(`새 글 ${result.new}개 발견!`);
        } else {
            alert('새 글이 없습니다.');
        }
    } catch (e) {
        alert('가져오기 실패: ' + e.message);
    }
}

// ── 글 목록 ──
async function loadArticles() {
    try {
        const feedId = document.getElementById('feed-filter').value;
        const limit = document.getElementById('limit-select').value;
        let url = `/api/blog/articles?limit=${limit}`;
        if (feedId) url += `&feed_id=${feedId}`;

        articles = await api('GET', url);
        document.getElementById('article-controls').style.display = '';
        document.getElementById('recent-section').style.display = '';
        document.getElementById('table-section').style.display = '';
        renderAll();
    } catch (e) {
        console.error('Failed to load articles:', e);
    }
}

function getRecentArticles() {
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    const cutoff = oneWeekAgo.toISOString().substring(0, 10);
    return articles.filter(a => a.published_at && a.published_at >= cutoff);
}

function renderAll() {
    const recent = getRecentArticles();
    sortList(recent, recentSortCol, recentSortAsc);
    renderTable(document.querySelector('#recent-table tbody'), recent, 'recent');

    const all = [...articles];
    sortList(all, sortCol, sortAsc);
    renderTable(document.querySelector('#data-table tbody'), all, 'all');
}

function renderTable(tbody, list, tableId) {
    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);padding:24px;">
            ${tableId === 'recent' ? '최근 일주일간 글이 없습니다' : '글이 없습니다'}</td></tr>`;
        return;
    }

    tbody.innerHTML = list.map(a => {
        const feed = feeds.find(f => f.id === a.feed_id);
        const feedName = feed ? (feed.title || feed.url) : '';

        // 언어 배지
        let langBadge = '';
        if (a.language) {
            const cls = ['ko', 'en', 'ja', 'zh'].includes(a.language) ? a.language : 'other';
            const labels = { ko: '한국어', en: '영어', ja: '일본어', zh: '중국어' };
            const label = labels[a.language] || a.language.toUpperCase();
            langBadge = `<span class="lang-badge ${cls}">${label}</span>`;
            if (a.translated) {
                langBadge += `<span class="translated-badge">번역됨</span>`;
            }
        }

        // 요약 셀
        let summaryCell;
        if (a.summary) {
            summaryCell = `
                <div class="summary-cell">${esc(a.summary)}</div>
                <button class="btn btn-secondary" style="padding:2px 6px;font-size:11px;margin-top:4px;"
                        onclick="summarizeArticle(${a.id})">재요약</button>`;
        } else {
            summaryCell = `
                <button class="btn btn-primary" style="padding:4px 10px;font-size:12px;"
                        onclick="summarizeArticle(${a.id})">요약</button>`;
        }

        return `
            <tr>
                <td><a href="${esc(a.url)}" target="_blank" class="title-cell"
                       style="color:var(--text);text-decoration:none;">${esc(a.title)}</a></td>
                <td>${summaryCell}</td>
                <td>${langBadge || '<span style="color:var(--text-secondary);font-size:12px;">-</span>'}</td>
                <td style="font-size:13px;">${esc(feedName)}</td>
                <td style="font-size:13px;">${a.published_at ? fmtDate(a.published_at) : '-'}</td>
                <td>${a.notified
                    ? '<span style="color:var(--success);">&#10003;</span>'
                    : '<span style="color:var(--text-secondary);">-</span>'}</td>
            </tr>`;
    }).join('');
}

// ── 정렬 ──
function sortTable(tableId, col) {
    if (tableId === 'recent') {
        if (recentSortCol === col) recentSortAsc = !recentSortAsc;
        else { recentSortCol = col; recentSortAsc = col === 'title' || col === 'feed_name'; }
        updateSortIndicators('#recent-table', recentSortCol, recentSortAsc);
    } else {
        if (sortCol === col) sortAsc = !sortAsc;
        else { sortCol = col; sortAsc = col === 'title' || col === 'feed_name'; }
        updateSortIndicators('#data-table', sortCol, sortAsc);
    }
    renderAll();
}

function updateSortIndicators(sel, col, asc) {
    document.querySelectorAll(`${sel} th`).forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.dataset.sort === col) th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
    });
}

function sortList(list, col, asc) {
    list.sort((a, b) => {
        let va = a[col] || '';
        let vb = b[col] || '';
        if (col === 'feed_name') {
            const fa = feeds.find(f => f.id === a.feed_id);
            const fb = feeds.find(f => f.id === b.feed_id);
            va = fa ? (fa.title || fa.url) : '';
            vb = fb ? (fb.title || fb.url) : '';
        }
        if (va < vb) return asc ? -1 : 1;
        if (va > vb) return asc ? 1 : -1;
        return 0;
    });
}

// ── AI 요약 ──
async function summarizeArticle(articleId) {
    try {
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = '요약 중...';
        await api('POST', `/api/blog/articles/${articleId}/summarize`);
        await loadArticles();
    } catch (e) {
        alert('요약 실패: ' + e.message);
        await loadArticles();
    }
}

// ── 헬퍼 ──
function fmtDate(s) {
    if (!s) return '-';
    return s.substring(0, 10);
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
