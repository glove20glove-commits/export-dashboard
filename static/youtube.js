let channels = [];
let videos = [];
let sortCol = 'published_at';
let sortAsc = false;
let recentSortCol = 'published_at';
let recentSortAsc = false;

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('btn-add').addEventListener('click', addChannel);
    document.getElementById('channel-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') addChannel();
    });
    document.getElementById('channel-filter').addEventListener('change', loadVideos);
    document.getElementById('limit-select').addEventListener('change', loadVideos);

    // Sort handlers for both tables
    document.querySelectorAll('#data-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => sortTable('all', th.dataset.sort));
    });
    document.querySelectorAll('#recent-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => sortTable('recent', th.dataset.sort));
    });

    await loadChannels();
    await loadVideos();
});

// --- API helper ---
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

// --- Channels ---
async function loadChannels() {
    try {
        channels = await api('GET', '/api/youtube/channels');
        renderChannels();
        updateFilterOptions();
    } catch (e) {
        console.error('Failed to load channels:', e);
    }
}

function renderChannels() {
    const container = document.getElementById('channel-cards');
    if (!channels.length) {
        container.innerHTML = '<p style="color:var(--text-secondary);padding:12px;">등록된 채널이 없습니다. 위에서 채널을 추가해주세요.</p>';
        return;
    }
    container.innerHTML = channels.map(ch => `
        <div class="card" style="cursor:default;min-width:220px;">
            <div class="card-label" style="display:flex;justify-content:space-between;align-items:center;">
                <span>${esc(ch.channel_name)}</span>
                <span style="display:flex;gap:4px;">
                    <button class="btn btn-secondary" style="padding:2px 8px;font-size:12px;" onclick="fetchChannel(${ch.id})" title="새 영상 확인">&#x21bb;</button>
                    <button class="btn btn-danger" style="padding:2px 8px;font-size:12px;" onclick="deleteChannel(${ch.id})" title="삭제">&times;</button>
                </span>
            </div>
            <div class="card-value" style="font-size:14px;">
                <a href="${esc(ch.channel_url)}" target="_blank" style="color:var(--primary);text-decoration:none;">${esc(ch.channel_id)}</a>
            </div>
            <div class="card-sub">${ch.last_checked_at ? '최근 확인: ' + fmtDate(ch.last_checked_at) : '미확인'}</div>
        </div>
    `).join('');
}

function updateFilterOptions() {
    const sel = document.getElementById('channel-filter');
    const current = sel.value;
    sel.innerHTML = '<option value="">전체</option>';
    channels.forEach(ch => {
        sel.innerHTML += `<option value="${ch.id}">${esc(ch.channel_name)}</option>`;
    });
    sel.value = current;
}

