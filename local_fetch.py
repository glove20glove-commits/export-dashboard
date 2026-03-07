#!/usr/bin/env python3
"""Fetch KITA data locally and upload to Railway.

Usage:
    python local_fetch.py                    # fetch all items with no data
    python local_fetch.py 22 23 24           # fetch specific items
    python local_fetch.py --year-from 2020   # custom start year
"""
import asyncio
import sys
import time
import httpx

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

sys.path.insert(0, ".")
from kita_client import get_daily_request_count

RAILWAY_URL = "https://web-production-a69d3.up.railway.app"
YEAR_FROM = 2019
MONTH_FROM = 1
YEAR_TO = 2026
MONTH_TO = 1


def railway_get(path: str, retries=3):
    """Sync GET with retries."""
    for attempt in range(retries):
        try:
            resp = httpx.get(f"{RAILWAY_URL}{path}", timeout=60)
            return resp
        except (httpx.ReadError, httpx.ReadTimeout, httpx.ConnectError) as e:
            if attempt < retries - 1:
                wait = 10 * (attempt + 1)
                print(f"  Railway error ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def railway_post(path: str, payload: dict, retries=3):
    """Sync POST with retries."""
    for attempt in range(retries):
        try:
            resp = httpx.post(f"{RAILWAY_URL}{path}", json=payload, timeout=60)
            return resp
        except (httpx.ReadError, httpx.ReadTimeout, httpx.ConnectError) as e:
            if attempt < retries - 1:
                wait = 10 * (attempt + 1)
                print(f"  Railway error ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def get_items():
    resp = railway_get("/api/items")
    items = resp.json()
    resp2 = railway_get("/api/industry/items")
    items.extend(resp2.json())
    return items


def get_existing(item_id: int) -> set:
    resp = railway_get(f"/api/data/{item_id}")
    data = resp.json()
    return {f"{r['year']}-{r['month']}" for r in data if r.get("export_amt", 0) != 0 or r.get("import_amt", 0) != 0}


def upload(item_id: int, rows: list[dict]):
    if not rows:
        return 0
    resp = railway_post(f"/api/import/{item_id}", {"rows": rows})
    if resp.status_code == 200:
        return resp.json().get("imported", 0)
    print(f"  Upload error: {resp.status_code} {resp.text[:200]}")
    return 0


def fetch_kita_month(item, year_str, month_str):
    """Run a single KITA fetch in a fresh event loop to avoid stale async state."""
    async def _fetch():
        if item["region_type"] == "0":
            from kita_client import fetch_industry_month
            return await fetch_industry_month(year_str, month_str, item["item_code"], item["item_type"])
        else:
            from kita_client import fetch_region_month
            return await fetch_region_month(
                year_str, month_str, item["item_code"],
                item.get("region_name", ""), item["item_type"], item["region_type"],
            )
    return asyncio.run(_fetch())


def fetch_item(item: dict, year_from=YEAR_FROM, month_from=MONTH_FROM, year_to=YEAR_TO, month_to=MONTH_TO):
    item_id = item["id"]
    code = item["item_code"]
    label = item.get("label") or item.get("stock_name") or code

    skip = get_existing(item_id)
    print(f"[{item_id}] {label} — {len(skip)} months in DB, fetching {year_from}-{month_from:02d} to {year_to}-{month_to:02d}...")

    total = 0
    batch = []
    y, m = year_from, month_from
    try:
        while (y, m) <= (year_to, month_to):
            year_str = str(y)
            month_str = str(m).zfill(2)
            key = f"{year_str}-{month_str}"
            if key not in skip:
                row = None
                for attempt in range(3):
                    try:
                        row = fetch_kita_month(item, year_str, month_str)
                        break
                    except (httpx.ReadTimeout, httpx.ReadError, httpx.ConnectError) as e:
                        if attempt < 2:
                            wait = 15 * (attempt + 1)
                            print(f"  KITA timeout ({key}), retry {attempt+1} in {wait}s...")
                            time.sleep(wait)
                        else:
                            print(f"  KITA failed after 3 attempts ({key}): {e}")
                if row:
                    batch.append({"year": year_str, "month": month_str, **row})
            m += 1
            if m > 12:
                m = 1
                y += 1
                if batch:
                    count = upload(item_id, batch)
                    total += count
                    print(f"  {year_str}: uploaded {count} months (total: {total})", flush=True)
                    batch = []
    except RuntimeError as e:
        print(f"  Rate limit: {e}")

    if batch:
        count = upload(item_id, batch)
        total += count
        print(f"  final batch: uploaded {count} months (total: {total})", flush=True)

    if total == 0:
        print(f"  No new data")
    return total


def main():
    items = get_items()
    item_map = {i["id"]: i for i in items}

    year_from = YEAR_FROM
    target_ids = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--year-from" and i + 1 < len(sys.argv):
            year_from = int(sys.argv[i + 1])
            i += 2
        else:
            target_ids.append(int(sys.argv[i]))
            i += 1

    if not target_ids:
        for item in items:
            existing = get_existing(item["id"])
            if len(existing) == 0:
                target_ids.append(item["id"])
        print(f"Found {len(target_ids)} items with no data")

    total = 0
    for idx, item_id in enumerate(target_ids):
        item = item_map.get(item_id)
        if not item:
            print(f"[{item_id}] Not found, skipping")
            continue
        stats = get_daily_request_count()
        print(f"\n--- [{idx+1}/{len(target_ids)}] KITA requests today: {stats['count']}/{stats['limit']} ---")
        if stats["count"] >= stats["limit"] - 100:
            print("Approaching daily limit, stopping.")
            break
        try:
            count = fetch_item(item, year_from=year_from)
            total += count
        except Exception as e:
            print(f"  [!] Item {item_id} failed: {e}, continuing to next item...")

    print(f"\nDone! Total uploaded: {total} months")
    stats = get_daily_request_count()
    print(f"KITA requests today: {stats['count']}/{stats['limit']}")


if __name__ == "__main__":
    main()
