import asyncio
import html
import re

import httpx

DRAM_CONTRACT_URL = "https://www.trendforce.com/price/dram/dram_contract"
NAND_CONTRACT_URL = "https://www.trendforce.com/price/flash/flash_contract"

_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml",
}


def _strip_tags(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _to_float(text: str):
    raw = (text or "").replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", raw)
    return float(m.group(0)) if m else None


def _to_change_pct(text: str):
    raw = (text or "").strip()
    val = _to_float(raw)
    if val is None:
        return None
    if "▼" in raw:
        return -abs(val)
    if "▲" in raw:
        return abs(val)
    return val


def _to_direction(text: str):
    raw = (text or "").strip()
    if "▲" in raw:
        return "up"
    if "▼" in raw:
        return "down"
    return "flat"


def _extract_last_update(html_text: str) -> str:
    m = re.search(r"Last Update\s*([^<]{1,80})", html_text, flags=re.I)
    return m.group(1).strip() if m else ""


def _extract_rows(html_text: str):
    tbody = re.search(r"<tbody[^>]*>(.*?)</tbody>", html_text, flags=re.I | re.S)
    if not tbody:
        return []

    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody.group(1), flags=re.I | re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.I | re.S)
        if len(tds) < 7:
            continue

        item_name = _strip_tags(tds[0])
        if not item_name:
            continue

        rows.append({
            "product_name": item_name,
            "daily_high": _to_float(_strip_tags(tds[1])),
            "daily_low": _to_float(_strip_tags(tds[2])),
            "session_high": _to_float(_strip_tags(tds[3])),
            "session_low": _to_float(_strip_tags(tds[4])),
            "session_avg": _to_float(_strip_tags(tds[5])),
            "session_change_pct": _to_change_pct(_strip_tags(tds[6])),
            "change_direction": _to_direction(_strip_tags(tds[6])),
        })

    return rows


async def _fetch_contract_page(client: httpx.AsyncClient, market_type: str, url: str):
    resp = await client.get(url)
    resp.raise_for_status()
    html_text = resp.text
    return {
        "market_type": market_type,
        "source_url": url,
        "source_updated_at": _extract_last_update(html_text),
        "items": _extract_rows(html_text),
    }


async def fetch_semiconductor_contract_prices():
    async with httpx.AsyncClient(timeout=30, headers=_HEADERS, follow_redirects=True) as client:
        dram, nand = await asyncio.gather(
            _fetch_contract_page(client, "DRAM", DRAM_CONTRACT_URL),
            _fetch_contract_page(client, "NAND", NAND_CONTRACT_URL),
        )
    return {"DRAM": dram, "NAND": nand}
