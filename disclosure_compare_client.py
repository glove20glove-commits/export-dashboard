"""
OpenDART periodic disclosure compare client.
"""

import datetime as dt
import html
import io
import re
import zipfile
from difflib import SequenceMatcher
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET

import httpx

BASE_URL = "https://opendart.fss.or.kr/api"
TIMEOUT = 30

REPORT_NAME_TO_CODE = {
    "사업보고서": "11011",
    "반기보고서": "11012",
    "분기보고서": "11013",
}
REPORT_CODE_TO_NAME = {v: k for k, v in REPORT_NAME_TO_CODE.items()}

_corp_cache: Dict[str, Dict] = {
    "loaded_at": None,
    "by_stock": {},
}


def _to_int(v) -> int:
    s = str(v or "").strip().replace(",", "")
    if not s or s == "-":
        return 0
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    try:
        n = int(float(s))
        return -n if neg else n
    except Exception:
        return 0


def _extract_bsns_year(report_nm: str, fallback_year: str) -> str:
    nm = report_nm or ""
    m = re.search(r"\((\d{4})\.\d{2}\)", nm)
    if m:
        return m.group(1)
    m = re.search(r"(20\d{2})", nm)
    if m:
        return m.group(1)
    return fallback_year


async def _ensure_corp_cache(api_key: str):
    loaded_at = _corp_cache.get("loaded_at")
    if loaded_at and (dt.datetime.now() - loaded_at).total_seconds() < 24 * 3600:
        return

    params = {"crtfc_key": api_key}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/corpCode.xml", params=params)
        resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        if not names:
            raise RuntimeError("corpCode.xml zip is empty")
        xml_bytes = zf.read(names[0])

    root = ET.fromstring(xml_bytes)
    by_stock: Dict[str, str] = {}
    for item in root.findall(".//list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        if re.match(r"^[0-9A-Z]{6}$", stock_code) and re.match(r"^\d{8}$", corp_code):
            by_stock[stock_code] = corp_code

    _corp_cache["loaded_at"] = dt.datetime.now()
    _corp_cache["by_stock"] = by_stock


async def get_corp_code_by_stock(api_key: str, stock_code: str) -> str:
    await _ensure_corp_cache(api_key)
    key = (stock_code or "").strip().upper()
    if len(key) < 6 and key.isdigit():
        key = key.zfill(6)
    return _corp_cache.get("by_stock", {}).get(key, "")


def _report_type_and_code(report_nm: str) -> Tuple[str, str]:
    nm = report_nm or ""
    for k, code in REPORT_NAME_TO_CODE.items():
        if k in nm:
            return k, code
    return "", ""


async def fetch_periodic_reports(api_key: str, corp_code: str, limit: int = 30) -> List[Dict]:
    end_de = dt.date.today().strftime("%Y%m%d")
    bgn_de = (dt.date.today() - dt.timedelta(days=3650)).strftime("%Y%m%d")

    rows: List[Dict] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for page_no in range(1, 6):
            params = {
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "pblntf_ty": "A",
                "page_count": "100",
                "page_no": str(page_no),
            }
            resp = await client.get(f"{BASE_URL}/list.json", params=params)
            resp.raise_for_status()
            payload = resp.json()
            status = str(payload.get("status", ""))
            if status not in {"000", "013"}:
                raise RuntimeError(f"DART list 조회 실패({status}): {payload.get('message', '')}")
            plist = payload.get("list", []) or []
            if not plist:
                break
            rows.extend(plist)
            if len(plist) < 100:
                break

    out: List[Dict] = []
    for r in rows:
        report_nm = r.get("report_nm", "")
        report_type, reprt_code = _report_type_and_code(report_nm)
        if not reprt_code:
            continue
        rcept_dt = (r.get("rcept_dt") or "").strip()
        bsns_year = _extract_bsns_year(report_nm, rcept_dt[:4] if len(rcept_dt) >= 4 else str(dt.date.today().year))
        out.append({
            "key": f"{bsns_year}|{reprt_code}|{(r.get('rcept_no') or '').strip()}",
            "rcept_no": (r.get("rcept_no") or "").strip(),
            "rcept_dt": rcept_dt,
            "report_nm": report_nm,
            "report_type": report_type,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
        })

    out.sort(key=lambda x: x.get("rcept_dt", ""), reverse=True)
    return out[: max(1, min(int(limit), 80))]


async def fetch_fnltt_rows(api_key: str, corp_code: str, bsns_year: str, reprt_code: str) -> List[Dict]:
    params_base = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": str(bsns_year),
        "reprt_code": str(reprt_code),
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for fs_div in ("CFS", "OFS"):
            params = {**params_base, "fs_div": fs_div}
            resp = await client.get(f"{BASE_URL}/fnlttSinglAcntAll.json", params=params)
            resp.raise_for_status()
            payload = resp.json()
            status = str(payload.get("status", ""))
            if status == "000":
                raw = payload.get("list", []) or []
                out: List[Dict] = []
                for row in raw:
                    sj_div = (row.get("sj_div") or "").strip()
                    account_nm = (row.get("account_nm") or "").strip()
                    if not account_nm:
                        continue
                    key = f"{sj_div}|{account_nm}"
                    out.append({
                        "key": key,
                        "sj_div": sj_div,
                        "account_nm": account_nm,
                        "amount": _to_int(row.get("thstrm_amount")),
                    })
                return out
            if status == "013":
                continue
            raise RuntimeError(f"재무데이터 조회 실패({status}): {payload.get('message', '')}")
    return []


def compare_fnltt_rows(left_rows: List[Dict], right_rows: List[Dict], max_changed: int = 200) -> Dict:
    left_map = {r["key"]: r for r in left_rows}
    right_map = {r["key"]: r for r in right_rows}
    keys = set(left_map.keys()) | set(right_map.keys())

    changed: List[Dict] = []
    only_left: List[Dict] = []
    only_right: List[Dict] = []

    for k in keys:
        l = left_map.get(k)
        r = right_map.get(k)
        if l and r:
            la = int(l.get("amount", 0))
            ra = int(r.get("amount", 0))
            if la != ra:
                diff = ra - la
                pct = None
                if la != 0:
                    pct = round((diff / abs(la)) * 100, 2)
                changed.append({
                    "sj_div": l.get("sj_div") or r.get("sj_div"),
                    "account_nm": l.get("account_nm") or r.get("account_nm"),
                    "left_amount": la,
                    "right_amount": ra,
                    "diff": diff,
                    "diff_pct": pct,
                })
        elif l:
            only_left.append({
                "sj_div": l.get("sj_div"),
                "account_nm": l.get("account_nm"),
                "amount": int(l.get("amount", 0)),
            })
        elif r:
            only_right.append({
                "sj_div": r.get("sj_div"),
                "account_nm": r.get("account_nm"),
                "amount": int(r.get("amount", 0)),
            })

    changed.sort(key=lambda x: abs(int(x.get("diff", 0))), reverse=True)
    only_left.sort(key=lambda x: abs(int(x.get("amount", 0))), reverse=True)
    only_right.sort(key=lambda x: abs(int(x.get("amount", 0))), reverse=True)

    return {
        "summary": {
            "changed_count": len(changed),
            "only_left_count": len(only_left),
            "only_right_count": len(only_right),
        },
        "changed": changed[:max_changed],
        "only_left": only_left[:100],
        "only_right": only_right[:100],
    }


def reprt_code_to_name(reprt_code: str) -> str:
    return REPORT_CODE_TO_NAME.get(str(reprt_code), str(reprt_code))


def _decode_bytes(b: bytes) -> str:
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="ignore")


