"""
Quarterly performance data client
- FnGuide quarterly financial extraction
- Simple web snippet search for performance reasons
"""

from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

FN_GUIDE_URL = "https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp"
DUCK_URL = "https://duckduckgo.com/html/"
TIMEOUT = 30


def _to_float(v: str) -> float:
    if not v:
        return 0.0
    s = str(v).replace(",", "").replace(" ", "").strip()
    if s in {"", "-", "N/A", "&nbsp;"}:
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def _quarter_key_from_label(label: str) -> str:
    # label examples: 2025/09, 2026/03(E)
    s = label.replace("(E)", "").strip()
    m = re.match(r"(\d{4})\/(\d{2})", s)
    if not m:
        return ""
    year = int(m.group(1))
    month = int(m.group(2))
    q = (month - 1) // 3 + 1
    return f"{year}Q{q}"


def fetch_fnguide_quarterly(stock_code: str) -> List[Dict]:
    """
    Returns actual quarterly metrics (excluding estimate columns):
    [{quarter_key, revenue, operating_profit, net_income}, ...] newest first
    """
    code = stock_code.zfill(6)
    params = {
        "pGB": "1",
        "gicode": f"A{code}",
        "cID": "",
        "MenuYn": "Y",
        "ReportGB": "",
        "NewMenuID": "Y",
        "stkGb": "701",
    }

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        html = client.get(FN_GUIDE_URL, params=params).text

    soup = BeautifulSoup(html, "html.parser")
    table_wrap = soup.select_one("#highlight_D_Q")
    if not table_wrap:
        return []

    # Header columns (quarter labels)
    header_ths = table_wrap.select("thead tr")
    if len(header_ths) < 2:
        return []
    quarter_labels = [th.get_text(" ", strip=True) for th in header_ths[1].select("th")]

    actual_indices = []
    quarter_keys = []
    for i, label in enumerate(quarter_labels):
        if "(E)" in label:
            continue
        qk = _quarter_key_from_label(label)
        if not qk:
            continue
        actual_indices.append(i)
        quarter_keys.append(qk)

    revenue_vals: List[float] = []
    op_vals: List[float] = []
    net_vals: List[float] = []

    for tr in table_wrap.select("tbody tr"):
        name = tr.select_one("th")
        if not name:
            continue
        row_name = name.get_text(" ", strip=True)
        tds = tr.select("td")
        vals = [_to_float(td.get("title") or td.get_text(" ", strip=True)) for td in tds]

        if row_name == "매출액":
            revenue_vals = vals
        elif row_name == "영업이익":
            op_vals = vals
        elif row_name == "당기순이익":
            net_vals = vals

    if not revenue_vals or not op_vals or not net_vals:
        return []

    out = []
    for col_idx, qk in zip(actual_indices, quarter_keys):
        if col_idx >= len(revenue_vals) or col_idx >= len(op_vals) or col_idx >= len(net_vals):
            continue
        out.append({
            "quarter_key": qk,
            "revenue": revenue_vals[col_idx],
            "operating_profit": op_vals[col_idx],
            "net_income": net_vals[col_idx],
            "source_url": f"{FN_GUIDE_URL}?pGB=1&gicode=A{code}&cID=&MenuYn=Y&ReportGB=&NewMenuID=Y&stkGb=701",
        })

    # newest first
    out.sort(key=lambda x: x["quarter_key"], reverse=True)
    return out


def search_reason_snippets(company_name: str, quarter_key: str, max_results: int = 5) -> List[str]:
    query = f"{company_name} {quarter_key} 실적 호실적 이유"
    url = f"{DUCK_URL}?q={quote_plus(query)}"

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        html = client.get(url).text

    soup = BeautifulSoup(html, "html.parser")
    snippets = []
    for tag in soup.select(".result__snippet"):
        txt = tag.get_text(" ", strip=True)
        if txt:
            snippets.append(txt)
        if len(snippets) >= max_results:
            break
    return snippets
