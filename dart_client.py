"""
OpenDART disclosure client (trading-trend auto ingest)
"""

import asyncio
import datetime as dt
import io
import re
import zipfile
from typing import Dict, List

import httpx
import requests

BASE_URL = "https://opendart.fss.or.kr/api"
TIMEOUT = 60
LIST_CONCURRENCY = 3
DETAIL_CONCURRENCY = 3
MAX_RETRIES = 8
PAGE_FETCH_DELAY = 0.7  # seconds between page batches to avoid overwhelming DART API

# Reports that are likely related to insider/related-party holdings changes.
INSIDER_REPORT_KEYWORDS = [
    "임원ㆍ주요주주 특정증권등 소유상황보고서",
    "임원ㆍ주요주주특정증권등소유상황보고서",
    "주식등의 대량보유 상황보고서",
    "주식등의대량보유상황보고서",
    "대량보유 상황보고서",
    "대량보유상황보고서",
]

# Text that usually implies acquisition/buy-side activity.
BUY_SIDE_HINTS = ["매수", "취득", "신규", "증가", "장내매수", "시간외매수"]
SELL_SIDE_HINTS = ["매도", "감소", "처분", "해지", "종결", "전량 매도"]


def _to_int(v) -> int:
    try:
        return int(float(str(v).replace(",", "").strip()))
    except Exception:
        return 0


def _to_float(v) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return 0.0


def _is_insider_related_report(name: str) -> bool:
    n = (name or "").replace(" ", "")
    for kw in INSIDER_REPORT_KEYWORDS:
        if kw.replace(" ", "") in n:
            return True
    return False


def _contains_buy_hint(text: str) -> bool:
    t = text or ""
    return any(h in t for h in BUY_SIDE_HINTS)


def _contains_sell_hint(text: str) -> bool:
    t = text or ""
    return any(h in t for h in SELL_SIDE_HINTS)


async def _gather_limited(coros, limit: int):
    semaphore = asyncio.Semaphore(max(1, int(limit)))

    async def _runner(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(_runner(coro) for coro in coros))


