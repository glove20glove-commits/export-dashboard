"""
Alpha Vantage API 클라이언트
- S&P 500 (SPY ETF) / NASDAQ (QQQ ETF) 일봉 데이터
- 섹터별 퍼포먼스 (Alpha Vantage 우선, Yahoo fallback)
- 무료 티어: 25 calls/day
"""
import os
import re
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=False)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

BASE_URL = "https://www.alphavantage.co/query"
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
TIMEOUT = 30

# SPDR sector ETFs mapped to display names used in UI/analysis.
SECTOR_ETF_MAP = {
    "소재": "XLB",
    "커뮤니케이션 서비스": "XLC",
    "에너지": "XLE",
    "금융": "XLF",
    "산업재": "XLI",
    "기술": "XLK",
    "필수소비재": "XLP",
    "부동산": "XLRE",
    "유틸리티": "XLU",
    "헬스케어": "XLV",
    "경기소비재": "XLY",
}

FINVIZ_SECTOR_NAME_MAP = {
    "Basic Materials": "소재",
    "Communication Services": "커뮤니케이션 서비스",
    "Consumer Cyclical": "경기소비재",
    "Consumer Defensive": "필수소비재",
    "Energy": "에너지",
    "Financial": "금융",
    "Healthcare": "헬스케어",
    "Industrials": "산업재",
    "Real Estate": "부동산",
    "Technology": "기술",
    "Utilities": "유틸리티",
}

async def _fetch_sector_performance_from_alpha_etfs(api_key: str) -> dict:
    """
    Last-resort fallback:
    compute sector performance from sector ETF daily change_pct via Alpha Vantage.
    """
    result = {}
    items = list(SECTOR_ETF_MAP.items())
    for idx, (sector_name, symbol) in enumerate(items):
        try:
            daily = await fetch_daily_index(symbol, api_key)
            result[sector_name] = round(float(daily.get("change_pct", 0.0)), 2)
        except Exception as e:
            msg = str(e).lower()
            if "호출 한도" in msg or "rate limit" in msg or "api call frequency" in msg:
                break
        if idx < len(items) - 1:
            await asyncio.sleep(0.5)
    return result


def _get_api_key():
    key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not key:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY 환경변수가 설정되지 않았습니다")
    return key


async def fetch_daily_index(symbol: str, api_key: str = None) -> dict:
    """
    특정 심볼의 최근 거래일 종가 + 변동률 조회.
    symbol: "SPY" (S&P500 ETF) or "QQQ" (NASDAQ ETF)
    Returns: {"date": "2026-03-13", "close": 512.34, "prev_close": 508.12, "change_pct": 0.83}
    """
    api_key = api_key or _get_api_key()
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",  # last 100 days
        "apikey": api_key,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    ts = data.get("Time Series (Daily)", {})
    if not ts:
        note = data.get("Note", data.get("Information", ""))
        if "rate limit" in note.lower() or "api call frequency" in note.lower():
            raise RuntimeError(f"Alpha Vantage API 호출 한도 초과: {note}")
        raise RuntimeError(f"데이터 없음 ({symbol}): {note or data}")

    dates = sorted(ts.keys(), reverse=True)
    if len(dates) < 2:
        raise RuntimeError(f"충분한 데이터가 없습니다 ({symbol})")

    latest = ts[dates[0]]
    prev = ts[dates[1]]
    close = float(latest["4. close"])
    prev_close = float(prev["4. close"])
    change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0

    return {
        "date": dates[0],
        "close": round(close, 2),
        "prev_close": round(prev_close, 2),
        "change_pct": change_pct,
        "open": round(float(latest["1. open"]), 2),
        "high": round(float(latest["2. high"]), 2),
        "low": round(float(latest["3. low"]), 2),
        "volume": int(float(latest["5. volume"])),
    }


