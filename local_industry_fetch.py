#!/usr/bin/env python3
"""Fetch industry export data from KITA locally and upload to Railway."""
import re
import json
import time
import random
import httpx

KITA_URL = "https://stat.kita.net/stat/kts/prod/ProdWholeListWorker.screen"
RAILWAY_BASE = "https://web-production-a69d3.up.railway.app"

INDUSTRIES = [
    (70, "133", "석유제품"),
    (71, "613", "철강판"),
    (72, "746", "선박해양구조물"),
    (73, "214", "합성수지"),
    (74, "835", "이차전지"),
    (75, "836", "평판디스플레이"),
    (76, "227", "화장품"),
    (77, "812", "무선통신기기"),
]

YEAR_FROM, MONTH_FROM = 2020, 1
YEAR_TO, MONTH_TO = 2026, 2


def build_params(item_code: str, year: str, month: str, region_type: str = "0"):
    return {
        "event_udap": "Search",
        "searchType": "SHEET",
        "sheet_col_length": "14",
        "pageNum": "1",
        "p_prod_cd": "",
        "p_prod_nm": "",
        "viewType": "SHEET",
        "chartType": "bar",
        "chartDelay": "",
        "p_field": "금액",
        "p_measure": "1000",
        "s_url": "/stat/kts/prod/ProdWholeList",
        "p_cond_in_gb": region_type,
        "s_item_type": "MTI",
        "s_item_value": item_code,
        "CTR_GB": "KTS",
        "HS_YN": "Y",
        "MTI_YN": "Y",
        "SITC_YN": "Y",
        "s_item_name": "",
        "H_QTY_UNIT": "",
        "stat_yn": "Y",
        "s_year": year,
        "s_month": month,
        "s_field": "AMT",
        "s_monthsum_gb": "1",
        "s_measure": "1000",
        "s_sort": "KOR_NAME",
        "s_sort_val": "ASC",
        "listCount": "300",
        "editpage0": "",
        "pie_legend": "Exp",
    }


def parse_total(body: str):
    """Parse 총계 row from KITA response."""
    for m in re.finditer(r"<TR>([\s\S]*?)</TR>", body):
        cells = re.findall(r"<TD[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</TD>", m.group(1))
        if len(cells) >= 14 and cells[3].strip() == "총계":
            return {
                "export_amt": int(cells[9]) if cells[9] else 0,
                "export_rate": float(cells[10]) if cells[10] else 0.0,
                "import_amt": int(cells[11]) if cells[11] else 0,
                "import_rate": float(cells[12]) if cells[12] else 0.0,
                "balance": int(cells[13]) if cells[13] else 0,
            }
    return None


def fetch_one_month(client: httpx.Client, item_code: str, year: str, month: str):
    """Fetch one month, trying region_type=0 then fallback to 2."""
    for region_type in ["0", "2"]:
        for attempt in range(2):
            try:
                resp = client.post(KITA_URL, data=build_params(item_code, year, month, region_type), timeout=30)
                body = resp.text
                is_blocked = (
                    resp.status_code != 200
                    or "wait_default" in body
                    or "접속량이 많아" in body
                    or "TRACER" in body
                    or "showWaitPage" in body
                )
                if is_blocked:
                    print(f"    BLOCKED (attempt {attempt+1}), waiting...")
                    time.sleep(30 + random.uniform(5, 15))
                    continue
                total = parse_total(body)
                if total:
                    return total
            except Exception as e:
                print(f"    Error: {e}")
                time.sleep(10)
        # Pause before trying fallback region_type
        time.sleep(random.uniform(3, 5))
    return None


def get_existing_months(item_id: int) -> set:
    """Get set of existing months from Railway."""
    resp = httpx.get(f"{RAILWAY_BASE}/api/data/{item_id}", timeout=15)
    data = resp.json()
    return {f"{r['year']}-{r['month']}" for r in data if r.get("export_amt", 0) != 0}


def upload_rows(item_id: int, rows: list):
    """Upload rows to Railway import API."""
    if not rows:
        return 0
    resp = httpx.post(
        f"{RAILWAY_BASE}/api/import/{item_id}",
        json={"rows": rows},
        timeout=30,
    )
    result = resp.json()
    return result.get("imported", 0)


def generate_months():
    """Generate (year, month) tuples for the range."""
    y, m = YEAR_FROM, MONTH_FROM
    while (y, m) <= (YEAR_TO, MONTH_TO):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def main():
    for item_id, mti_code, name in INDUSTRIES:
        print(f"\n{'='*50}")
        print(f"Fetching {name} (ID {item_id}, MTI {mti_code})")

        existing = get_existing_months(item_id)
        print(f"  Existing: {len(existing)} months")

        months_to_fetch = []
        for y, m in generate_months():
            key = f"{y}-{m:02d}"
            if key not in existing:
                months_to_fetch.append((y, m))

        if not months_to_fetch:
            print(f"  All months present, skipping!")
            continue

        print(f"  Need to fetch: {len(months_to_fetch)} months")

        batch = []
        fetched = 0
        client = httpx.Client(follow_redirects=True)

        for y, m in months_to_fetch:
            year_str = str(y)
            month_str = f"{m:02d}"
            print(f"  {year_str}-{month_str}...", end=" ", flush=True)

            data = fetch_one_month(client, mti_code, year_str, month_str)
            if data:
                row = {"year": year_str, "month": month_str, **data}
                batch.append(row)
                fetched += 1
                print(f"export={data['export_amt']:,}")
            else:
                print("no data")

            # Upload in batches of 12
            if len(batch) >= 12:
                n = upload_rows(item_id, batch)
                print(f"  -> Uploaded {n} rows to Railway")
                batch = []

            # Polite delay
            time.sleep(random.uniform(4, 7))

        # Upload remaining
        if batch:
            n = upload_rows(item_id, batch)
            print(f"  -> Uploaded {n} rows to Railway")

        client.close()
        print(f"  Done: {fetched} new months fetched")

        # Extra pause between industries
        time.sleep(random.uniform(5, 10))

    print("\n\nAll done!")


if __name__ == "__main__":
    main()
