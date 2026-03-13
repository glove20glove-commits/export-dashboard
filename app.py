import asyncio
import datetime
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

try:
    import anthropic
    _anthropic_client = anthropic.Anthropic()
    SUMMARIZE_ENABLED = True
except Exception:
    _anthropic_client = None
    SUMMARIZE_ENABLED = False

try:
    from dashboard.db import (
        init_db, add_item, get_items, get_item, delete_item,
        upsert_trade_data, get_trade_data, get_yearly_summary, get_latest_month,
        upsert_stock_price, get_stock_prices, get_stock_info,
        upsert_quarterly_revenue, get_quarterly_revenue,
        add_company, get_companies, get_company, update_company, delete_company,
        add_visit, get_visits, get_all_visits, get_upcoming_visits, update_visit, delete_visit,
        get_pending_visit_alarms, mark_visit_alarm_sent,
        add_visit_material, add_text_material, get_visit_materials, get_visit_material, delete_visit_material,
        add_event, get_events, get_all_events, update_event, delete_event,
        get_pending_event_alarms, mark_event_alarm_sent,
        add_report, get_reports, get_report, update_report, delete_report,
        upsert_consensus, get_consensus,
        add_tourism_country, get_tourism_countries, get_tourism_country,
        delete_tourism_country, upsert_tourism_data, get_tourism_data, get_tourism_total,
        add_nps_company, get_nps_companies, get_nps_company, update_nps_company,
        delete_nps_company, upsert_nps_data, get_nps_data, get_nps_overview,
        upsert_market_index, get_market_index, upsert_market_export, get_market_export,
        add_youtube_channel, get_youtube_channels, get_youtube_channel,
        delete_youtube_channel, update_youtube_channel,
        upsert_youtube_video, get_youtube_videos, get_known_video_ids,
        mark_youtube_video_notified, update_youtube_video_summary,
        add_blog_feed, get_blog_feeds, get_blog_feed, update_blog_feed, delete_blog_feed,
        upsert_blog_article, get_blog_articles, get_blog_article, update_blog_article_summary,
        get_known_blog_guids,
    )
    from dashboard.kita_client import fetch_range, fetch_region_month, fetch_industry_range, fetch_industry_month, get_daily_request_count
    from dashboard.stock_client import fetch_stock_prices, fetch_daily_stock_prices, search_stock_by_name, fetch_index_prices
    from dashboard.carbon_client import fetch_carbon_prices, fetch_all_carbon_items
    from dashboard.tourism_client import fetch_country_list, fetch_all_countries_month, fetch_tourism_range
    from dashboard.nps_client import search_company as nps_search, fetch_nps_data
    from dashboard.notifier import notify_update, notify_visit_update_sync, send_telegram
    from dashboard.youtube_client import resolve_channel, fetch_latest_videos
    from dashboard.blog_client import discover_feed, fetch_articles_rss, fetch_articles_scrape, fetch_article_content
except ImportError:
    from db import (
        init_db, add_item, get_items, get_item, delete_item,
        upsert_trade_data, get_trade_data, get_yearly_summary, get_latest_month,
        upsert_stock_price, get_stock_prices, get_stock_info,
        upsert_quarterly_revenue, get_quarterly_revenue,
        add_company, get_companies, get_company, update_company, delete_company,
        add_visit, get_visits, get_all_visits, get_upcoming_visits, update_visit, delete_visit,
        get_pending_visit_alarms, mark_visit_alarm_sent,
        add_visit_material, add_text_material, get_visit_materials, get_visit_material, delete_visit_material,
        add_event, get_events, get_all_events, update_event, delete_event,
        get_pending_event_alarms, mark_event_alarm_sent,
        add_report, get_reports, get_report, update_report, delete_report,
        upsert_consensus, get_consensus,
        add_tourism_country, get_tourism_countries, get_tourism_country,
        delete_tourism_country, upsert_tourism_data, get_tourism_data, get_tourism_total,
        add_nps_company, get_nps_companies, get_nps_company, update_nps_company,
        delete_nps_company, upsert_nps_data, get_nps_data, get_nps_overview,
        upsert_market_index, get_market_index, upsert_market_export, get_market_export,
        add_youtube_channel, get_youtube_channels, get_youtube_channel,
        delete_youtube_channel, update_youtube_channel,
        upsert_youtube_video, get_youtube_videos, get_known_video_ids,
        mark_youtube_video_notified, update_youtube_video_summary,
        add_blog_feed, get_blog_feeds, get_blog_feed, update_blog_feed, delete_blog_feed,
        upsert_blog_article, get_blog_articles, get_blog_article, update_blog_article_summary,
        get_known_blog_guids,
    )
    from kita_client import fetch_range, fetch_region_month, fetch_industry_range, fetch_industry_month, get_daily_request_count
    from stock_client import fetch_stock_prices, fetch_daily_stock_prices, search_stock_by_name, fetch_index_prices
    from carbon_client import fetch_carbon_prices, fetch_all_carbon_items
    from tourism_client import fetch_country_list, fetch_all_countries_month, fetch_tourism_range
    from nps_client import search_company as nps_search, fetch_nps_data
    from notifier import notify_update, notify_visit_update_sync, send_telegram
    from youtube_client import resolve_channel, fetch_latest_videos
    from blog_client import discover_feed, fetch_articles_rss, fetch_articles_scrape, fetch_article_content

scheduler = AsyncIOScheduler()


def _fire_visit_notify(company_id: int, update_type: str, detail: str = ""):
    """Fire a visit update notification."""
    company = get_company(company_id)
    name = company["name"] if company else f"ID {company_id}"
    notify_visit_update_sync(name, company_id, update_type, detail)


