import re
import asyncio
import datetime
import random
import httpx

KITA_URL = "https://stat.kita.net/stat/kts/prod/ProdWholeListWorker.screen"

# --- Rate limiter: prevent ban ---
REQUEST_DELAY_MIN = 5      # minimum seconds between requests
REQUEST_DELAY_MAX = 10     # maximum seconds between requests
DAILY_LIMIT = 500          # conservative daily limit
_daily_count = 0
_daily_date = None
_consecutive_blocks = 0    # track consecutive blocked responses


def _random_delay() -> float:
    """Return a random delay between min and max to look more human."""
    return random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)


def _check_daily_limit():
    """Reset counter on new day, raise if limit reached."""
    global _daily_count, _daily_date
    today = datetime.date.today()
    if _daily_date != today:
        _daily_date = today
        _daily_count = 0
    if _daily_count >= DAILY_LIMIT:
        raise RuntimeError(f"KITA daily request limit reached ({DAILY_LIMIT}). Try again tomorrow.")
    _daily_count += 1


def _parse_row(row_content: str) -> list[str]:
    """Extract TD values from a TR row, handling CDATA."""
    return re.findall(r"<TD[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</TD>", row_content)


async def fetch_month(
    year: str,
    month: str,
    item_code: str,
    item_type: str = "HS",
    region_type: str = "3",
    region_name: str | None = None,
) -> list[dict]:
    """Fetch one month of KITA data for all regions. Returns list of region dicts."""
    # Strip type prefixes (e.g. "HSK851762" → "851762")
    clean_code = re.sub(r"^(HSK?|MTI|SITC)", "", item_code)
    params = {
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
        "s_item_type": item_type,
        "s_item_value": clean_code,
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

    global _consecutive_blocks
    _check_daily_limit()
    text = None
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.post(KITA_URL, data=params)
            body = resp.text
            # Detect all known block patterns
            is_blocked = (
                resp.status_code != 200
                or "wait_default" in body
                or "접속량이 많아" in body
                or "TRACER" in body
                or "showWaitPage" in body
            )
            if not is_blocked and "<TR>" in body:
                text = body
                _consecutive_blocks = 0
                break
            # Blocked — back off exponentially with jitter
            _consecutive_blocks += 1
            backoff = min(30 * (attempt + 1) + random.uniform(5, 15), 120)
            await asyncio.sleep(backoff)

    # Polite random delay after each request
    await asyncio.sleep(_random_delay())

    # If we keep getting blocked, slow down even more
    if _consecutive_blocks >= 3:
        await asyncio.sleep(random.uniform(20, 40))

    if text is None:
        return [], None

    results = []
    total_row = None
    for match in re.finditer(r"<TR>([\s\S]*?)</TR>", text):
        values = _parse_row(match.group(1))
        if len(values) < 14:
            continue
        name = values[3].strip()
        if not name:
            continue
        row = {
            "region_name": name,
            "export_amt": int(values[9]) if values[9] else 0,
            "export_rate": float(values[10]) if values[10] else 0.0,
            "import_amt": int(values[11]) if values[11] else 0,
            "import_rate": float(values[12]) if values[12] else 0.0,
            "balance": int(values[13]) if values[13] else 0,
        }
        if name == "총계":
            total_row = row
        else:
            results.append(row)

    return results, total_row


async def fetch_region_month(
    year: str,
    month: str,
    item_code: str,
    region_name: str,
    item_type: str = "HS",
    region_type: str = "3",
) -> dict | None:
    """Fetch one month of data for a specific region."""
    rows, _total = await fetch_month(year, month, item_code, item_type, region_type, region_name)
    norm = region_name.replace(" ", "")
    for row in rows:
        if row["region_name"].replace(" ", "") == norm:
            return row
    return None


async def fetch_industry_month(
    year: str,
    month: str,
    item_code: str,
    item_type: str = "HS",
) -> dict | None:
    """Fetch one month of industry-wide total data (no region filter)."""
    _rows, total = await fetch_month(year, month, item_code, item_type, region_type="0")
    if total:
        return total
    # Extra pause before fallback attempt
    await asyncio.sleep(random.uniform(3, 7))
    # Fallback: use region_type=2 (metropolitan) and take 총계 row
    _rows, total = await fetch_month(year, month, item_code, item_type, region_type="2")
    return total


async def fetch_industry_range(
    item_code: str,
    year_from: int,
    month_from: int,
    year_to: int,
    month_to: int,
    item_type: str = "HS",
    skip_months: set | None = None,
) -> list[dict]:
    """Fetch a range of months for industry-wide totals. skip_months: set of 'YYYY-MM' to skip."""
    results = []
    y, m = year_from, month_from
    while (y, m) <= (year_to, month_to):
        year_str = str(y)
        month_str = str(m).zfill(2)
        if skip_months and f"{year_str}-{month_str}" in skip_months:
            m += 1
            if m > 12:
                m = 1; y += 1
            continue
        row = await fetch_industry_month(year_str, month_str, item_code, item_type)
        if row:
            results.append({"year": year_str, "month": month_str, **row})
        m += 1
        if m > 12:
            m = 1
            y += 1
    return results


async def fetch_range(
    item_code: str,
    region_name: str,
    year_from: int,
    month_from: int,
    year_to: int,
    month_to: int,
    item_type: str = "HS",
    region_type: str = "3",
    skip_months: set | None = None,
) -> list[dict]:
    """Fetch a range of months for a specific region. skip_months: set of 'YYYY-MM' to skip."""
    results = []
    y, m = year_from, month_from
    while (y, m) <= (year_to, month_to):
        year_str = str(y)
        month_str = str(m).zfill(2)
        if skip_months and f"{year_str}-{month_str}" in skip_months:
            m += 1
            if m > 12:
                m = 1; y += 1
            continue
        row = await fetch_region_month(year_str, month_str, item_code, region_name, item_type, region_type)
        if row:
            results.append({"year": year_str, "month": month_str, **row})
        m += 1
        if m > 12:
            m = 1
            y += 1
    return results


def get_daily_request_count() -> dict:
    """Return current daily request stats."""
    return {"date": str(_daily_date), "count": _daily_count, "limit": DAILY_LIMIT}