async function addChannel() {
    const input = document.getElementById('channel-input');
    const identifier = input.value.trim();
    if (!identifier) return;

    const btn = document.getElementById('btn-add');
    btn.disabled = true;
    btn.textContent = '등록 중...';

    try {
        await api('POST', '/api/youtube/channels', { identifier });
        input.value = '';
        await loadChannels();
        await loadVideos();
    } catch (e) {
        alert('채널 등록 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '등록';
    }
}

async function deleteChannel(dbId) {
    if (!confirm('이 채널을 삭제하시겠습니까?')) return;
    try {
        await api('DELETE', `/api/youtube/channels/${dbId}`);
        await loadChannels();
        await loadVideos();
    } catch (e) {
        alert('삭제 실패: ' + e.message);
    }
}

async function fetchChannel(dbId) {
    try {
        const result = await api('POST', `/api/youtube/channels/${dbId}/fetch`);
        await loadChannels();
        await loadVideos();
        if (result.new > 0) {
            alert(`새 영상 ${result.new}개 발견!`);
        }
    } catch (e) {
        alert('가져오기 실패: ' + e.message);
    }
}

// --- Videos ---
async function loadVideos() {
    try {
        const channelId = document.getElementById('channel-filter').value;
        const limit = document.getElementById('limit-select').value;
        let url = `/api/youtube/videos?limit=${limit}`;
        if (channelId) url += `&channel_id=${channelId}`;

        videos = await api('GET', url);

        document.getElementById('video-controls').style.display = '';
        document.getElementById('recent-section').style.display = '';
        document.getElementById('table-section').style.display = '';

        renderAll();
    } catch (e) {
        console.error('Failed to load videos:', e);
    }
}

function getRecentVideos() {
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    const cutoff = oneWeekAgo.toISOString();
    return videos.filter(v => v.published_at && v.published_at >= cutoff);
}

function renderAll() {
    const recent = getRecentVideos();
    sortList(recent, recentSortCol, recentSortAsc);
    renderTable(document.querySelector('#recent-table tbody'), recent, 'recent');

    const all = [...videos];
    sortList(all, sortCol, sortAsc);
    renderTable(document.querySelector('#data-table tbody'), all, 'all');
}

function renderTable(tbody, list, tableId) {
    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);padding:24px;">${tableId === 'recent' ? '최근 일주일간 영상이 없습니다' : '영상이 없습니다'}</td></tr>`;
        return;
    }
    tbody.innerHTML = list.map(v => {
        const ch = channels.find(c => c.id === v.channel_db_id);
        const chName = ch ? ch.channel_name : '';
        let summaryCell;
        if (v.summary) {
            summaryCell = `<div class="summary-cell">${esc(v.summary)}</div>
                <button class="btn btn-secondary" style="padding:2px 6px;font-size:11px;margin-top:4px;" onclick="summarizeVideo('${esc(v.video_id)}')">재요약</button>`;
        } else {
            summaryCell = `<button class="btn btn-primary" style="padding:4px 10px;font-size:12px;" onclick="summarizeVideo('${esc(v.video_id)}')">요약</button>`;
        }
        return `
        <tr>
            <td>${v.thumbnail_url ? `<a href="${esc(v.url)}" target="_blank"><img src="${esc(v.thumbnail_url)}" alt="" style="width:100px;height:56px;object-fit:cover;border-radius:4px;"></a>` : '-'}</td>
            <td><a href="${esc(v.url)}" target="_blank" class="title-cell" style="color:var(--text);text-decoration:none;">${esc(v.title)}</a></td>
            <td>${summaryCell}</td>
            <td style="font-size:13px;">${esc(chName)}</td>
            <td style="font-size:13px;">${v.published_at ? fmtDate(v.published_at) : '-'}</td>
            <td>${v.notified ? '<span style="color:var(--success);">&#10003;</span>' : '<span style="color:var(--text-secondary);">-</span>'}</td>
        </tr>`;
    }).join('');
}

function sortTable(tableId, col) {
    if (tableId === 'recent') {
        if (recentSortCol === col) { recentSortAsc = !recentSortAsc; }
        else { recentSortCol = col; recentSortAsc = col === 'title' || col === 'channel_name'; }
        updateSortIndicators('#recent-table', recentSortCol, recentSortAsc);
    } else {
        if (sortCol === col) { sortAsc = !sortAsc; }
        else { sortCol = col; sortAsc = col === 'title' || col === 'channel_name'; }
        updateSortIndicators('#data-table', sortCol, sortAsc);
    }
    renderAll();
}

function updateSortIndicators(tableSelector, col, asc) {
    document.querySelectorAll(`${tableSelector} th`).forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.dataset.sort === col) {
            th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
        }
    });
}

function sortList(list, col, asc) {
    list.sort((a, b) => {
        let va = a[col] || '';
        let vb = b[col] || '';
        if (col === 'channel_name') {
            const ca = channels.find(c => c.id === a.channel_db_id);
            const cb = channels.find(c => c.id === b.channel_db_id);
            va = ca ? ca.channel_name : '';
            vb = cb ? cb.channel_name : '';
        }
        if (va < vb) return asc ? -1 : 1;
        if (va > vb) return asc ? 1 : -1;
        return 0;
    });
}

// --- Summarize ---
async function summarizeVideo(videoId) {
    try {
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = '요약 중...';
        const result = await api('POST', `/api/youtube/videos/${videoId}/summarize`);
        await loadVideos();
    } catch (e) {
        alert('요약 실패: ' + e.message);
        await loadVideos();
    }
}

// --- Helpers ---
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
