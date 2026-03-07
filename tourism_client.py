"""Client for fetching visitor data from Korea Tourism Data Lab (datalab.visitkorea.or.kr)."""

import asyncio
import httpx

DATALAB_URL = "https://datalab.visitkorea.or.kr/visualize/getGridData.do"
COUNTRY_LIST_URL = "https://datalab.visitkorea.or.kr/datalab/portal/cvd/getCvdSittnNatList.do"
HEADERS = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
REQUEST_DELAY = 2  # seconds between requests

# Fallback country list (22 countries from Data Lab, rarely changes)
FALLBACK_COUNTRIES = [
    {"nat_cd": "TW", "nat_nm": "대만", "tar_cd": "158"},
    {"nat_cd": "DE", "nat_nm": "독일", "tar_cd": "276"},
    {"nat_cd": "RU", "nat_nm": "러시아", "tar_cd": "643"},
    {"nat_cd": "MY", "nat_nm": "말레이시아", "tar_cd": "458"},
    {"nat_cd": "MN", "nat_nm": "몽골", "tar_cd": "496"},
    {"nat_cd": "US", "nat_nm": "미국", "tar_cd": "840"},
    {"nat_cd": "VN", "nat_nm": "베트남", "tar_cd": "704"},
    {"nat_cd": "SG", "nat_nm": "싱가포르", "tar_cd": "702"},
    {"nat_cd": "AE", "nat_nm": "아랍에미리트", "tar_cd": "784"},
    {"nat_cd": "GB", "nat_nm": "영국", "tar_cd": "826"},
    {"nat_cd": "IN", "nat_nm": "인도", "tar_cd": "356"},
    {"nat_cd": "ID", "nat_nm": "인도네시아", "tar_cd": "360"},
    {"nat_cd": "JP", "nat_nm": "일본", "tar_cd": "392"},
    {"nat_cd": "CN", "nat_nm": "중국", "tar_cd": "156"},
    {"nat_cd": "KZ", "nat_nm": "카자흐스탄", "tar_cd": "398"},
    {"nat_cd": "CA", "nat_nm": "캐나다", "tar_cd": "124"},
    {"nat_cd": "TH", "nat_nm": "태국", "tar_cd": "764"},
    {"nat_cd": "TR", "nat_nm": "튀르키예", "tar_cd": "792"},
    {"nat_cd": "FR", "nat_nm": "프랑스", "tar_cd": "250"},
    {"nat_cd": "PH", "nat_nm": "필리핀", "tar_cd": "608"},
    {"nat_cd": "AU", "nat_nm": "호주", "tar_cd": "036"},
    {"nat_cd": "HK", "nat_nm": "홍콩", "tar_cd": "344"},
]


async def fetch_country_list() -> list[dict]:
    """Fetch list of 22 major countries from Data Lab, with hardcoded fallback."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            await client.get("https://datalab.visitkorea.or.kr/datalab/portal/main/getMainForm.do")
            resp = await client.post(COUNTRY_LIST_URL, headers=HEADERS)
            if resp.status_code != 200 or "text/html" in resp.headers.get("content-type", ""):
                raise RuntimeError("non-JSON response")
            data = resp.json()
            result = [
                {"nat_cd": r["natCd"], "nat_nm": r["natNm"], "tar_cd": r.get("tarCd", "")}
                for r in data.get("list", [])
            ]
            if result:
                return result
    except Exception as e:
        print(f"[tourism] Data Lab country list failed ({e}), using fallback")
    return list(FALLBACK_COUNTRIES)


async def fetch_tourism_month(year: str, month: str) -> list[dict]:
    """Fetch one month of visitor data for all countries.

    Returns list of dicts with keys: nat_nm, visitors, prev_visitors, change_rate
    """
    ym = f"{year}{month.zfill(2)}"
    params = {
        "adminYn": "",
        "BASE_YM1": ym,
        "BASE_YM2": ym,
        "srchAreaDate": "1",
        "qid": "TS_01_16_005_New",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(DATALAB_URL, data=params, headers=HEADERS)
        data = resp.json()

    results = []
    for row in data.get("list", []):
        if row.get("SEX_CD") != "전체" or row.get("R_LEV") != "3":
            continue
        results.append({
            "nat_nm": row["NAT_NM"],
            "visitors": int(row.get("QTY", 0)),
            "prev_visitors": int(row.get("PRE_QTY", 0)),
            "change_rate": float(row.get("C_RATE", 0)),
        })
    return results


async def fetch_tourism_range(
    year_from: int, month_from: int,
    year_to: int, month_to: int,
    country_name: str,
    skip_months: set | None = None,
) -> list[dict]:
    """Fetch a range of months for a specific country.

    Returns list of dicts with keys: year, month, visitors, prev_visitors, change_rate
    """
    results = []
    y, m = year_from, month_from
    while (y, m) <= (year_to, month_to):
        key = f"{y}-{m}"
        if skip_months and key in skip_months:
            m += 1
            if m > 12:
                m = 1; y += 1
            continue

        month_data = await fetch_tourism_month(str(y), str(m).zfill(2))
        for row in month_data:
            if row["nat_nm"] == country_name:
                results.append({
                    "year": str(y),
                    "month": str(m).zfill(2),
                    **row,
                })
                break

        await asyncio.sleep(REQUEST_DELAY)
        m += 1
        if m > 12:
            m = 1; y += 1

    return results


async def fetch_all_countries_month(year: str, month: str) -> list[dict]:
    """Fetch one month of data for ALL countries at once (single API call).

    Returns list of dicts with keys: nat_nm, year, month, visitors, prev_visitors, change_rate
    """
    rows = await fetch_tourism_month(year, month)
    for r in rows:
        r["year"] = year
        r["month"] = month.zfill(2)
    return rows