async def scheduled_fetch_latest():
    """Monthly job: fetch latest month for all tracked items."""
    now = datetime.datetime.now()
    # Fetch previous month's data (current month likely incomplete)
    if now.month == 1:
        target_year, target_month = now.year - 1, 12
    else:
        target_year, target_month = now.year, now.month - 1

    items = get_items()
    for item in items:
        year_str = str(target_year)
        month_str = str(target_month).zfill(2)
        try:
            if item["region_type"] == "0":
                row = await fetch_industry_month(
                    year_str, month_str,
                    item["item_code"], item["item_type"],
                )
            else:
                row = await fetch_region_month(
                    year_str, month_str,
                    item["item_code"], item["region_name"],
                    item["item_type"], item["region_type"],
                )
        except RuntimeError as e:
            print(f"[scheduler] KITA limit reached: {e}")
            break
        if row:
            upsert_trade_data(
                item["id"], year_str, month_str,
                row["export_amt"], row["export_rate"],
                row["import_amt"], row["import_rate"],
                row["balance"],
            )
            label = item["label"] or f"{item['region_name']} {item['item_code']}"
            await notify_update(
                label, year_str, month_str,
                row["export_amt"], row["import_amt"],
                row["balance"], row["export_rate"],
            )
    # Also update stock prices
    for item in items:
        if item.get("stock_code"):
            try:
                prices = await fetch_stock_prices(item["stock_code"], count=3)
                for p in prices:
                    upsert_stock_price(item["id"], item["stock_code"], item.get("stock_name", ""), p["year"], p["month"], p["close_price"])
            except Exception as e:
                print(f"[scheduler] Stock fetch error for {item.get('stock_name')}: {e}")

    print(f"[scheduler] Fetched {target_year}-{target_month:02d} for {len(items)} items")


async def scheduled_visit_alarms():
    """Daily job: check for today's visits and events that need alarms."""
    today = datetime.date.today().isoformat()
    pending_visits = get_pending_visit_alarms(today)
    for v in pending_visits:
        msg = (
            f"<b>오늘 회사 탐방 일정</b>\n\n"
            f"<b>{v['company_name']}</b>\n"
            f"일시: {v['visit_date']} {v.get('visit_time') or ''}\n"
            f"목적: {v.get('purpose') or '-'}\n"
            f"참석자: {v.get('attendees') or '-'}"
        )
        await send_telegram(msg, use_group=True)
        mark_visit_alarm_sent(v["id"])

    pending_events = get_pending_event_alarms(today)
    type_labels = {"issue": "이슈", "momentum": "모멘텀", "followup": "팔로업"}
    for e in pending_events:
        label = type_labels.get(e["event_type"], e["event_type"])
        msg = (
            f"<b>{label} 알림</b>\n\n"
            f"<b>{e['company_name']}</b>\n"
            f"{e['title']}\n"
            f"{e.get('description') or ''}"
        )
        await send_telegram(msg, use_group=True)
        mark_event_alarm_sent(e["id"])

    count = len(pending_visits) + len(pending_events)
    if count:
        print(f"[scheduler] Sent {count} visit/event alarms for {today}")


def _summarize_video(title: str, description: str) -> str | None:
    """Summarize a YouTube video using Claude API. Returns summary text or None on failure."""
    if not SUMMARIZE_ENABLED or not _anthropic_client:
        return None
    if not description or not description.strip():
        return None
    try:
        prompt = (
            f"다음 유튜브 영상의 제목과 설명을 읽고, 핵심 내용을 한국어로 3~5문장으로 요약해줘.\n\n"
            f"제목: {title}\n\n"
            f"설명:\n{description[:3000]}"
        )
        resp = _anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"[youtube] Summary error: {e}")
        return None


async def scheduled_youtube_check():
    """Hourly job: check all YouTube channels for new videos, notify, and summarize."""
    channels = get_youtube_channels()
    total_new = 0
    for ch in channels:
        try:
            known = get_known_video_ids(ch["id"])
            videos = await fetch_latest_videos(ch["channel_id"], max_results=5)
            for v in videos:
                if v["video_id"] not in known:
                    upsert_youtube_video(
                        ch["id"], v["video_id"], v["title"],
                        description=v.get("description"),
                        thumbnail_url=v.get("thumbnail_url"),
                        published_at=v.get("published_at"),
                        url=v["url"],
                    )
                    # Auto-summarize new video
                    summary = _summarize_video(v["title"], v.get("description", ""))
                    if summary:
                        update_youtube_video_summary(v["video_id"], summary)
                    msg = (
                        f"<b>유튜브 새 영상</b>\n\n"
                        f"<b>{ch['channel_name']}</b>\n"
                        f"{v['title']}\n\n"
                    )
                    if summary:
                        msg += f"<i>{summary}</i>\n\n"
                    msg += f"<a href=\"{v['url']}\">영상 보기</a>"
                    await send_telegram(msg)
                    mark_youtube_video_notified(v["video_id"])
                    total_new += 1
            update_youtube_channel(ch["id"], last_checked_at=datetime.datetime.now().isoformat())
        except Exception as e:
            print(f"[youtube] Error checking {ch.get('channel_name')}: {e}")
    if total_new:
        print(f"[youtube] Found {total_new} new videos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(
        scheduled_fetch_latest,
        "cron",
        day=17,
        hour=9,
        minute=0,
        id="monthly_fetch",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_visit_alarms,
        "cron",
        hour=8,
        minute=0,
        id="daily_visit_alarms",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_youtube_check,
        "interval",
        hours=1,
        id="youtube_check",
        replace_existing=True,
    )
    scheduler.start()
    print("[scheduler] Started - monthly fetch on 17th at 09:00, daily visit alarms at 08:00, youtube check hourly")
    yield
    scheduler.shutdown()


app = FastAPI(title="KITA Trade Dashboard", lifespan=lifespan)

# --- API Models ---

class ItemCreate(BaseModel):
    item_code: str
    item_type: str = "HS"
    region_type: str = "3"
    region_name: str
    label: str | None = None
    stock_code: str | None = None
    stock_name: str | None = None

class IndustryCreate(BaseModel):
    item_code: str
    item_type: str = "HS"
    label: str

class FetchRequest(BaseModel):
    year_from: int
    month_from: int = 1
    year_to: int
    month_to: int = 12

class TradeDataRow(BaseModel):
    year: str
    month: str
    export_amt: int = 0
    export_rate: float = 0.0
    import_amt: int = 0
    import_rate: float = 0.0
    balance: int = 0

class TradeDataImport(BaseModel):
    rows: list[TradeDataRow]

class CompanyCreate(BaseModel):
    name: str
    stock_code: str | None = None
    sector: str | None = None
    notes: str | None = None

