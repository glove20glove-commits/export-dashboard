#!/usr/bin/env python3
"""Fetch tourism data locally and upload to Railway.

Usage:
    python3 -u local_tourism_fetch.py [year_from] [year_to]

Example:
    python3 -u local_tourism_fetch.py 2020 2026
"""

import asyncio
import sys
import time
import httpx

# Import tourism client
sys.path.insert(0, ".")
from tourism_client import fetch_tourism_month

RAILWAY_URL = "https://web-production-a69d3.up.railway.app"
DELAY = 4  # seconds between requests (conservative)


async def get_countries():
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{RAILWAY_URL}/api/tourism/countries")
        return resp.json()


async def upload_data(country_id: int, rows: list[dict]):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RAILWAY_URL}/api/tourism/import/{country_id}",
            json={"rows": rows},
        )
        return resp.json()


async def main():
    year_from = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    year_to = int(sys.argv[2]) if len(sys.argv) > 2 else 2026

    countries = await get_countries()
    if not countries:
        print("No countries registered. Run init-top10 first.")
        return

    name_to_id = {c["nat_nm"]: c["id"] for c in countries}
    print(f"Tracked countries: {', '.join(name_to_id.keys())}")
    print(f"Fetching {year_from}-01 ~ {year_to}-12")
    print(f"Delay: {DELAY}s between requests")
    print()

    total_uploaded = 0
    y, m = year_from, 1

    while (y, m) <= (year_to, 12):
        ym = f"{y}-{str(m).zfill(2)}"
        print(f"[{ym}] Fetching...", end=" ", flush=True)

        try:
            rows = await fetch_tourism_month(str(y), str(m).zfill(2))
        except Exception as e:
            print(f"ERROR: {e}")
            print(f"  Waiting 30s and retrying...")
            await asyncio.sleep(30)
            try:
                rows = await fetch_tourism_month(str(y), str(m).zfill(2))
            except Exception as e2:
                print(f"  Retry failed: {e2}, skipping.")
                m += 1
                if m > 12:
                    m = 1; y += 1
                continue

        if not rows:
            print(f"no data")
        else:
            # Group by country and upload
            month_count = 0
            for nat_nm, cid in name_to_id.items():
                for row in rows:
                    if row["nat_nm"] == nat_nm:
                        upload_rows = [{
                            "year": str(y),
                            "month": str(m).zfill(2),
                            "visitors": row["visitors"],
                            "prev_visitors": row["prev_visitors"],
                            "change_rate": row["change_rate"],
                        }]
                        await upload_data(cid, upload_rows)
                        month_count += 1
                        break
            total_uploaded += month_count
            print(f"{month_count} countries uploaded (total: {total_uploaded})")

        m += 1
        if m > 12:
            m = 1; y += 1

        # Rate limit
        await asyncio.sleep(DELAY)

    print(f"\nDone! Total records uploaded: {total_uploaded}")


if __name__ == "__main__":
    asyncio.run(main())
