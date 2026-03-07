"""National Pension Service (NPS) API client for company headcount tracking.

API structure:
- Each month (dataCrtYm) generates a new seq for each company.
- getBassInfoSearchV2: search by name → get all seq numbers with dataCrtYm
- getDetailInfoSearchV2: get subscriber count (jnngpCnt) for a specific seq
- getPdAcctoSttusInfoSearchV2: get hires/losses for a specific seq
"""

import asyncio
import os

import httpx

NPS_BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2"
API_KEY = os.environ.get("NPS_API_KEY", "")
REQUEST_DELAY = 0.5  # seconds between requests
TIMEOUT = 60  # seconds per request
MAX_RETRIES = 3


async def _get_json(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    """GET with retries and JSON parsing."""
    import json
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url, params=params)
            text = resp.text.strip()
            if not text or text.startswith("<"):
                raise ValueError(f"Non-JSON response (HTTP {resp.status_code}): {text[:100]}")
            return json.loads(text)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ReadError,
                httpx.ConnectError, json.JSONDecodeError, ValueError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = 5 * (attempt + 1)
                print(f"[nps] Retry {attempt+1}/{MAX_RETRIES} after {type(e).__name__}, waiting {wait}s")
                await asyncio.sleep(wait)
            else:
                raise


def _parse_items(data: dict) -> list:
    """Extract items list from NPS API response."""
    items = (
        data.get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item", [])
    )
    if isinstance(items, dict):
        items = [items]
    return items


async def search_company(name: str) -> list[dict]:
    """Search NPS companies by name.
    Returns deduplicated list per biz_no with latest seq.
    """
    url = f"{NPS_BASE}/getBassInfoSearchV2"
    params = {
        "serviceKey": API_KEY,
        "wkplNm": name,
        "numOfRows": 100,
        "pageNo": 1,
        "dataType": "json",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        data = await _get_json(client, url, params)

    items = _parse_items(data)

    # Deduplicate: keep latest seq per (wkplNm, bzowrRgstNo)
    seen = {}
    for item in items:
        key = (item.get("wkplNm", ""), item.get("bzowrRgstNo", ""))
        ym = item.get("dataCrtYm", "")
        if key not in seen or ym > seen[key]["dataCrtYm"]:
            seen[key] = item

    results = []
    for item in seen.values():
        results.append({
            "seq": str(item.get("seq", "")),
            "name": item.get("wkplNm", ""),
            "biz_no": item.get("bzowrRgstNo", ""),
            "status": item.get("wkplJnngStcd", ""),
            "dataCrtYm": item.get("dataCrtYm", ""),
        })
    results.sort(key=lambda x: x["name"])
    return results


async def _get_all_snapshots(client: httpx.AsyncClient, name: str, biz_no: str) -> list[dict]:
    """Get all monthly snapshots (seq + dataCrtYm) for a specific company."""
    url = f"{NPS_BASE}/getBassInfoSearchV2"
    all_items = []
    page = 1

    while True:
        params = {
            "serviceKey": API_KEY,
            "wkplNm": name,
            "numOfRows": 100,
            "pageNo": page,
            "dataType": "json",
        }
        data = await _get_json(client, url, params)
        await asyncio.sleep(REQUEST_DELAY)

        body = data.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break

        for item in items:
            if item.get("wkplNm") == name and item.get("bzowrRgstNo") == biz_no:
                all_items.append({
                    "seq": str(item["seq"]),
                    "dataCrtYm": item.get("dataCrtYm", ""),
                })

        total = int(body.get("totalCount", 0))
        if page * 100 >= total:
            break
        page += 1

    all_items.sort(key=lambda x: x["dataCrtYm"])
    return all_items


async def fetch_nps_data(seq: str, name: str, biz_no: str) -> tuple[int, list[dict]]:
    """Fetch complete NPS data for a company.

    1. Get all monthly snapshots via search
    2. For each snapshot, fetch subscriber count and hires/losses

    Returns (current_count, monthly_data).
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        snapshots = await _get_all_snapshots(client, name, biz_no)
        if not snapshots:
            return 0, []

        results = []
        for snap in snapshots:
            ym = snap["dataCrtYm"]
            if len(ym) < 6:
                continue
            year = ym[:4]
            month = ym[4:6]

            # Fetch detail (subscriber count)
            detail_url = f"{NPS_BASE}/getDetailInfoSearchV2"
            detail_data = await _get_json(client, detail_url, {
                "serviceKey": API_KEY, "seq": snap["seq"], "dataType": "json",
            })
            await asyncio.sleep(REQUEST_DELAY)

            detail_items = _parse_items(detail_data)
            subscribers = int(detail_items[0].get("jnngpCnt", 0)) if detail_items else 0

            # Fetch period (hires/losses)
            period_url = f"{NPS_BASE}/getPdAcctoSttusInfoSearchV2"
            period_data = await _get_json(client, period_url, {
                "serviceKey": API_KEY, "seq": snap["seq"], "dataType": "json",
            })
            await asyncio.sleep(REQUEST_DELAY)

            period_items = _parse_items(period_data)
            new_hires = int(period_items[0].get("nwAcqzrCnt", 0)) if period_items else 0
            losses = int(period_items[0].get("lssJnngpCnt", 0)) if period_items else 0

            results.append({
                "year": year,
                "month": month,
                "subscribers": subscribers,
                "new_hires": new_hires,
                "losses": losses,
            })

    current_count = results[-1]["subscribers"] if results else 0
    return current_count, results