class CompanyUpdate(BaseModel):
    name: str | None = None
    stock_code: str | None = None
    sector: str | None = None
    notes: str | None = None

class VisitCreate(BaseModel):
    company_id: int
    visit_date: str
    visit_time: str | None = None
    purpose: str | None = None
    attendees: str | None = None

class VisitUpdate(BaseModel):
    visit_date: str | None = None
    visit_time: str | None = None
    purpose: str | None = None
    attendees: str | None = None
    status: str | None = None
    summary: str | None = None

class EventCreate(BaseModel):
    company_id: int
    event_date: str
    event_type: str
    title: str
    description: str | None = None
    alarm_date: str | None = None

class EventUpdate(BaseModel):
    event_date: str | None = None
    event_type: str | None = None
    title: str | None = None
    description: str | None = None
    alarm_date: str | None = None

class ConsensusEntry(BaseModel):
    period_type: str
    period: str
    revenue: float | None = None
    operating_profit: float | None = None
    net_income: float | None = None
    eps: float | None = None
    per: float | None = None
    is_estimate: int = 0

# --- API Routes ---

@app.get("/api/items")
def api_get_items():
    items = get_items()
    return [i for i in items if i.get("region_type") != "0"]

@app.post("/api/items")
def api_add_item(req: ItemCreate):
    item_id = add_item(req.item_code, req.item_type, req.region_type, req.region_name, req.label, req.stock_code, req.stock_name)
    return {"id": item_id}

@app.delete("/api/items/{item_id}")
def api_delete_item(item_id: int):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    delete_item(item_id)
    return {"ok": True}

@app.get("/api/data/{item_id}")
def api_get_data(item_id: int, year_from: str | None = None, year_to: str | None = None):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return get_trade_data(item_id, year_from, year_to)

@app.get("/api/summary/{item_id}")
def api_get_summary(item_id: int):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return get_yearly_summary(item_id)

@app.post("/api/fetch/{item_id}")
async def api_fetch_data(item_id: int, req: FetchRequest):
    """Fetch data from KITA and store in DB. Skips months already in DB."""
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    # Build set of months already in DB to skip
    existing = get_trade_data(item_id)
    skip_months = {f"{r['year']}-{r['month']}" for r in existing if r.get("export_amt", 0) != 0 or r.get("import_amt", 0) != 0}

    try:
        if item["region_type"] == "0":
            rows = await fetch_industry_range(
                item["item_code"],
                req.year_from, req.month_from,
                req.year_to, req.month_to,
                item["item_type"],
                skip_months=skip_months,
            )
        else:
            rows = await fetch_range(
                item["item_code"], item["region_name"],
                req.year_from, req.month_from,
                req.year_to, req.month_to,
                item["item_type"], item["region_type"],
                skip_months=skip_months,
            )
    except RuntimeError as e:
        raise HTTPException(429, str(e))

    count = 0
    for row in rows:
        upsert_trade_data(
            item_id, row["year"], row["month"],
            row["export_amt"], row["export_rate"],
            row["import_amt"], row["import_rate"],
            row["balance"],
        )
        count += 1

    return {"fetched": count, "skipped": len(skip_months)}

@app.post("/api/import/{item_id}")
def api_import_data(item_id: int, req: TradeDataImport):
    """Import trade data directly (for when KITA is not reachable from server)."""
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    count = 0
    for row in req.rows:
        upsert_trade_data(
            item_id, row.year, row.month,
            row.export_amt, row.export_rate,
            row.import_amt, row.import_rate,
            row.balance,
        )
        count += 1
    return {"imported": count}

@app.get("/api/kita-status")
def api_kita_status():
    """Check KITA daily request count."""
    return get_daily_request_count()

@app.get("/api/debug/regions")
async def api_debug_regions(code: str = "851762", item_type: str = "HS", region_type: str = "3", year: str = "2025", month: str = "01"):
    """Debug: show all region names KITA returns for given params."""
    try:
        from dashboard.kita_client import fetch_month
    except ImportError:
        from kita_client import fetch_month
    rows, total = await fetch_month(year, month, code, item_type, region_type)
    return {
        "code": code,
        "region_type": region_type,
        "kita_regions": [{"name": r["region_name"], "export": r["export_amt"]} for r in rows],
        "total": total,
        "count": len(rows),
    }

@app.post("/api/fetch-stock/{item_id}")
async def api_fetch_stock(item_id: int):
    """Fetch stock prices from Naver Finance and store in DB."""
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    if not item.get("stock_code"):
        raise HTTPException(400, "No stock code for this item")

    prices = await fetch_stock_prices(item["stock_code"])
    stock_name = item.get("stock_name") or ""
    for p in prices:
        upsert_stock_price(item_id, item["stock_code"], stock_name, p["year"], p["month"], p["close_price"])
    return {"fetched": len(prices)}

@app.post("/api/fetch-latest")
async def api_fetch_latest():
    """Manually trigger fetch of latest month for all items."""
    await scheduled_fetch_latest()
    return {"ok": True}

@app.get("/api/stock/{item_id}")
def api_get_stock(item_id: int, year_from: str | None = None, year_to: str | None = None):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return get_stock_prices(item_id, year_from, year_to)

@app.get("/api/stock-info/{item_id}")
def api_get_stock_info(item_id: int):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    info = get_stock_info(item_id)
    return info or {}

@app.get("/api/revenue/{item_id}")
def api_get_revenue(item_id: int, year_from: str | None = None, year_to: str | None = None):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return get_quarterly_revenue(item_id, year_from, year_to)

@app.post("/api/stock/{item_id}")
def api_add_stock(item_id: int, data: list[dict]):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    for d in data:
        upsert_stock_price(item_id, d["stock_code"], d["stock_name"], d["year"], d["month"], d["close_price"])
    return {"inserted": len(data)}

@app.post("/api/revenue/{item_id}")
def api_add_revenue(item_id: int, data: list[dict]):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    for d in data:
        upsert_quarterly_revenue(item_id, d["stock_code"], d["stock_name"], d["year"], d["quarter"], d["revenue"])
    return {"inserted": len(data)}

