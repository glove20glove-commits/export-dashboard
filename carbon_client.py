import os
import httpx

API_URL = "https://apis.data.go.kr/1160100/service/GetGeneralProductInfoService/getCertifiedEmissionReductionPriceInfo"


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
