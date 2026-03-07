import re
import httpx

NAVER_CHART_URL = "https://fchart.stock.naver.com/sise.nhn"
NAVER_SEARCH_URL = "https://m.stock.naver.com/front-api/search/autoComplete"


async def search_stock_by_name(query: str) -> list[dict]:
    """Search stock by name using Naver Finance autocomplete API."""
    params = {"query": query, "target": "stock"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            NAVER_SEARCH_URL, params=params,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
    data = resp.json()
    if not data.get("isSuccess") or not data.get("result", {}).get("items"):
        return []
    return [
        {"name": item["name"], "code": item["code"], "market": item.get("typeName", "")}
        for item in data["result"]["items"]
        if item.get("category") == "stock" and item.get("nationCode") == "KOR"
    ]


async def fetch_stock_prices(stock_code: str, count: int = 120) -> list[dict]:
    """Fetch monthly stock prices from Naver Finance chart API."""
    params = {
        "symbol": stock_code,
        "timeframe": "month",
        "count": str(count),
        "requestType": "0",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(NAVER_CHART_URL, params=params)
        resp.raise_for_status()

    results = []
    for match in re.finditer(r'data="(\d{8})\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|', resp.text):
        date_str = match.group(1)
        close_price = int(match.group(5))
        year = date_str[:4]
        month = date_str[4:6]
        results.append({
            "year": year,
            "month": month,
            "close_price": close_price,
        })

    return results


async def fetch_index_prices(symbol: str = "KOSPI", count: int = 120) -> list[dict]:
    """Fetch monthly index prices from Naver Finance (KOSPI, KOSDAQ etc)."""
    params = {
        "symbol": symbol,
        "timeframe": "month",
        "count": str(count),
        "requestType": "0",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(NAVER_CHART_URL, params=params)
        resp.raise_for_status()

    results = []
    for match in re.finditer(r'data="(\d{8})\|([0-9.]+)\|([0-9.]+)\|([0-9.]+)\|([0-9.]+)\|', resp.text):
        date_str = match.group(1)
        close_price = float(match.group(5))
        results.append({
            "year": date_str[:4],
            "month": date_str[4:6],
            "close_price": round(close_price, 2),
        })

    return results


async def fetch_daily_stock_prices(stock_code: str, count: int = 500) -> list[dict]:
    """Fetch daily stock prices from Naver Finance chart API."""
    params = {
        "symbol": stock_code,
        "timeframe": "day",
        "count": str(count),
        "requestType": "0",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(NAVER_CHART_URL, params=params)
        resp.raise_for_status()

    results = []
    for match in re.finditer(r'data="(\d{8})\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|(\d+)"', resp.text):
        results.append({
            "date": match.group(1),
            "close": int(match.group(5)),
            "volume": int(match.group(6)),
        })

    return results