@app.post("/api/data/{item_id}")
def api_add_trade(item_id: int, data: list[dict]):
    item = get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    for d in data:
        upsert_trade_data(
            item_id, d["year"], d["month"],
            d["export_amt"], d.get("export_rate", 0),
            d["import_amt"], d.get("import_rate", 0),
            d.get("balance", 0),
        )
    return {"inserted": len(data)}

# --- Industry API Routes ---

@app.get("/api/industry/items")
def api_get_industry_items():
    items = get_items()
    return [i for i in items if i.get("region_type") == "0"]

@app.post("/api/industry/items")
def api_add_industry_item(req: IndustryCreate):
    item_id = add_item(req.item_code, req.item_type, "0", None, req.label)
    return {"id": item_id}

# --- Carbon API Routes ---

@app.get("/api/carbon/prices")
async def api_get_carbon_prices(
    item_name: str = "KAU25",
    begin_date: str | None = None,
    end_date: str | None = None,
):
    """Fetch carbon emission credit prices from public data API."""
    prices = await fetch_carbon_prices(item_name, begin_date, end_date)
    return prices

@app.get("/api/carbon/stock")
async def api_get_carbon_stock(code: str = "448280", count: int = 500):
    """Fetch daily stock prices for carbon-related company."""
    prices = await fetch_daily_stock_prices(code, count)
    return prices

@app.get("/api/carbon/items")
async def api_get_carbon_items(date: str | None = None):
    """Fetch all carbon credit items for a date."""
    items = await fetch_all_carbon_items(date)
    return items

# --- Visit Management API Routes ---

MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10MB

@app.get("/api/visit/companies")
def api_get_companies():
    return get_companies()

@app.post("/api/visit/companies")
def api_add_company(req: CompanyCreate):
    cid = add_company(req.name, req.stock_code, req.sector, req.notes)
    return {"id": cid}

@app.get("/api/visit/companies/{company_id}")
def api_get_company(company_id: int):
    c = get_company(company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    return c

@app.put("/api/visit/companies/{company_id}")
def api_update_company(company_id: int, req: CompanyUpdate):
    if not get_company(company_id):
        raise HTTPException(404, "Company not found")
    update_company(company_id, req.name, req.stock_code, req.sector, req.notes)
    return {"ok": True}

@app.delete("/api/visit/companies/{company_id}")
def api_delete_company(company_id: int):
    if not get_company(company_id):
        raise HTTPException(404, "Company not found")
    delete_company(company_id)
    return {"ok": True}

# Visits
@app.post("/api/visit/visits")
def api_add_visit(req: VisitCreate):
    if not get_company(req.company_id):
        raise HTTPException(404, "Company not found")
    vid = add_visit(req.company_id, req.visit_date, req.visit_time, req.purpose, req.attendees)
    return {"id": vid}

@app.get("/api/visit/companies/{company_id}/visits")
def api_get_visits(company_id: int):
    return get_visits(company_id)

@app.get("/api/visit/all-visits")
def api_get_all_visits():
    return get_all_visits()

@app.get("/api/visit/upcoming")
def api_get_upcoming():
    return get_upcoming_visits()

@app.put("/api/visit/visits/{visit_id}")
def api_update_visit(visit_id: int, req: VisitUpdate):
    update_visit(visit_id, **req.model_dump(exclude_none=True))
    if req.status or req.summary:
        try:
            from dashboard.db import get_db
        except ImportError:
            from db import get_db
        with get_db() as conn:
            row = conn.execute("SELECT company_id FROM company_visits WHERE id = ?", (visit_id,)).fetchone()
        if row:
            detail = req.summary[:80] if req.summary else (req.status or "")
            _fire_visit_notify(row["company_id"], "탐방 결과", detail)
    return {"ok": True}

@app.delete("/api/visit/visits/{visit_id}")
def api_delete_visit(visit_id: int):
    delete_visit(visit_id)
    return {"ok": True}

# Materials (file upload/download)
@app.post("/api/visit/materials/{company_id}")
async def api_upload_material(
    company_id: int,
    file: UploadFile = File(...),
    visit_id: int | None = Form(None),
    description: str | None = Form(None),
):
    if not get_company(company_id):
        raise HTTPException(404, "Company not found")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, "File too large (max 10MB)")
    mid = add_visit_material(company_id, visit_id, file.filename, file.content_type, contents, len(contents), description)
    _fire_visit_notify(company_id, "탐방 자료", f"파일: {file.filename}")
    return {"id": mid, "filename": file.filename, "size": len(contents)}

@app.get("/api/visit/companies/{company_id}/materials")
def api_get_materials(company_id: int):
    return get_visit_materials(company_id)

