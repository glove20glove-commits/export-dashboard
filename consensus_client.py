import re
import httpx

WISEREPORT_PAGE = "https://navercomp.wisereport.co.kr/v2/company/c1030001.aspx?cmp_cd={code}"
WISEREPORT_API = "https://navercomp.wisereport.co.kr/v2/company/cF3002.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


async def _get_encparam(client: httpx.AsyncClient, stock_code: str) -> str:
    """Fetch the main page to extract the encparam token."""
    resp = await client.get(
        WISEREPORT_PAGE.format(code=stock_code),
        headers=HEADERS,
    )
    resp.raise_for_status()
    match = re.search(r"encparam:\s*'([^']+)'", resp.text)
    return match.group(1) if match else ""


async def _fetch_financial_data(client: httpx.AsyncClient, stock_code: str, encparam: str, frq: str = "0") -> dict:
    """Fetch financial data JSON from WiseReport.
    frq=0: annual, frq=1: quarterly
    """
    frq_typ = "1" if frq == "1" else "0"
    params = {
        "cmp_cd": stock_code,
        "frq": frq,
        "rpt": "",
        "finGubun": "MAIN",
        "frqTyp": frq_typ,
        "cn": "",
        "encparam": encparam,
    }
    resp = await client.get(
        WISEREPORT_API,
        params=params,
        headers={
            **HEADERS,
            "Referer": WISEREPORT_PAGE.format(code=stock_code),
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    resp.raise_for_status()
    return resp.json()


def _parse_period(period_str: str) -> tuple[str, bool]:
    """Parse period string like '2024/12 (IFRS연결)' or '2026/12(E) (IFRS연결)'.
    Returns (period_label, is_estimate).
    """
    is_estimate = "(E)" in period_str
    # Extract year/month
    match = re.match(r"(\d{4})/(\d{2})", period_str)
    if not match:
        return period_str, is_estimate
    year = match.group(1)
    month = match.group(2)
    return year, is_estimate


def _parse_quarterly_period(period_str: str) -> tuple[str, bool]:
    """Parse quarterly period like '2024/03 (IFRS연결)' or '2025/06(E)'.
    Returns (label like '2024Q1', is_estimate).
    """
    is_estimate = "(E)" in period_str
    match = re.match(r"(\d{4})/(\d{2})", period_str)
    if not match:
        return period_str, is_estimate
    year = match.group(1)
    month = int(match.group(2))
    quarter = (month - 1) // 3 + 1
    return f"{year}Q{quarter}", is_estimate


def _extract_items(data: dict, period_type: str) -> list[dict]:
    """Extract financial items from WiseReport JSON response."""
    periods_raw = data.get("YYMM", [])
    items_data = data.get("DATA", [])

    # Map account names
    acc_map = {
        "매출액": "revenue",
        "매출액(수익)": "revenue",
        "영업이익": "operating_profit",
        "당기순이익": "net_income",
        "*주당순이익": "eps",
        "*(지배주주지분)주당순이익": "eps",
    }

    # Parse periods (skip the last 2 which are YoY columns)
    periods = []
    for p in periods_raw:
        p_clean = p.replace("<br />", " ").strip()
        if "전년대비" in p_clean or "전분기대비" in p_clean or "전년동기대비" in p_clean:
            continue
        if period_type == "annual":
            label, is_est = _parse_period(p_clean)
        else:
            label, is_est = _parse_quarterly_period(p_clean)
        periods.append({"label": label, "is_estimate": is_est})

    # Build result per period
    results = {}
    for p in periods:
        results[p["label"]] = {
            "period_type": period_type,
            "period": p["label"],
            "is_estimate": 1 if p["is_estimate"] else 0,
            "revenue": None,
            "operating_profit": None,
            "net_income": None,
            "eps": None,
            "per": None,
        }

    for item in items_data:
        acc_name = item.get("ACC_NM", "").strip().strip(".")
        field = acc_map.get(acc_name)
        if not field:
            continue

        for i, p in enumerate(periods):
            data_key = f"DATA{i + 1}"
            val = item.get(data_key)
            if val is not None and p["label"] in results:
                results[p["label"]][field] = val

    return list(results.values())


async def fetch_consensus(stock_code: str) -> list[dict]:
    """Fetch consensus data (annual + quarterly) for a stock from NaverComp WiseReport.
    Returns list of dicts with period_type, period, revenue, operating_profit, net_income, eps, per, is_estimate.
    """
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        encparam = await _get_encparam(client, stock_code)
        if not encparam:
            return []

        results = []

        # Annual data
        try:
            annual_data = await _fetch_financial_data(client, stock_code, encparam, frq="0")
            results.extend(_extract_items(annual_data, "annual"))
        except Exception as e:
            print(f"[consensus] Annual fetch error for {stock_code}: {e}")

        # Quarterly data
        try:
            quarterly_data = await _fetch_financial_data(client, stock_code, encparam, frq="1")
            results.extend(_extract_items(quarterly_data, "quarterly"))
        except Exception as e:
            print(f"[consensus] Quarterly fetch error for {stock_code}: {e}")

    return results