async def fetch_daily_index_series(symbol: str, api_key: str = None, limit: int = 30) -> list[dict]:
    """
    특정 심볼의 최근 거래일 시계열(최신순) 조회.
    Returns: [{"date":"YYYY-MM-DD","close":..,"prev_close":..,"change_pct":..}, ...]
    """
    api_key = api_key or _get_api_key()
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": api_key,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    ts = data.get("Time Series (Daily)", {})
    if not ts:
        note = data.get("Note", data.get("Information", ""))
        if "rate limit" in note.lower() or "api call frequency" in note.lower():
            raise RuntimeError(f"Alpha Vantage API 호출 한도 초과: {note}")
        raise RuntimeError(f"데이터 없음 ({symbol}): {note or data}")

    dates = sorted(ts.keys(), reverse=True)
    out = []
    max_items = max(1, min(int(limit), max(1, len(dates) - 1)))
    for i in range(max_items):
        latest = ts[dates[i]]
        prev = ts[dates[i + 1]]
        close = float(latest["4. close"])
        prev_close = float(prev["4. close"])
        change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0
        out.append({
            "date": dates[i],
            "close": round(close, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": change_pct,
            "open": round(float(latest["1. open"]), 2),
            "high": round(float(latest["2. high"]), 2),
            "low": round(float(latest["3. low"]), 2),
            "volume": int(float(latest["5. volume"])),
        })
    return out


async def fetch_sector_performance(api_key: str = None) -> dict:
    """
    섹터별 일일 퍼포먼스 조회.
    Returns: {"Information Technology": 1.23, "Healthcare": -0.45, ...}
    """
    # 1) Alpha Vantage legacy SECTOR endpoint (if available for the key/plan)
    try:
        api_key = api_key or _get_api_key()
        params = {
            "function": "SECTOR",
            "apikey": api_key,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        day_perf = data.get("Rank A: Real-Time Performance", {})
        if not day_perf:
            day_perf = data.get("Rank B: 1 Day Performance", {})
        if day_perf:
            result = {}
            for sector, pct_str in day_perf.items():
                try:
                    result[sector] = float(str(pct_str).replace("%", ""))
                except (ValueError, TypeError):
                    continue
            if result:
                return result
    except Exception:
        # Fall through to Yahoo fallback.
        pass

    # 2) Yahoo Finance multi-symbol quote fallback (fast and no Alpha call limit)
    symbols = ",".join(SECTOR_ETF_MAP.values())
    symbol_to_sector = {v: k for k, v in SECTOR_ETF_MAP.items()}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(YAHOO_QUOTE_URL, params={"symbols": symbols})
            resp.raise_for_status()
            payload = resp.json()

        quotes = payload.get("quoteResponse", {}).get("result", [])
        result = {}
        for q in quotes:
            symbol = q.get("symbol")
            sector_name = symbol_to_sector.get(symbol)
            if not sector_name:
                continue
            pct = q.get("regularMarketChangePercent")
            if pct is None:
                pct = q.get("postMarketChangePercent")
            if pct is None:
                continue
            try:
                result[sector_name] = round(float(pct), 2)
            except (ValueError, TypeError):
                continue
        if result:
            return result
    except Exception:
        pass

    # 3) Finviz sector table fallback (single page parse)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://finviz.com/groups.ashx?g=sector&v=140&o=-change"
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        # Capture row sector name + first % column (daily change)
        pattern = re.compile(
            r'<tr[^>]*?>.*?<a [^>]*class="tab-link">([^<]+)</a></td>'
            r'<td[^>]*><span[^>]*>([-+]?\d+(?:\.\d+)?)%</span>',
            re.IGNORECASE | re.DOTALL,
        )
        result = {}
        for eng_name, pct_str in pattern.findall(html):
            sector_name = FINVIZ_SECTOR_NAME_MAP.get(eng_name.strip(), eng_name.strip())
            try:
                result[sector_name] = round(float(pct_str), 2)
            except (ValueError, TypeError):
                continue
        if result:
            return result
    except Exception:
        pass

    # 4) Final fallback: Alpha daily ETF changes per sector
    try:
        api_key = api_key or _get_api_key()
        return await _fetch_sector_performance_from_alpha_etfs(api_key)
    except Exception:
        return {}


async def fetch_sp500_daily(api_key: str = None) -> dict:
    """S&P 500 (SPY ETF) 최신 데이터"""
    return await fetch_daily_index("SPY", api_key)


async def fetch_nasdaq_daily(api_key: str = None) -> dict:
    """NASDAQ (QQQ ETF) 최신 데이터"""
    return await fetch_daily_index("QQQ", api_key)