async def _request_json_with_retries(client: httpx.AsyncClient, url: str, params: Dict) -> Dict:
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await asyncio.to_thread(requests.get, url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            if attempt + 1 >= MAX_RETRIES:
                break
            delay = min(2 ** (attempt + 1), 60)
            await asyncio.sleep(delay)
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt + 1 >= MAX_RETRIES:
                break
            delay = min(2 ** attempt, 30)
            await asyncio.sleep(delay)
    raise last_error or RuntimeError("JSON 요청 실패")


async def _request_bytes_with_retries(client: httpx.AsyncClient, url: str, params: Dict) -> bytes:
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await asyncio.to_thread(requests.get, url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.content or b""
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            if attempt + 1 >= MAX_RETRIES:
                break
            delay = min(2 ** (attempt + 1), 60)
            await asyncio.sleep(delay)
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 >= MAX_RETRIES:
                break
            delay = min(2 ** attempt, 30)
            await asyncio.sleep(delay)
    raise last_error or RuntimeError("바이너리 요청 실패")


async def _fetch_majorstock_rows(client: httpx.AsyncClient, api_key: str, corp_code: str) -> List[Dict]:
    params = {"crtfc_key": api_key, "corp_code": corp_code}
    payload = await _request_json_with_retries(client, f"{BASE_URL}/majorstock.json", params)
    if str(payload.get("status", "")) not in {"000", "013"}:
        return []
    return payload.get("list", []) or []


async def _fetch_document_xml(client: httpx.AsyncClient, api_key: str, rcept_no: str) -> str:
    params = {"crtfc_key": api_key, "rcept_no": str(rcept_no)}
    content = await _request_bytes_with_retries(client, f"{BASE_URL}/document.xml", params)
    if not content.startswith(b"PK"):
        return ""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".xml"):
                try:
                    return zf.read(name).decode("utf-8")
                except Exception:
                    return zf.read(name).decode("utf-8", errors="ignore")
    return ""


def _extract_insider_values_from_document(raw_xml: str) -> Dict:
    text = raw_xml or ""
    if "임원ㆍ주요주주 특정증권등 소유상황보고서" not in text and "임원ㆍ주요주주특정증권등소유상황보고서" not in text:
        return {}

    def _pick(pattern: str, cast=int, default=0):
        m = re.search(pattern, text, re.S)
        if not m:
            return default
        raw = (m.group(1) or "").replace(",", "").strip()
        try:
            return cast(raw)
        except Exception:
            return default

    def _pick_text(pattern: str) -> str:
        m = re.search(pattern, text, re.S)
        return (m.group(1).strip() if m else "")

    change_shares = _pick(r'ACODE="MDF_STK_CNT"[^>]*>\s*([0-9,]+)\s*<')
    before_shares = _pick(r'ACODE="BFR_STK_CNT"[^>]*>\s*([0-9,]+)\s*<')
    after_shares = _pick(r'ACODE="AFR_STK_CNT"[^>]*>\s*([0-9,]+)\s*<')
    avg_price = _pick(r'ACODE="ACI_AMT2"[^>]*>\s*([0-9,]+)\s*<', cast=float, default=0.0)
    reason = _pick_text(r'AUNIT="RPT_RSN"[^>]*>\s*([^<]+)\s*<')
    party = _pick_text(r'ACODE="IFR_NM"[^>]*>\s*([^<]+)\s*<').replace(" ", "")
    change_ratio = _pick(r'ACODE="MDF_UN_RT"[^>]*>\s*([0-9.,-]+)\s*<', cast=float, default=0.0)

    if change_shares <= 0 and after_shares > before_shares:
        change_shares = after_shares - before_shares
    if not reason and change_shares > 0:
        reason = "문서기반 변동"

    return {
        "related_party": party,
        "change_shares": int(change_shares),
        "change_ratio": float(change_ratio),
        "avg_price": float(avg_price),
        "reason": reason,
    }


async def fetch_trading_trend_candidates(
    api_key: str,
    days: int = 14,
    page_count: int = 20,
) -> List[Dict]:
    """
    Fetch recent DART disclosures and extract insider buy candidates.

    It enriches each candidate with share/ratio deltas from majorstock endpoint,
    then keeps buy-side records only.
    """
    days = max(1, min(int(days), 90))
    end_de = dt.date.today()
    bgn_de = end_de - dt.timedelta(days=days)

    base_params = {
        "crtfc_key": api_key,
        "bgn_de": bgn_de.strftime("%Y%m%d"),
        "end_de": end_de.strftime("%Y%m%d"),
        "page_count": str(max(10, min(int(page_count), 30))),
        "pblntf_ty": "D",
    }

    raw_items: List[Dict] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        first_payload = await _request_json_with_retries(client, f"{BASE_URL}/list.json", {**base_params, "page_no": "1"})

        status = str(first_payload.get("status", ""))
        if status not in {"000", "013"}:
            msg = first_payload.get("message", "DART API 오류")
            raise RuntimeError(f"DART list 조회 실패({status}): {msg}")

        raw_items.extend(first_payload.get("list", []) or [])

        total_page = int(first_payload.get("total_page") or 1)
        # Fetch remaining pages in small batches with delay to avoid overwhelming DART API
        for batch_start in range(2, total_page + 1, LIST_CONCURRENCY):
            batch_end = min(batch_start + LIST_CONCURRENCY, total_page + 1)
            batch_coros = [
                _request_json_with_retries(client, f"{BASE_URL}/list.json", {**base_params, "page_no": str(p)})
                for p in range(batch_start, batch_end)
            ]
            for payload in await asyncio.gather(*batch_coros):
                if str(payload.get("status", "")) not in {"000", "013"}:
                    continue
                raw_items.extend(payload.get("list", []) or [])
            if batch_end <= total_page:
                await asyncio.sleep(PAGE_FETCH_DELAY)
        items = [it for it in raw_items if _is_insider_related_report(it.get("report_nm", ""))]

        corp_codes = sorted({it.get("corp_code", "") for it in items if it.get("corp_code")})
        majorstock_by_corp: Dict[str, Dict[str, List[Dict]]] = {}
        majorstock_coros = [_fetch_majorstock_rows(client, api_key, corp) for corp in corp_codes]
        for corp, rows in zip(corp_codes, await _gather_limited(majorstock_coros, DETAIL_CONCURRENCY)):
            rmap: Dict[str, List[Dict]] = {}
            for r in rows:
                rmap.setdefault(r.get("rcept_no", ""), []).append(r)
            majorstock_by_corp[corp] = rmap

        insider_rcepts = sorted({
            it.get("rcept_no", "")
            for it in items
            if it.get("rcept_no")
            and "임원ㆍ주요주주" in (it.get("report_nm", ""))
            and not majorstock_by_corp.get(it.get("corp_code", ""), {}).get(it.get("rcept_no", ""))
        })
        insider_doc_map: Dict[str, Dict] = {}
        doc_coros = [_fetch_document_xml(client, api_key, rcept_no) for rcept_no in insider_rcepts]
        for rcept_no, raw_xml in zip(insider_rcepts, await _gather_limited(doc_coros, DETAIL_CONCURRENCY)):
            parsed = _extract_insider_values_from_document(raw_xml)
            if parsed:
                insider_doc_map[rcept_no] = parsed

        out: List[Dict] = []
        for it in items:
            report_name = it.get("report_nm", "")
            rcept_no = it.get("rcept_no", "")
            rcept_dt = it.get("rcept_dt", "")
            corp_code = it.get("corp_code", "")

            if len(rcept_dt) == 8:
                trade_date = f"{rcept_dt[0:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}"
            else:
                trade_date = dt.date.today().isoformat()

            source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}" if rcept_no else ""

            related_party = it.get("flr_nm", "") or "공시제출인"
            change_shares = 0
            change_ratio = 0.0
            avg_price = 0.0
            relation_type = "특수관계인/주요주주"
            reason = ""

            mrows = majorstock_by_corp.get(corp_code, {}).get(rcept_no, [])
            if mrows:
                pick = None
                for r in mrows:
                    if (r.get("repror") or "") == related_party:
                        pick = r
                        break
                if pick is None:
                    pick = mrows[0]

                related_party = pick.get("repror") or related_party
                change_shares = _to_int(pick.get("stkqy_irds", 0))
                change_ratio = round(_to_float(pick.get("stkrt_irds", 0)), 4)
                reason = pick.get("report_resn", "") or ""
            elif "임원ㆍ주요주주" in report_name:
                parsed = insider_doc_map.get(rcept_no, {})
                if parsed:
                    related_party = parsed.get("related_party") or related_party
                    change_shares = _to_int(parsed.get("change_shares", 0))
                    change_ratio = round(_to_float(parsed.get("change_ratio", 0)), 4)
                    avg_price = _to_float(parsed.get("avg_price", 0))
                    reason = parsed.get("reason", "") or ""

            buy_from_qty = change_shares > 0
            buy_from_text = _contains_buy_hint(report_name) or _contains_buy_hint(reason)
            sell_from_text = _contains_sell_hint(report_name) or _contains_sell_hint(reason)

            if not buy_from_qty:
                if not buy_from_text or sell_from_text:
                    continue

            note = "자동수집(DART): 수치 자동채움"
            if reason:
                note += f" | 사유: {reason.strip()[:120]}"
            elif not buy_from_qty:
                note += " | 수치 미확인(텍스트 기준 매수 후보)"

            out.append({
                "trade_date": trade_date,
                "company_name": it.get("corp_name", ""),
                "stock_code": it.get("stock_code", "") or "",
                "related_party": related_party,
                "relation_type": relation_type,
                "change_shares": change_shares,
                "change_ratio": change_ratio,
                "avg_price": avg_price,
                "amount_krw": avg_price * change_shares if change_shares > 0 else 0,
                "source_title": report_name,
                "source_url": source_url,
                "note": note,
            })

    out.sort(key=lambda x: (x.get("trade_date", ""), x.get("company_name", "")), reverse=True)
    return out