@app.get("/api/visit/materials/{material_id}/download")
def api_download_material(material_id: int, inline: bool = False):
    mat = get_visit_material(material_id)
    if not mat:
        raise HTTPException(404, "Material not found")
    if not mat.get("file_data"):
        raise HTTPException(404, "No file data")
    disposition = "inline" if inline else "attachment"
    return Response(
        content=mat["file_data"],
        media_type=mat["mime_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{mat["filename"]}"'},
    )

@app.delete("/api/visit/materials/{material_id}")
def api_delete_material(material_id: int):
    delete_visit_material(material_id)
    return {"ok": True}

class TextNoteCreate(BaseModel):
    title: str | None = None
    text_content: str
    visit_id: int | None = None

@app.post("/api/visit/materials/{company_id}/text")
def api_add_text_note(company_id: int, req: TextNoteCreate):
    if not get_company(company_id):
        raise HTTPException(404, "Company not found")
    mid = add_text_material(company_id, req.title, req.text_content, req.visit_id)
    _fire_visit_notify(company_id, "탐방 메모", req.title or "")
    return {"id": mid}

# Events (issues / momentum / followup)
@app.post("/api/visit/events")
def api_add_event(req: EventCreate):
    if not get_company(req.company_id):
        raise HTTPException(404, "Company not found")
    eid = add_event(req.company_id, req.event_date, req.event_type, req.title, req.description, req.alarm_date)
    type_label = {"issue": "이슈", "momentum": "모멘텀", "followup": "팔로업"}.get(req.event_type, req.event_type)
    _fire_visit_notify(req.company_id, type_label, req.title or "")
    return {"id": eid}

@app.get("/api/visit/all-events")
def api_get_all_events():
    return get_all_events()

@app.get("/api/visit/companies/{company_id}/events")
def api_get_events(company_id: int):
    return get_events(company_id)

@app.put("/api/visit/events/{event_id}")
def api_update_event(event_id: int, req: EventUpdate):
    update_event(event_id, **req.model_dump(exclude_none=True))
    # Notify: look up company_id from the event
    from dashboard.db import get_db
    with get_db() as conn:
        row = conn.execute("SELECT company_id, event_type, title FROM company_events WHERE id = ?", (event_id,)).fetchone()
    if row:
        et = req.event_type or row["event_type"]
        type_label = {"issue": "이슈", "momentum": "모멘텀", "followup": "팔로업"}.get(et, et)
        _fire_visit_notify(row["company_id"], f"{type_label} (수정)", req.title or row["title"] or "")
    return {"ok": True}

@app.delete("/api/visit/events/{event_id}")
def api_delete_event(event_id: int):
    delete_event(event_id)
    return {"ok": True}

# Reports
@app.post("/api/visit/reports/{company_id}")
async def api_upload_report(
    company_id: int,
    report_date: str = Form(...),
    source: str | None = Form(None),
    title: str | None = Form(None),
    summary: str | None = Form(None),
    target_price: int | None = Form(None),
    rating: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    if not get_company(company_id):
        raise HTTPException(404, "Company not found")
    file_data, filename, mime = None, None, None
    if file:
        file_data = await file.read()
        if len(file_data) > MAX_UPLOAD_SIZE:
            raise HTTPException(413, "File too large (max 10MB)")
        filename = file.filename
        mime = file.content_type
    rid = add_report(company_id, report_date, source, title, summary, target_price, rating, filename, file_data, mime)
    detail = title or filename or ""
    if source:
        detail = f"[{source}] {detail}"
    _fire_visit_notify(company_id, "리포트", detail)
    return {"id": rid}

@app.get("/api/visit/companies/{company_id}/reports")
def api_get_reports(company_id: int):
    return get_reports(company_id)

@app.get("/api/visit/reports/{report_id}/download")
def api_download_report(report_id: int):
    report = get_report(report_id)
    if not report or not report.get("original_file"):
        raise HTTPException(404, "Report file not found")
    from urllib.parse import quote
    filename = report["original_filename"]
    encoded = quote(filename)
    return Response(
        content=report["original_file"],
        media_type=report["mime_type"] or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )

@app.delete("/api/visit/reports/{report_id}")
def api_delete_report(report_id: int):
    delete_report(report_id)
    return {"ok": True}

# Stock search by name
@app.get("/api/visit/search-stock")
async def api_search_stock(name: str):
    results = await search_stock_by_name(name)
    return results

# Stock for visit company (daily prices)
@app.get("/api/visit/stock/{company_id}")
async def api_get_visit_stock(company_id: int, from_date: str | None = None, count: int = 500):
    company = get_company(company_id)
    if not company or not company.get("stock_code"):
        raise HTTPException(400, "No stock code")
    prices = await fetch_daily_stock_prices(company["stock_code"], count)
    if from_date:
        prices = [p for p in prices if p["date"] >= from_date]
    return prices

# Consensus
@app.get("/api/visit/consensus/{company_id}")
def api_get_consensus(company_id: int):
    return get_consensus(company_id)

@app.post("/api/visit/consensus/{company_id}")
def api_add_consensus(company_id: int, req: ConsensusEntry):
    company = get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    upsert_consensus(company_id, company.get("stock_code", ""), req.period_type, req.period,
                     req.revenue, req.operating_profit, req.net_income, req.eps, req.per, req.is_estimate)
    _fire_visit_notify(company_id, "컨센서스", f"{req.period} ({req.period_type})")
    return {"ok": True}

@app.post("/api/visit/consensus/{company_id}/fetch")
async def api_fetch_consensus(company_id: int):
    company = get_company(company_id)
    if not company or not company.get("stock_code"):
        raise HTTPException(400, "No stock code")
    try:
        from dashboard.consensus_client import fetch_consensus
    except ImportError:
        from consensus_client import fetch_consensus
    data = await fetch_consensus(company["stock_code"])
    for item in data:
        upsert_consensus(company_id, company["stock_code"], item["period_type"], item["period"],
                         item.get("revenue"), item.get("operating_profit"), item.get("net_income"),
                         item.get("eps"), item.get("per"), item.get("is_estimate", 0))
    return {"fetched": len(data)}

# --- Tourism API ---

class TourismCountryCreate(BaseModel):
    nat_cd: str
    nat_nm: str
    tar_cd: str | None = None

class TourismFetchRequest(BaseModel):
    year_from: int
    month_from: int = 1
    year_to: int
    month_to: int = 12

class TourismDataRow(BaseModel):
    year: str
    month: str
    visitors: int = 0
    prev_visitors: int = 0
    change_rate: float = 0.0

class TourismDataImport(BaseModel):
    rows: list[TourismDataRow]

@app.get("/api/tourism/countries")
def api_tourism_countries():
    return get_tourism_countries()

@app.post("/api/tourism/countries")
def api_add_tourism_country(req: TourismCountryCreate):
    cid = add_tourism_country(req.nat_cd, req.nat_nm, req.tar_cd)
    return {"id": cid}

@app.delete("/api/tourism/countries/{country_id}")
def api_delete_tourism_country(country_id: int):
    delete_tourism_country(country_id)
    return {"ok": True}

@app.get("/api/tourism/data/{country_id}")
def api_tourism_data(country_id: int, year_from: int | None = None, year_to: int | None = None):
    return get_tourism_data(country_id, year_from, year_to)

@app.post("/api/tourism/fetch/{country_id}")
async def api_tourism_fetch(country_id: int, req: TourismFetchRequest):
    """Fetch tourism data for a specific country from Data Lab."""
    country = get_tourism_country(country_id)
    if not country:
        raise HTTPException(404, "Country not found")

    existing = get_tourism_data(country_id)
    skip_months = {f"{r['year']}-{r['month']}" for r in existing if r.get("visitors", 0) != 0}

    rows = await fetch_tourism_range(
        req.year_from, req.month_from, req.year_to, req.month_to,
        country["nat_nm"], skip_months=skip_months,
    )
    count = 0
    for row in rows:
        upsert_tourism_data(
            country_id, row["year"], row["month"],
            row["visitors"], row["prev_visitors"], row["change_rate"],
        )
        count += 1
    return {"fetched": count, "skipped": len(skip_months)}

@app.post("/api/tourism/fetch-all")
async def api_tourism_fetch_all(req: TourismFetchRequest):
    """Fetch tourism data for ALL tracked countries at once (efficient: 1 API call per month)."""
    countries = get_tourism_countries()
    if not countries:
        raise HTTPException(400, "No countries tracked")
    name_to_id = {c["nat_nm"]: c["id"] for c in countries}

    total = 0
    y, m = req.year_from, req.month_from
    while (y, m) <= (req.year_to, req.month_to):
        rows = await fetch_all_countries_month(str(y), str(m).zfill(2))
        for row in rows:
            cid = name_to_id.get(row["nat_nm"])
            if cid:
                upsert_tourism_data(cid, row["year"], row["month"],
                                    row["visitors"], row["prev_visitors"], row["change_rate"])
                total += 1
        import asyncio as _aio
        await _aio.sleep(2)
        m += 1
        if m > 12:
            m = 1; y += 1
    return {"fetched": total}

@app.post("/api/tourism/import/{country_id}")
def api_tourism_import(country_id: int, req: TourismDataImport):
    """Import tourism data directly."""
    country = get_tourism_country(country_id)
    if not country:
        raise HTTPException(404, "Country not found")
    count = 0
    for row in req.rows:
        upsert_tourism_data(country_id, row.year, row.month,
                            row.visitors, row.prev_visitors, row.change_rate)
        count += 1
    return {"imported": count}

@app.get("/api/tourism/country-list")
async def api_tourism_country_list():
    """Fetch available countries from Data Lab."""
    try:
        return await fetch_country_list()
    except Exception as e:
        raise HTTPException(502, f"Data Lab 연결 실패: {e}")

TOP10 = [
    ("CN", "중국", "156"), ("JP", "일본", "392"), ("US", "미국", "840"),
    ("TW", "대만", "158"), ("HK", "홍콩", "344"), ("TH", "태국", "764"),
    ("VN", "베트남", "704"), ("PH", "필리핀", "608"), ("SG", "싱가포르", "702"),
    ("MY", "말레이시아", "458"),
]

@app.post("/api/tourism/init-top10")
def api_tourism_init_top10():
    """Register top 10 countries if not already tracked."""
    added = []
    for nat_cd, nat_nm, tar_cd in TOP10:
        cid = add_tourism_country(nat_cd, nat_nm, tar_cd)
        if cid:
            added.append({"id": cid, "nat_cd": nat_cd, "nat_nm": nat_nm})
    return {"added": added, "total": len(get_tourism_countries())}

@app.get("/api/tourism/overview")
def api_tourism_overview():
    """Get latest month data for all tracked countries."""
    countries = get_tourism_countries()
    result = []
    for c in countries:
        data = get_tourism_data(c["id"])
        if data:
            latest = data[-1]
            result.append({
                "id": c["id"], "nat_cd": c["nat_cd"], "nat_nm": c["nat_nm"],
                "year": latest["year"], "month": latest["month"],
                "visitors": latest["visitors"],
                "prev_visitors": latest["prev_visitors"],
                "change_rate": latest["change_rate"],
                "total_months": len(data),
            })
        else:
            result.append({
                "id": c["id"], "nat_cd": c["nat_cd"], "nat_nm": c["nat_nm"],
                "year": "", "month": "", "visitors": 0,
                "prev_visitors": 0, "change_rate": 0, "total_months": 0,
            })
    result.sort(key=lambda x: x["visitors"], reverse=True)
    return result

@app.get("/api/tourism/total")
def api_tourism_total(year_from: int | None = None, year_to: int | None = None):
    """Get monthly total visitors summed across all tracked countries."""
    return get_tourism_total(year_from, year_to)


# --- NPS Headcount API ---

class NpsCompanyCreate(BaseModel):
    seq: str
    name: str
    biz_no: str | None = None

class NpsDataRow(BaseModel):
    year: str
    month: str
    subscribers: int = 0
    new_hires: int = 0
    losses: int = 0

class NpsDataImport(BaseModel):
    rows: list[NpsDataRow]

@app.get("/api/nps/companies")
def api_nps_companies():
    return get_nps_companies()

@app.post("/api/nps/companies")
def api_add_nps_company(req: NpsCompanyCreate):
    cid = add_nps_company(req.seq, req.name, req.biz_no)
    return {"id": cid}

@app.delete("/api/nps/companies/{company_id}")
def api_delete_nps_company(company_id: int):
    if not get_nps_company(company_id):
        raise HTTPException(404, "Company not found")
    delete_nps_company(company_id)
    return {"ok": True}

@app.get("/api/nps/data/{company_id}")
def api_nps_data(company_id: int, year_from: int | None = None, year_to: int | None = None):
    return get_nps_data(company_id, year_from, year_to)

@app.get("/api/nps/overview")
def api_nps_overview():
    return get_nps_overview()

@app.get("/api/nps/search")
async def api_nps_search(name: str):
    """Search NPS companies by name."""
    try:
        return await nps_search(name)
    except Exception as e:
        raise HTTPException(502, f"NPS API 연결 실패: {e}")

@app.post("/api/nps/fetch/{company_id}")
async def api_nps_fetch(company_id: int):
    """Fetch NPS data for a specific company."""
    company = get_nps_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    try:
        current_count, data = await fetch_nps_data(company["seq"], company["name"], company.get("biz_no", ""))
    except Exception as e:
        import traceback
        print(f"[nps] Fetch error for {company['name']}: {traceback.format_exc()}")
        raise HTTPException(502, f"NPS API 오류: {type(e).__name__}: {e}")

    update_nps_company(company_id, current_count=current_count)
    count = 0
    for row in data:
        upsert_nps_data(
            company_id, row["year"], row["month"],
            row["subscribers"], row["new_hires"], row["losses"],
        )
        count += 1
    return {"fetched": count, "current_count": current_count}

@app.post("/api/nps/fetch-all")
async def api_nps_fetch_all():
    """Fetch NPS data for all tracked companies."""
    companies = get_nps_companies()
    if not companies:
        raise HTTPException(400, "No companies tracked")
    total = 0
    for c in companies:
        try:
            current_count, data = await fetch_nps_data(c["seq"], c["name"], c.get("biz_no", ""))
            update_nps_company(c["id"], current_count=current_count)
            for row in data:
                upsert_nps_data(
                    c["id"], row["year"], row["month"],
                    row["subscribers"], row["new_hires"], row["losses"],
                )
                total += 1
        except Exception as e:
            print(f"[nps] Error fetching {c['name']}: {e}")
    return {"fetched": total}

@app.post("/api/nps/import/{company_id}")
def api_nps_import(company_id: int, req: NpsDataImport):
    """Import NPS data directly."""
    company = get_nps_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    count = 0
    for row in req.rows:
        upsert_nps_data(company_id, row.year, row.month,
                        row.subscribers, row.new_hires, row.losses)
        count += 1
    return {"imported": count}


# --- Market Correlation API ---

class MarketExportRow(BaseModel):
    year: str
    month: str
    export_amt: int = 0
    export_rate: float = 0.0

class MarketExportImport(BaseModel):
    category: str
    rows: list[MarketExportRow]

@app.get("/api/market/index")
def api_market_index(code: str = "KOSPI", year_from: int | None = None, year_to: int | None = None):
    return get_market_index(code, year_from, year_to)

@app.post("/api/market/fetch-index")
async def api_market_fetch_index(code: str = "KOSPI", count: int = 120):
    """Fetch KOSPI (or other index) monthly data from Naver Finance."""
    name_map = {"KOSPI": "코스피", "KOSDAQ": "코스닥"}
    name = name_map.get(code, code)
    prices = await fetch_index_prices(code, count)
    for p in prices:
        upsert_market_index(code, name, p["year"], p["month"], p["close_price"])
    return {"fetched": len(prices)}

@app.get("/api/market/exports")
def api_market_exports(category: str = "semiconductor", year_from: int | None = None, year_to: int | None = None):
    return get_market_export(category, year_from, year_to)

@app.post("/api/market/fetch-exports")
async def api_market_fetch_exports(year_from: int = 2020, year_to: int = 2026):
    """Fetch semiconductor export data from KITA (HS 8542, industry level)."""
    skip_months: set[str] = set()
    existing = get_market_export("semiconductor")
    for r in existing:
        if r.get("export_amt", 0) != 0:
            skip_months.add(f"{r['year']}-{r['month']}")

    try:
        rows = await fetch_industry_range("8542", year_from, 1, year_to, 12, "HS", skip_months=skip_months)
    except RuntimeError as e:
        raise HTTPException(429, str(e))

    count = 0
    for row in rows:
        upsert_market_export("semiconductor", row["year"], row["month"], row["export_amt"], row["export_rate"])
        count += 1

    # Also store as "total" export rate if available from same response
    return {"fetched": count, "skipped": len(skip_months)}

@app.post("/api/market/import-exports")
def api_market_import_exports(req: MarketExportImport):
    """Import export data manually (for total Korean exports etc)."""
    count = 0
    for row in req.rows:
        upsert_market_export(req.category, row.year, row.month, row.export_amt, row.export_rate)
        count += 1
    return {"imported": count}


# --- YouTube API ---

class YouTubeChannelCreate(BaseModel):
    identifier: str  # channel ID, handle (@username), or name


@app.get("/api/youtube/channels")
def api_youtube_channels():
    return get_youtube_channels()


@app.post("/api/youtube/channels")
async def api_youtube_add_channel(req: YouTubeChannelCreate):
    info = await resolve_channel(req.identifier)
    if not info:
        raise HTTPException(404, "채널을 찾을 수 없습니다")
    db_id = add_youtube_channel(info["channel_id"], info["channel_name"], info["channel_url"])
    if not db_id:
        raise HTTPException(409, "이미 등록된 채널입니다")
    # Fetch initial videos
    try:
        videos = await fetch_latest_videos(info["channel_id"], max_results=10)
        for v in videos:
            upsert_youtube_video(
                db_id, v["video_id"], v["title"],
                description=v.get("description"),
                thumbnail_url=v.get("thumbnail_url"),
                published_at=v.get("published_at"),
                url=v["url"],
            )
        update_youtube_channel(db_id, last_checked_at=datetime.datetime.now().isoformat())
    except Exception as e:
        print(f"[youtube] Initial fetch error: {e}")
    return {"id": db_id, **info}


@app.delete("/api/youtube/channels/{db_id}")
def api_youtube_delete_channel(db_id: int):
    ch = get_youtube_channel(db_id)
    if not ch:
        raise HTTPException(404, "채널 없음")
    delete_youtube_channel(db_id)
    return {"deleted": True}


@app.get("/api/youtube/videos")
def api_youtube_videos(channel_id: int | None = None, limit: int = 50):
    return get_youtube_videos(channel_db_id=channel_id, limit=limit)


@app.post("/api/youtube/channels/{db_id}/fetch")
async def api_youtube_fetch_channel(db_id: int):
    ch = get_youtube_channel(db_id)
    if not ch:
        raise HTTPException(404, "채널 없음")
    known = get_known_video_ids(db_id)
    videos = await fetch_latest_videos(ch["channel_id"], max_results=10)
    new_count = 0
    for v in videos:
        if v["video_id"] not in known:
            upsert_youtube_video(
                db_id, v["video_id"], v["title"],
                description=v.get("description"),
                thumbnail_url=v.get("thumbnail_url"),
                published_at=v.get("published_at"),
                url=v["url"],
            )
            new_count += 1
    update_youtube_channel(db_id, last_checked_at=datetime.datetime.now().isoformat())
    return {"fetched": len(videos), "new": new_count}


@app.post("/api/youtube/videos/{video_id}/summarize")
def api_youtube_summarize(video_id: str):
    """Generate or regenerate a summary for a specific video."""
    if not SUMMARIZE_ENABLED:
        raise HTTPException(503, "요약 기능을 사용할 수 없습니다 (ANTHROPIC_API_KEY 필요)")
    vids = get_youtube_videos(limit=500)
    vid = next((v for v in vids if v["video_id"] == video_id), None)
    if not vid:
        raise HTTPException(404, "영상을 찾을 수 없습니다")
    summary = _summarize_video(vid["title"], vid.get("description", ""))
    if not summary:
        raise HTTPException(422, "요약 생성에 실패했습니다 (설명이 비어있거나 API 오류)")
    update_youtube_video_summary(video_id, summary)
    return {"video_id": video_id, "summary": summary}


# ============================
#  Blog Monitoring API
# ============================

class BlogFeedCreate(BaseModel):
    url: str


def _summarize_blog(title: str, content: str) -> dict:
    """블로그 글 요약 + 언어 감지 + 번역 (Anthropic Claude)."""
    if not SUMMARIZE_ENABLED or not _anthropic_client:
        return {"summary": "", "language": "", "translated": False}
    text = content[:5000] if content else title
    if not text or not text.strip():
        return {"summary": "", "language": "", "translated": False}
    try:
        prompt = (
            "다음 블로그 글의 제목과 본문을 분석하세요.\n\n"
            "1. 글의 원래 언어를 감지하세요 (ISO 639-1 코드: en, ko, ja, zh 등)\n"
            "2. 핵심 내용을 한국어로 3~5문장으로 요약하세요\n"
            "3. 원래 언어가 한국어가 아닌 경우, 요약을 한국어로 작성하세요\n\n"
            "반드시 아래 JSON 형식으로만 응답하세요:\n"
            '{"language": "감지된_언어_코드", "summary": "한국어_요약_내용", "translated": true_또는_false}\n\n'
            f"제목: {title}\n\n본문:\n{text}"
        )
        resp = _anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        raw = resp.content[0].text.strip()
        # JSON 부분만 추출
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(raw[start:end])
            return {
                "summary": result.get("summary", ""),
                "language": result.get("language", ""),
                "translated": bool(result.get("translated", False)),
            }
        return {"summary": raw, "language": "", "translated": False}
    except Exception as e:
        print(f"[blog] Summary error: {e}")
        return {"summary": "", "language": "", "translated": False}


@app.get("/api/blog/feeds")
def api_blog_feeds():
    return get_blog_feeds()


@app.post("/api/blog/feeds")
async def api_blog_add_feed(req: BlogFeedCreate):
    url = req.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    try:
        info = await discover_feed(url)
    except Exception as e:
        raise HTTPException(400, f"URL 접근 실패: {str(e)[:200]}")

    feed_id = add_blog_feed(url, info["feed_url"], info["title"], info["language"])
    if not feed_id:
        raise HTTPException(409, "이미 등록된 블로그입니다")

    # 등록 직후 글 자동 수집
    try:
        if info["feed_url"]:
            articles = await fetch_articles_rss(info["feed_url"])
        else:
            articles = await fetch_articles_scrape(url)
        for a in articles:
            upsert_blog_article(
                feed_id, a["guid"], a["url"], a["title"],
                author=a.get("author", ""),
                published_at=a.get("published_at", ""),
                content=a.get("content", ""),
            )
        update_blog_feed(feed_id, last_checked=datetime.datetime.now().strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"[blog] Initial fetch error: {e}")

    return {"id": feed_id, "title": info["title"], "feed_url": info["feed_url"]}


@app.delete("/api/blog/feeds/{feed_id}")
def api_blog_delete_feed(feed_id: int):
    feed = get_blog_feed(feed_id)
    if not feed:
        raise HTTPException(404, "블로그 없음")
    delete_blog_feed(feed_id)
    return {"deleted": True}


@app.get("/api/blog/articles")
def api_blog_articles(feed_id: int | None = None, limit: int = 50):
    return get_blog_articles(feed_id=feed_id, limit=limit)


@app.post("/api/blog/feeds/{feed_id}/fetch")
async def api_blog_fetch_feed(feed_id: int):
    feed = get_blog_feed(feed_id)
    if not feed:
        raise HTTPException(404, "블로그 없음")

    known = get_known_blog_guids(feed_id)
    if feed.get("feed_url"):
        articles = await fetch_articles_rss(feed["feed_url"])
    else:
        articles = await fetch_articles_scrape(feed["url"])

    new_count = 0
    for a in articles:
        if a["guid"] not in known:
            upsert_blog_article(
                feed_id, a["guid"], a["url"], a["title"],
                author=a.get("author", ""),
                published_at=a.get("published_at", ""),
                content=a.get("content", ""),
            )
            new_count += 1

    update_blog_feed(feed_id, last_checked=datetime.datetime.now().strftime("%Y-%m-%d"))
    return {"fetched": len(articles), "new": new_count}


@app.post("/api/blog/articles/{article_id}/summarize")
async def api_blog_summarize(article_id: int):
    art = get_blog_article(article_id)
    if not art:
        raise HTTPException(404, "글을 찾을 수 없습니다")

    content = art.get("content", "") or ""
    # 본문이 없으면 페이지에서 직접 가져오기
    if not content and art.get("url"):
        content = await fetch_article_content(art["url"])

    result = _summarize_blog(art["title"], content)
    if not result["summary"]:
        raise HTTPException(422, "요약 생성에 실패했습니다")

    update_blog_article_summary(article_id, result["summary"], result["language"], result["translated"])
    return {"article_id": article_id, **result}


# --- Static files ---

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/industry")
def industry():
    return FileResponse(os.path.join(static_dir, "industry.html"))

@app.get("/carbon")
def carbon():
    return FileResponse(os.path.join(static_dir, "carbon.html"))

@app.get("/visit")
def visit():
    return FileResponse(os.path.join(static_dir, "visit.html"))

@app.get("/tourism")
def tourism():
    return FileResponse(os.path.join(static_dir, "tourism.html"))

@app.get("/headcount")
def headcount():
    return FileResponse(os.path.join(static_dir, "headcount.html"))

@app.get("/market")
def market():
    return FileResponse(os.path.join(static_dir, "market.html"))

@app.get("/youtube")
def youtube():
    return FileResponse(os.path.join(static_dir, "youtube.html"))

@app.get("/blog")
def blog():
    return FileResponse(os.path.join(static_dir, "blog.html"))
