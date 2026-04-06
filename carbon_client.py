import os
import datetime
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

API_URL = "https://apis.data.go.kr/1160100/service/GetGeneralProductInfoService/getCertifiedEmissionReductionPriceInfo"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SCEEX_BASE_URL = "https://ets.sceex.com.cn"


def _get_key() -> str:
    return os.environ.get("CARBON_API_KEY", "")


async def fetch_carbon_prices(
    item_name: str = "KAU25",
    begin_date: str | None = None,
    end_date: str | None = None,
    num_rows: int = 1000,
) -> list[dict]:
    """Fetch carbon emission credit prices from data.go.kr API."""
    key = _get_key()
    if not key:
        return []

    params = {
        "serviceKey": key,
        "resultType": "json",
        "numOfRows": str(num_rows),
        "pageNo": "1",
        "itmsNm": item_name,
    }
    if begin_date:
        params["beginBasDt"] = begin_date
    if end_date:
        params["endBasDt"] = end_date

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(API_URL, params=params)
        resp.raise_for_status()

    data = resp.json()
    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

    results = []
    for item in items:
        results.append({
            "date": item["basDt"],
            "item_name": item["itmsNm"],
            "close": int(item["clpr"]),
            "open": int(item["mkp"]) if item["mkp"] != "0" else None,
            "high": int(item["hipr"]) if item["hipr"] != "0" else None,
            "low": int(item["lopr"]) if item["lopr"] != "0" else None,
            "change": int(item["vs"]),
            "change_rate": float(item["fltRt"]) if item["fltRt"] else 0.0,
            "volume": int(item["trqu"]),
            "trade_amount": int(item["trPrc"]),
        })

    # API returns newest first, reverse to chronological order
    results.reverse()
    return results


async def fetch_all_carbon_items(date: str | None = None, num_rows: int = 20) -> list[dict]:
    """Fetch all carbon credit items for a given date."""
    key = _get_key()
    if not key:
        return []

    params = {
        "serviceKey": key,
        "resultType": "json",
        "numOfRows": str(num_rows),
        "pageNo": "1",
    }
    if date:
        params["basDt"] = date

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(API_URL, params=params)
        resp.raise_for_status()

    data = resp.json()
    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

    results = []
    for item in items:
        results.append({
            "date": item["basDt"],
            "item_name": item["itmsNm"],
            "close": int(item["clpr"]),
            "change": int(item["vs"]),
            "change_rate": float(item["fltRt"]) if item["fltRt"] else 0.0,
            "volume": int(item["trqu"]),
        })
    return results


def _safe_float(value):
    if value is None:
        return None
    text = str(value).replace(",", "").replace("€", "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except Exception:
        return None


def _safe_int(value):
    num = _safe_float(value)
    return int(num) if num is not None else None


async def fetch_yahoo_symbol_history(symbol: str, range_str: str = "1y", interval: str = "1d") -> list[dict]:
    params = {"range": range_str, "interval": interval, "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        resp = await client.get(YAHOO_CHART_URL.format(symbol=symbol), params=params)
        resp.raise_for_status()
        data = resp.json()

    result = (((data or {}).get("chart") or {}).get("result") or [None])[0] or {}
    timestamps = result.get("timestamp") or []
    quote = ((((result.get("indicators") or {}).get("quote") or [None])[0]) or {})
    closes = quote.get("close") or []
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    volumes = quote.get("volume") or []

    rows = []
    prev_close = None
    for idx, ts in enumerate(timestamps):
        close = _safe_float(closes[idx] if idx < len(closes) else None)
        if close is None:
            continue
        open_price = _safe_float(opens[idx] if idx < len(opens) else None)
        high = _safe_float(highs[idx] if idx < len(highs) else None)
        low = _safe_float(lows[idx] if idx < len(lows) else None)
        volume = _safe_int(volumes[idx] if idx < len(volumes) else None) or 0
        change = None if prev_close is None else round(close - prev_close, 4)
        change_rate = None if prev_close in (None, 0) else round((close - prev_close) / prev_close * 100, 2)
        rows.append({
            "date": datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
            "close": round(close, 4),
            "open": round(open_price, 4) if open_price is not None else None,
            "high": round(high, 4) if high is not None else None,
            "low": round(low, 4) if low is not None else None,
            "change": change,
            "change_rate": change_rate,
            "volume": volume,
            "trade_amount": None,
        })
        prev_close = close
    return rows


async def _fetch_sceex_table_rows(path: str, max_pages: int = 5) -> list[list[str]]:
    headers = {"User-Agent": "Mozilla/5.0"}
    rows: list[list[str]] = []
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        for page in range(1, max_pages + 1):
            sep = "&" if "?" in path else "?"
            page_path = f"{path}{sep}pageIndex={page}"
            resp = await client.get(urljoin(SCEEX_BASE_URL, page_path))
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if not table:
                break
            page_rows = []
            for tr in table.find_all("tr")[1:]:
                cols = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if cols:
                    page_rows.append(cols)
            if not page_rows:
                break
            rows.extend(page_rows)
    return rows


async def fetch_sceex_domestic_history(product_code: str = "SHEA", max_pages: int = 5) -> list[dict]:
    raw_rows = await _fetch_sceex_table_rows(
        "/internal.htm?k=guo_nei_xing_qing&url=mrhq_gn&orderby=tradeTime%20desc",
        max_pages=max_pages,
    )
    out = []
    for cols in raw_rows:
        if len(cols) < 10 or cols[2] != product_code:
            continue
        out.append({
            "date": cols[0],
            "exchange": cols[1],
            "item_name": cols[2],
            "open": _safe_float(cols[3]),
            "high": _safe_float(cols[4]),
            "low": _safe_float(cols[5]),
            "avg_price": _safe_float(cols[6]),
            "close": _safe_float(cols[7]),
            "volume": _safe_int(cols[8]) or 0,
            "trade_amount": _safe_float(cols[9]),
        })
    out.sort(key=lambda x: x["date"])
    prev_close = None
    for row in out:
        close = row["close"]
        row["change"] = None if prev_close is None or close is None else round(close - prev_close, 4)
        row["change_rate"] = None if prev_close in (None, 0) or close is None else round((close - prev_close) / prev_close * 100, 2)
        prev_close = close if close is not None else prev_close
    return out


async def fetch_sceex_international_history(product_keyword: str = "ECX-EUA", max_pages: int = 5) -> list[dict]:
    raw_rows = await _fetch_sceex_table_rows(
        "/history.htm?k=guo_ji_xing_qing&url=mrhq_gj",
        max_pages=max_pages,
    )
    out = []
    for cols in raw_rows:
        if len(cols) < 5 or product_keyword not in cols[2]:
            continue
        out.append({
            "date": cols[0],
            "exchange": cols[1],
            "item_name": cols[2],
            "close": _safe_float(cols[3]),
            "volume": _safe_int(cols[4]) or 0,
            "trade_amount": None,
            "open": None,
            "high": None,
            "low": None,
        })
    out.sort(key=lambda x: x["date"])
    prev_close = None
    for row in out:
        close = row["close"]
        row["change"] = None if prev_close is None or close is None else round(close - prev_close, 4)
        row["change_rate"] = None if prev_close in (None, 0) or close is None else round((close - prev_close) / prev_close * 100, 2)
        prev_close = close if close is not None else prev_close
    return out