def _strip_to_text(raw: str) -> str:
    s = raw or ""
    s = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", s)
    s = re.sub(r"(?i)</(p|div|li|tr|h1|h2|h3|h4|h5|h6|title)>", "\n", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    lines = []
    for ln in s.split("\n"):
        t = ln.strip()
        if not t:
            continue
        if len(t) < 8:
            continue
        if not re.search(r"[A-Za-z가-힣0-9]", t):
            continue
        lines.append(t)
    return "\n".join(lines)


def _split_units(text: str, unit: str) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []

    if unit == "sentence":
        parts = re.split(r"(?<=[\.\!\?])\s+|\n+", t)
        parts = [p.strip() for p in parts if p and p.strip()]
        # Korean filings often have weak sentence punctuation; fallback to short chunks.
        if len(parts) < 20:
            rough = []
            for p in re.split(r"\n+", t):
                p = p.strip()
                if not p:
                    continue
                if len(p) <= 120:
                    rough.append(p)
                else:
                    for i in range(0, len(p), 120):
                        rough.append(p[i:i + 120].strip())
            parts = [p for p in rough if p]
        return parts

    # paragraph(default)
    parts = [p.strip() for p in re.split(r"\n{2,}|\n", t) if p and p.strip()]
    return parts


async def fetch_disclosure_document_text(api_key: str, rcept_no: str) -> str:
    params = {"crtfc_key": api_key, "rcept_no": str(rcept_no)}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/document.xml", params=params)
        resp.raise_for_status()
        content = resp.content or b""

    if content.startswith(b"PK"):
        texts: List[str] = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                lower = name.lower()
                if not (lower.endswith(".xml") or lower.endswith(".xhtml") or lower.endswith(".html") or lower.endswith(".htm")):
                    continue
                raw = _decode_bytes(zf.read(name))
                txt = _strip_to_text(raw)
                if txt:
                    texts.append(txt)
        if not texts:
            raise RuntimeError("공시 원문에서 텍스트를 추출하지 못했습니다")
        return "\n".join(texts)

    raw = _decode_bytes(content)
    # DART error payloads are plain XML with status/message
    m_status = re.search(r"<status>\s*(\d+)\s*</status>", raw)
    if m_status and m_status.group(1) != "000":
        m_msg = re.search(r"<message>\s*([^<]+)\s*</message>", raw)
        msg = m_msg.group(1).strip() if m_msg else "document 조회 실패"
        raise RuntimeError(f"document 조회 실패({m_status.group(1)}): {msg}")
    txt = _strip_to_text(raw)
    if not txt:
        raise RuntimeError("공시 원문 텍스트가 비어 있습니다")
    return txt


def compare_document_text(left_text: str, right_text: str, unit: str = "paragraph", max_items: int | None = None) -> Dict:
    left_units = _split_units(left_text, unit)
    right_units = _split_units(right_text, unit)

    sm = SequenceMatcher(a=left_units, b=right_units, autojunk=False)
    rows: List[Dict] = []
    changed_count = 0
    added_count = 0
    removed_count = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            lseg = left_units[i1:i2]
            rseg = right_units[j1:j2]
            used_right = set()
            for ltxt in lseg:
                best_idx = -1
                best_score = 0.0
                for idx, rtxt in enumerate(rseg):
                    if idx in used_right:
                        continue
                    score = SequenceMatcher(a=ltxt, b=rtxt, autojunk=False).ratio()
                    if score > best_score:
                        best_score = score
                        best_idx = idx
                if best_idx >= 0 and best_score >= 0.35:
                    used_right.add(best_idx)
                    changed_count += 1
                    rows.append({
                        "kind": "changed",
                        "left_text": ltxt,
                        "right_text": rseg[best_idx],
                    })
                else:
                    removed_count += 1
                    rows.append({"kind": "removed", "left_text": ltxt, "right_text": ""})
            for idx, rtxt in enumerate(rseg):
                if idx in used_right:
                    continue
                added_count += 1
                rows.append({"kind": "added", "left_text": "", "right_text": rtxt})
        elif tag == "delete":
            for t in left_units[i1:i2]:
                removed_count += 1
                rows.append({"kind": "removed", "left_text": t, "right_text": ""})
        elif tag == "insert":
            for t in right_units[j1:j2]:
                added_count += 1
                rows.append({"kind": "added", "left_text": "", "right_text": t})

    out_rows = rows
    if isinstance(max_items, int) and max_items > 0:
        out_rows = rows[:max_items]

    return {
        "unit": unit,
        "summary": {
            "left_unit_count": len(left_units),
            "right_unit_count": len(right_units),
            "changed_count": changed_count,
            "added_count": added_count,
            "removed_count": removed_count,
            "diff_count": len(rows),
            "rendered_count": len(out_rows),
        },
        "rows": out_rows,
    }
