import asyncio
import base64
import csv
import datetime
import io
import json
import math
import os
import re
import threading
import traceback
import zipfile

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
import requests
from bs4 import BeautifulSoup

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
        upsert_us_market_daily, get_us_market_daily, get_us_market_daily_by_date,
        update_us_market_summary,
        upsert_kr_market_daily, get_kr_market_daily, get_kr_market_daily_by_date,
        add_insider_buy_record, get_insider_buy_records, delete_insider_buy_record,
        get_insider_buy_record_by_source_url,
        update_insider_buy_record_by_source_url,
        add_quarterly_perf_watch, get_quarterly_perf_watchlist, delete_quarterly_perf_watch,
        upsert_quarterly_perf_data, get_quarterly_perf_data, get_quarterly_perf_quarters,
        upsert_quarterly_perf_reason, get_quarterly_perf_reasons,
        upsert_stock_monitor_return, get_stock_monitor_returns,
        add_overhang_lockup, get_overhang_lockups, delete_overhang_lockup,
        add_overhang_exercise, get_overhang_exercises, delete_overhang_exercise,
        upsert_usdc_supply_daily, get_usdc_supply_daily,
        upsert_stablecoin_supply_daily, get_stablecoin_supply_daily,
        upsert_semiconductor_price_daily, get_semiconductor_price_daily,
        get_latest_semiconductor_price_date,
    )
    from dashboard.kita_client import fetch_range, fetch_region_month, fetch_industry_range, fetch_industry_month, get_daily_request_count
    from dashboard.stock_client import (
        fetch_stock_prices, fetch_daily_stock_prices, search_stock_by_name,
        fetch_index_prices, fetch_daily_index_prices,
    )
    from dashboard.carbon_client import (
        fetch_carbon_prices, fetch_all_carbon_items,
        fetch_yahoo_symbol_history, fetch_sceex_domestic_history, fetch_sceex_international_history,
    )
    from dashboard.tourism_client import fetch_country_list, fetch_all_countries_month, fetch_tourism_range
    from dashboard.nps_client import search_company as nps_search, fetch_nps_data
    from dashboard.notifier import notify_update, notify_visit_update_sync, send_telegram
    from dashboard.youtube_client import resolve_channel, fetch_latest_videos
    from dashboard.blog_client import discover_feed, fetch_articles_rss, fetch_articles_scrape, fetch_article_content
    from dashboard.alpha_vantage_client import fetch_sp500_daily, fetch_nasdaq_daily, fetch_sector_performance, fetch_daily_index_series
    from dashboard.dart_client import fetch_trading_trend_candidates
    from dashboard.quarterly_perf_client import fetch_fnguide_quarterly, search_reason_snippets
    from dashboard.disclosure_compare_client import (
        get_corp_code_by_stock, fetch_periodic_reports, fetch_fnltt_rows,
        compare_fnltt_rows, reprt_code_to_name,
        fetch_disclosure_document_text, compare_document_text,
    )
    from dashboard.usdc_client import fetch_stablecoin_supply_history, fetch_usdc_supply_history
    from dashboard.semiconductor_price_client import fetch_semiconductor_contract_prices
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
        upsert_us_market_daily, get_us_market_daily, get_us_market_daily_by_date,
        update_us_market_summary,
        upsert_kr_market_daily, get_kr_market_daily, get_kr_market_daily_by_date,
        add_insider_buy_record, get_insider_buy_records, delete_insider_buy_record,
        get_insider_buy_record_by_source_url,
        update_insider_buy_record_by_source_url,
        add_quarterly_perf_watch, get_quarterly_perf_watchlist, delete_quarterly_perf_watch,
        upsert_quarterly_perf_data, get_quarterly_perf_data, get_quarterly_perf_quarters,
        upsert_quarterly_perf_reason, get_quarterly_perf_reasons,
        upsert_stock_monitor_return, get_stock_monitor_returns,
        add_overhang_lockup, get_overhang_lockups, delete_overhang_lockup,
        add_overhang_exercise, get_overhang_exercises, delete_overhang_exercise,
        upsert_usdc_supply_daily, get_usdc_supply_daily,
        upsert_stablecoin_supply_daily, get_stablecoin_supply_daily,
        upsert_semiconductor_price_daily, get_semiconductor_price_daily,
        get_latest_semiconductor_price_date,
    )
    from kita_client import fetch_range, fetch_region_month, fetch_industry_range, fetch_industry_month, get_daily_request_count
    from stock_client import (
        fetch_stock_prices, fetch_daily_stock_prices, search_stock_by_name,
        fetch_index_prices, fetch_daily_index_prices,
    )
    from carbon_client import (
        fetch_carbon_prices, fetch_all_carbon_items,
        fetch_yahoo_symbol_history, fetch_sceex_domestic_history, fetch_sceex_international_history,
    )
    from tourism_client import fetch_country_list, fetch_all_countries_month, fetch_tourism_range
    from nps_client import search_company as nps_search, fetch_nps_data
    from notifier import notify_update, notify_visit_update_sync, send_telegram
    from youtube_client import resolve_channel, fetch_latest_videos
    from blog_client import discover_feed, fetch_articles_rss, fetch_articles_scrape, fetch_article_content
    from alpha_vantage_client import fetch_sp500_daily, fetch_nasdaq_daily, fetch_sector_performance, fetch_daily_index_series
    from dart_client import fetch_trading_trend_candidates
    from quarterly_perf_client import fetch_fnguide_quarterly, search_reason_snippets
    from disclosure_compare_client import (
        get_corp_code_by_stock, fetch_periodic_reports, fetch_fnltt_rows,
        compare_fnltt_rows, reprt_code_to_name,
        fetch_disclosure_document_text, compare_document_text,
    )
    from usdc_client import fetch_stablecoin_supply_history, fetch_usdc_supply_history
    from semiconductor_price_client import fetch_semiconductor_contract_prices

scheduler = AsyncIOScheduler()
quarterly_refresh_job = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "params": None,
    "result": None,
    "error": None,
}


def _run_quarterly_refresh_job(auto_reason: bool, start: int, limit: int | None):
    quarterly_refresh_job["running"] = True
    quarterly_refresh_job["started_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    quarterly_refresh_job["finished_at"] = None
    quarterly_refresh_job["params"] = {"auto_reason": auto_reason, "start": start, "limit": limit}
    quarterly_refresh_job["result"] = None
    quarterly_refresh_job["error"] = None
    try:
        result = asyncio.run(sync_quarterly_perf_data(auto_reason=auto_reason, start=start, limit=limit))
        quarterly_refresh_job["result"] = result
    except Exception as e:
        quarterly_refresh_job["error"] = str(e)
    finally:
        quarterly_refresh_job["running"] = False
        quarterly_refresh_job["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")


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


def _prev_month_pair(ref: datetime.date | None = None) -> tuple[int, int]:
    today = ref or datetime.date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _next_month_pair(year: int, month: int) -> tuple[int, int]:
    if month >= 12:
        return year + 1, 1
    return year, month + 1


def _latest_tourism_period() -> tuple[int, int] | None:
    latest = None
    for country in get_tourism_countries():
        data = get_tourism_data(country["id"])
        if not data:
            continue
        row = data[-1]
        candidate = (int(row["year"]), int(row["month"]))
        if latest is None or candidate > latest:
            latest = candidate
    return latest


async def _fetch_and_store_tourism_month(year: int, month: int) -> dict:
    countries = get_tourism_countries()
    if not countries:
        for nat_cd, nat_nm, tar_cd in TOP10:
            add_tourism_country(nat_cd, nat_nm, tar_cd)
        countries = get_tourism_countries()
    name_to_id = {c["nat_nm"]: c["id"] for c in countries}
    rows = await fetch_all_countries_month(str(year), str(month).zfill(2))
    if not rows:
        return {
            "year": year,
            "month": str(month).zfill(2),
            "available": False,
            "source_rows": 0,
            "matched_rows": 0,
        }

    matched = 0
    for row in rows:
        cid = name_to_id.get(row["nat_nm"])
        if not cid:
            continue
        upsert_tourism_data(
            cid,
            row["year"],
            row["month"],
            row["visitors"],
            row["prev_visitors"],
            row["change_rate"],
        )
        matched += 1
    return {
        "year": year,
        "month": str(month).zfill(2),
        "available": matched > 0,
        "source_rows": len(rows),
        "matched_rows": matched,
    }


async def check_and_update_tourism_latest(max_probe_months: int = 3) -> dict:
    latest_stored = _latest_tourism_period()
    latest_publishable = _prev_month_pair()
    if latest_stored and latest_stored >= latest_publishable:
        return {
            "latest_stored": f"{latest_stored[0]}-{latest_stored[1]:02d}",
            "latest_publishable": f"{latest_publishable[0]}-{latest_publishable[1]:02d}",
            "checked": [],
            "updated_months": [],
            "message": "already up to date",
        }

    if latest_stored:
        year, month = _next_month_pair(*latest_stored)
    else:
        year, month = latest_publishable

    checked = []
    updated_months = []
    probes = 0
    while (year, month) <= latest_publishable and probes < max_probe_months:
        result = await _fetch_and_store_tourism_month(year, month)
        checked.append(result)
        if result["available"]:
            updated_months.append(f"{year}-{month:02d}")
            year, month = _next_month_pair(year, month)
            probes += 1
            continue
        break

    latest_after = _latest_tourism_period()
    return {
        "latest_stored": f"{latest_stored[0]}-{latest_stored[1]:02d}" if latest_stored else None,
        "latest_after": f"{latest_after[0]}-{latest_after[1]:02d}" if latest_after else None,
        "latest_publishable": f"{latest_publishable[0]}-{latest_publishable[1]:02d}",
        "checked": checked,
        "updated_months": updated_months,
    }


async def scheduled_tourism_availability_check():
    """Daily job: check whether a newly published tourism month is available."""
    try:
        result = await check_and_update_tourism_latest(max_probe_months=3)
        print(
            f"[scheduler] Tourism availability check: latest={result.get('latest_after') or result.get('latest_stored')}, "
            f"updated={','.join(result.get('updated_months', [])) or '-'}"
        )
    except Exception as e:
        print(f"[scheduler] Tourism availability check failed: {e}")


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


def _derive_sector_rankings(sectors: dict, top_n: int = 3):
    """Build deterministic strong/weak sector lists from a sector->pct map."""
    if not isinstance(sectors, dict):
        return [], []
    rows = []
    for name, pct in sectors.items():
        if not name:
            continue
        try:
            rows.append({"name": str(name), "change_pct": round(float(pct), 2)})
        except (ValueError, TypeError):
            continue
    if not rows:
        return [], []
    strong = sorted(rows, key=lambda x: x["change_pct"], reverse=True)[:top_n]
    weak = sorted(rows, key=lambda x: x["change_pct"])[:top_n]
    return strong, weak


def _normalize_sector_items(items):
    """Normalize model output to [{'name': str, 'change_pct': float}]."""
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
            pct = item.get("change_pct")
        else:
            name = str(item)
            pct = 0
        if not name:
            continue
        try:
            pct = round(float(pct), 2)
        except (ValueError, TypeError):
            pct = 0.0
        normalized.append({"name": str(name), "change_pct": pct})
    return normalized


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


def _summarize_us_market(sp500: dict, nasdaq: dict, sectors: dict) -> dict:
    """Claude API로 미국 시장 일일 요약 생성."""
    fallback_strong, fallback_weak = _derive_sector_rankings(sectors, top_n=3)
    if not SUMMARIZE_ENABLED or not _anthropic_client:
        return {
            "summary": f"S&P 500: {sp500.get('close', 0)} ({sp500.get('change_pct', 0):+.2f}%), "
                       f"NASDAQ: {nasdaq.get('close', 0)} ({nasdaq.get('change_pct', 0):+.2f}%)",
            "key_factors": [],
            "sectors_strong": fallback_strong,
            "sectors_weak": fallback_weak,
            "earnings_text": "",
        }
    try:
        sector_text = "\n".join(f"  - {k}: {v:+.2f}%" for k, v in sorted(sectors.items(), key=lambda x: x[1], reverse=True))
        prompt = (
            f"오늘 미국 주식시장 마감 데이터를 분석하여 한국어로 시장 브리핑을 작성해줘.\n\n"
            f"S&P 500 (SPY ETF): 종가 {sp500.get('close')}, 전일대비 {sp500.get('change_pct'):+.2f}%\n"
            f"NASDAQ (QQQ ETF): 종가 {nasdaq.get('close')}, 전일대비 {nasdaq.get('change_pct'):+.2f}%\n\n"
            f"섹터별 성과:\n{sector_text}\n\n"
            f"다음 JSON 형식으로 응답해줘:\n"
            f'{{"summary": "전체 시장 요약 3~5문장", '
            f'"key_factors": ["주요 변동 요인1", "요인2", "요인3"], '
            f'"sectors_strong": [{{"name": "섹터명", "change_pct": 1.23}}], '
            f'"sectors_weak": [{{"name": "섹터명", "change_pct": -1.23}}], '
            f'"earnings_text": "해당일 주요 실적발표/컨퍼런스콜 내용 요약 (없으면 빈 문자열)"}}'
        )
        resp = _anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # JSON 추출
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
            parsed["sectors_strong"] = _normalize_sector_items(parsed.get("sectors_strong")) or fallback_strong
            parsed["sectors_weak"] = _normalize_sector_items(parsed.get("sectors_weak")) or fallback_weak
            return parsed
        return {
            "summary": text,
            "key_factors": [],
            "sectors_strong": fallback_strong,
            "sectors_weak": fallback_weak,
            "earnings_text": "",
        }
    except Exception as e:
        print(f"[us_market] Summary error: {e}")
        return {
            "summary": f"S&P 500: {sp500.get('close', 0)} ({sp500.get('change_pct', 0):+.2f}%), "
                       f"NASDAQ: {nasdaq.get('close', 0)} ({nasdaq.get('change_pct', 0):+.2f}%)",
            "key_factors": [],
            "sectors_strong": fallback_strong,
            "sectors_weak": fallback_weak,
            "earnings_text": "",
        }


def _is_alpha_limit_error(err: Exception | str) -> bool:
    msg = str(err).lower()
    return (
        "호출 한도 초과" in msg
        or "api call frequency" in msg
        or "rate limit" in msg
        or "25 requests per day" in msg
    )


async def _backfill_us_market_missing_dates(
    api_key: str,
    lookback_trading_days: int = 7,
    skip_date: str | None = None,
    spy_rows: list[dict] | None = None,
    qqq_rows: list[dict] | None = None,
) -> list[str]:
    """
    Fill missing recent US-market rows using SPY/QQQ daily series.
    Historical sector ranking/AI summary is not reliably available,
    so only index fields + fallback summary are backfilled.
    """
    lookback = max(1, min(int(lookback_trading_days), 20))
    if spy_rows is None or qqq_rows is None:
        series_limit = max(lookback + 3, 12)
        spy_rows = await fetch_daily_index_series("SPY", api_key, limit=series_limit)
        await asyncio.sleep(1.1)
        qqq_rows = await fetch_daily_index_series("QQQ", api_key, limit=series_limit)

    spy_map = {r["date"]: r for r in spy_rows}
    qqq_map = {r["date"]: r for r in qqq_rows}
    common_dates = sorted(set(spy_map.keys()) & set(qqq_map.keys()), reverse=True)[:lookback]

    inserted_dates: list[str] = []
    for d in common_dates:
        if skip_date and d == skip_date:
            continue
        existing = get_us_market_daily_by_date(d)
        if existing:
            continue
        sp = spy_map[d]
        nq = qqq_map[d]
        summary = (
            f"S&P 500: {sp.get('close', 0)} ({sp.get('change_pct', 0):+.2f}%), "
            f"NASDAQ: {nq.get('close', 0)} ({nq.get('change_pct', 0):+.2f}%)"
        )
        upsert_us_market_daily(
            trading_date=d,
            sp500_close=sp.get("close", 0),
            sp500_change_pct=sp.get("change_pct", 0),
            nasdaq_close=nq.get("close", 0),
            nasdaq_change_pct=nq.get("change_pct", 0),
            summary_text=summary,
            key_factors="[]",
            sectors_strong="[]",
            sectors_weak="[]",
            earnings_text="",
        )
        inserted_dates.append(d)
    return inserted_dates


async def scheduled_us_market_check():
    """매일 오전 8시 (KST): 미국 시장 데이터 수집 + AI 요약 생성."""
    try:
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        if not api_key:
            print("[us_market] ALPHA_VANTAGE_API_KEY not configured, skipping")
            return

        sp500 = await fetch_sp500_daily(api_key)
        await asyncio.sleep(2)
        nasdaq = await fetch_nasdaq_daily(api_key)
        await asyncio.sleep(2)
        sectors = await fetch_sector_performance(api_key)

        # AI 요약 생성
        result = _summarize_us_market(sp500, nasdaq, sectors)

        trading_date = sp500["date"]
        upsert_us_market_daily(
            trading_date=trading_date,
            sp500_close=sp500["close"],
            sp500_change_pct=sp500["change_pct"],
            nasdaq_close=nasdaq["close"],
            nasdaq_change_pct=nasdaq["change_pct"],
            summary_text=result.get("summary", ""),
            key_factors=json.dumps(result.get("key_factors", []), ensure_ascii=False),
            sectors_strong=json.dumps(result.get("sectors_strong", []), ensure_ascii=False),
            sectors_weak=json.dumps(result.get("sectors_weak", []), ensure_ascii=False),
            earnings_text=result.get("earnings_text", ""),
        )
        print(f"[us_market] Updated for {trading_date}")

    except Exception as e:
        print(f"[us_market] Error: {e}")


async def scheduled_kr_market_check():
    """매일 오후 4시 (KST): 국내 시장 데이터 수집."""
    try:
        result = await api_market_refresh_daily()
        print(f"[kr_market] Updated: {result}")
    except Exception as e:
        print(f"[kr_market] Error: {e}")


async def sync_trading_trend_from_dart(days: int = 14):
    """Fetch insider-related disclosures from DART and ingest unseen candidates."""
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        return {"inserted": 0, "skipped": 0, "total": 0, "message": "DART_API_KEY not configured"}

    candidates = await fetch_trading_trend_candidates(api_key=api_key, days=days, page_count=100)
    inserted = 0
    updated = 0
    skipped = 0
    for item in candidates:
        src = (item.get("source_url") or "").strip()
        existing = get_insider_buy_record_by_source_url(src) if src else None
        if existing:
            # Backfill numerical columns when previously unknown.
            has_new_signal = (
                abs(float(item.get("change_ratio", 0) or 0)) > 0
                or abs(int(item.get("change_shares", 0) or 0)) > 0
            )
            needs_update = (
                abs(float(existing.get("change_ratio", 0) or 0)) == 0
                and abs(int(existing.get("change_shares", 0) or 0)) == 0
            )
            if has_new_signal and needs_update:
                ok = update_insider_buy_record_by_source_url(
                    src,
                    related_party=item.get("related_party", ""),
                    relation_type=item.get("relation_type", ""),
                    change_shares=item.get("change_shares", 0),
                    change_ratio=item.get("change_ratio", 0),
                    avg_price=item.get("avg_price", 0),
                    amount_krw=item.get("amount_krw", 0),
                    note=item.get("note", ""),
                )
                if ok:
                    updated += 1
                else:
                    skipped += 1
            else:
                skipped += 1
            continue
        add_insider_buy_record(
            trade_date=item.get("trade_date", ""),
            company_name=item.get("company_name", ""),
            stock_code=item.get("stock_code", ""),
            related_party=item.get("related_party", ""),
            relation_type=item.get("relation_type", ""),
            change_shares=item.get("change_shares", 0),
            change_ratio=item.get("change_ratio", 0),
            avg_price=item.get("avg_price", 0),
            amount_krw=item.get("amount_krw", 0),
            source_title=item.get("source_title", ""),
            source_url=src,
            note=item.get("note", ""),
        )
        inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total": len(candidates), "message": "ok"}


async def scheduled_trading_trend_check():
    """Daily trading-trend auto ingest from DART."""
    try:
        result = await sync_trading_trend_from_dart(days=14)
        print(f"[trading_trend] sync result: {result}")
    except Exception as e:
        print(f"[trading_trend] Error: {e}")


async def scheduled_stock_monitor_check():
    """매일 새벽: 종목주가(워치리스트) 수익률 캐시 갱신."""
    try:
        watch_count = len(get_quarterly_perf_watchlist())
        if watch_count == 0:
            print("[stock_monitor] no watchlist items")
            return
        batch = 200
        start = 0
        total_processed = 0
        total_upserted = 0
        total_failed = 0
        while start < watch_count:
            out = await _refresh_stock_monitor_range(start=start, limit=batch)
            total_processed += int(out.get("processed_count", 0))
            total_upserted += int(out.get("upserted", 0))
            total_failed += int(out.get("failed", 0))
            start += batch
        print(
            f"[stock_monitor] refreshed: processed={total_processed}, "
            f"upserted={total_upserted}, failed={total_failed}, watch={watch_count}"
        )
    except Exception as e:
        print(f"[stock_monitor] Error: {e}")


async def scheduled_overhang_check():
    """매일 새벽 4시(KST): 전종목 오버행 DART 자동 동기화."""
    try:
        watch = get_quarterly_perf_watchlist()
        if not watch:
            print("[overhang] no watchlist items")
            return

        ok = 0
        failed = 0
        lockup_added = 0
        exercise_added = 0

        for idx, w in enumerate(watch, start=1):
            code = (w.get("stock_code") or "").zfill(6)
            name = (w.get("stock_name") or "").strip()
            if not re.match(r"^\d{6}$", code):
                failed += 1
                continue
            try:
                out = await _sync_overhang_from_dart(code, name)
                ok += 1
                lockup_added += int(out.get("inserted_lockups", 0) or 0)
                exercise_added += int(out.get("inserted_exercises", 0) or 0)
                if idx % 100 == 0:
                    print(
                        f"[overhang] progress {idx}/{len(watch)} "
                        f"(ok={ok}, failed={failed}, lockup+={lockup_added}, ex+={exercise_added})"
                    )
            except Exception as e:
                failed += 1
                print(f"[overhang] sync error {code} {name}: {e}")
            # Avoid bursty API calls to OpenDART
            await asyncio.sleep(0.2)

        print(
            f"[overhang] daily sync done: total={len(watch)}, ok={ok}, failed={failed}, "
            f"lockup_added={lockup_added}, exercise_added={exercise_added}"
        )
    except Exception as e:
        print(f"[overhang] Error: {e}")


def _quarter_prev_year(quarter_key: str) -> str:
    m = re.match(r"^(\d{4})Q([1-4])$", quarter_key or "")
    if not m:
        return ""
    return f"{int(m.group(1)) - 1}Q{m.group(2)}"


def _calc_yoy(curr: float, prev: float) -> float | None:
    if prev is None or prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 2)


def _guess_quarter_reason(company_name: str, quarter_key: str, row: dict, snippets: list[str]) -> str:
    rev_yoy = row.get("revenue_yoy")
    op_yoy = row.get("operating_profit_yoy")
    net_yoy = row.get("net_income_yoy")

    if SUMMARIZE_ENABLED and _anthropic_client and snippets:
        try:
            prompt = (
                f"{company_name}의 {quarter_key} 분기 실적 요약 이유를 한국어 2문장으로 작성해줘.\\n"
                f"조건: 사실 기반으로만 작성, 불확실하면 가능성 표현 사용.\\n"
                f"지표: 매출 YoY {rev_yoy}%, 영업이익 YoY {op_yoy}%, 순이익 YoY {net_yoy}%\\n"
                f"참고 스니펫:\\n- " + "\\n- ".join(snippets[:5])
            )
            resp = _anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=220,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            if text:
                return text
        except Exception as e:
            print(f"[quarterly_perf] reason summarize error: {e}")

    # Fallback heuristic text
    parts = []
    if isinstance(rev_yoy, (int, float)):
        parts.append(f"매출 YoY {rev_yoy:+.2f}%")
    if isinstance(op_yoy, (int, float)):
        parts.append(f"영업이익 YoY {op_yoy:+.2f}%")
    if isinstance(net_yoy, (int, float)):
        parts.append(f"순이익 YoY {net_yoy:+.2f}%")
    base = ", ".join(parts) if parts else "핵심 지표 변동"
    if snippets:
        return f"{base}. 관련 기사/공시 요약: {snippets[0][:180]}"
    return f"{base}. 공시/뉴스 기반 추가 확인이 필요합니다."


def _build_quarterly_perf_overview(quarter_key: str, sort_by: str):
    data = get_quarterly_perf_data()
    reasons = {r["stock_code"]: r for r in get_quarterly_perf_reasons(quarter_key)}

    by_stock = {}
    for r in data:
        by_stock.setdefault(r["stock_code"], []).append(r)
    for code in by_stock:
        by_stock[code].sort(key=lambda x: x["quarter_key"], reverse=True)

    rows = []
    for code, arr in by_stock.items():
        selected = next((x for x in arr if x["quarter_key"] == quarter_key), None)
        if not selected:
            continue
        prev_key = _quarter_prev_year(quarter_key)
        prev = next((x for x in arr if x["quarter_key"] == prev_key), None)

        row = {
            "stock_code": code,
            "stock_name": selected["stock_name"],
            "quarter_key": quarter_key,
            "revenue": selected["revenue"],
            "operating_profit": selected["operating_profit"],
            "net_income": selected["net_income"],
            "revenue_yoy": _calc_yoy(selected["revenue"], prev["revenue"]) if prev else None,
            "operating_profit_yoy": _calc_yoy(selected["operating_profit"], prev["operating_profit"]) if prev else None,
            "net_income_yoy": _calc_yoy(selected["net_income"], prev["net_income"]) if prev else None,
            "recent_4q": arr[:4],
            "reason_text": (reasons.get(code) or {}).get("reason_text", ""),
            "reason_auto_generated": bool((reasons.get(code) or {}).get("auto_generated", 0)),
        }
        rows.append(row)

    sort_map = {
        "revenue": "revenue_yoy",
        "operating_profit": "operating_profit_yoy",
        "net_income": "net_income_yoy",
    }
    sort_key = sort_map.get(sort_by, "revenue_yoy")
    rows.sort(key=lambda x: (x.get(sort_key) is None, -(x.get(sort_key) or -10**9), x["stock_name"]))
    return rows


def _build_quarterly_perf_stock_detail(quarter_key: str, stock_code: str):
    code = (stock_code or "").zfill(6)
    data = [r for r in get_quarterly_perf_data() if (r.get("stock_code") or "").zfill(6) == code]
    if not data:
        return None
    data.sort(key=lambda x: x["quarter_key"], reverse=True)
    selected = next((x for x in data if x["quarter_key"] == quarter_key), None)
    if not selected:
        return None

    prev_key = _quarter_prev_year(quarter_key)
    prev = next((x for x in data if x["quarter_key"] == prev_key), None)
    reason_map = {r["stock_code"]: r for r in get_quarterly_perf_reasons(quarter_key)}
    reason = reason_map.get(code) or reason_map.get((selected.get("stock_code") or "").zfill(6)) or {}

    return {
        "stock_code": code,
        "stock_name": selected["stock_name"],
        "quarter_key": quarter_key,
        "revenue": selected["revenue"],
        "operating_profit": selected["operating_profit"],
        "net_income": selected["net_income"],
        "revenue_yoy": _calc_yoy(selected["revenue"], prev["revenue"]) if prev else None,
        "operating_profit_yoy": _calc_yoy(selected["operating_profit"], prev["operating_profit"]) if prev else None,
        "net_income_yoy": _calc_yoy(selected["net_income"], prev["net_income"]) if prev else None,
        "recent_4q": data[:4],
        "reason_text": reason.get("reason_text", ""),
        "reason_auto_generated": bool(reason.get("auto_generated", 0)),
    }


def _to_iso_date(yyyymmdd: str) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return ""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _summarize_kr_market(kospi: dict, kosdaq: dict, semi_export_rate: float | None = None, total_export_rate: float | None = None):
    k_pct = float(kospi.get("change_pct", 0) or 0)
    q_pct = float(kosdaq.get("change_pct", 0) or 0)
    score = k_pct + q_pct
    if semi_export_rate is not None:
        score += float(semi_export_rate) * 0.08
    if total_export_rate is not None:
        score += float(total_export_rate) * 0.08

    if score >= 0.7:
        tone = "강세"
        tone_text = "지수 전반이 견조해 위험선호 흐름이 우세했습니다."
    elif score <= -0.7:
        tone = "약세"
        tone_text = "지수 전반이 약세를 보이며 방어적 심리가 우세했습니다."
    else:
        tone = "혼조"
        tone_text = "지수 등락이 엇갈리며 방향성이 제한됐습니다."

    lead_text = ""
    if abs(k_pct) >= abs(q_pct):
        lead_text = f"KOSPI({k_pct:+.2f}%)가 상대적으로 흐름을 주도했습니다."
    else:
        lead_text = f"KOSDAQ({q_pct:+.2f}%)가 상대적으로 흐름을 주도했습니다."

    extra = []
    if semi_export_rate is not None:
        extra.append(f"반도체 수출 YoY {float(semi_export_rate):+.1f}%")
    if total_export_rate is not None:
        extra.append(f"총수출 YoY {float(total_export_rate):+.1f}%")
    macro = f"대외지표는 {', '.join(extra)} 수준입니다." if extra else ""

    summary = (
        f"KOSPI {float(kospi.get('close', 0)):.2f}pt({k_pct:+.2f}%), "
        f"KOSDAQ {float(kosdaq.get('close', 0)):.2f}pt({q_pct:+.2f}%). "
        f"{lead_text} {macro} {tone_text}"
    ).strip()
    factors = [
        f"시장 톤: {tone}",
        f"KOSPI: {float(kospi.get('close', 0)):.2f}pt ({k_pct:+.2f}%)",
        f"KOSDAQ: {float(kosdaq.get('close', 0)):.2f}pt ({q_pct:+.2f}%)",
    ]
    if semi_export_rate is not None:
        factors.append(f"반도체 수출 YoY: {float(semi_export_rate):+.1f}%")
    if total_export_rate is not None:
        factors.append(f"총수출 YoY: {float(total_export_rate):+.1f}%")
    return summary, factors


def _latest_export_rate(category: str):
    rows = get_market_export(category)
    if not rows:
        return None
    latest = rows[-1]
    try:
        return float(latest.get("export_rate"))
    except (TypeError, ValueError):
        return None


KR_SECTOR_ETFS = {
    "반도체": "091160",
    "2차전지": "305720",
    "자동차": "091180",
    "은행": "091170",
    "바이오": "266420",
    "인터넷": "266370",
    "건설": "117700",
    "철강": "117680",
    "에너지화학": "117460",
    "미디어엔터": "266360",
    "게임": "300640",
    "배당": "161510",
}


async def _fetch_kr_sector_rankings_by_date(count: int = 90, top_n: int = 2):
    """
    Build per-date sector strong/weak ranking using representative KR sector ETFs.
    Returns: { 'YYYYMMDD': {'strong': [{'name','change_pct'}], 'weak': [...] } }
    """
    async def _one(name: str, code: str):
        try:
            rows = await fetch_daily_stock_prices(code, count=count)
            return name, rows
        except Exception:
            return name, []

    pairs = await asyncio.gather(*[_one(name, code) for name, code in KR_SECTOR_ETFS.items()])
    by_date: dict[str, list[dict]] = {}
    for sector_name, rows in pairs:
        rows_sorted = sorted(
            [x for x in rows if x.get("close") not in (None, 0) and x.get("date")],
            key=lambda x: x["date"],
        )
        prev_close = None
        for row in rows_sorted:
            close = float(row["close"])
            if prev_close and prev_close > 0:
                ch = round((close - prev_close) / prev_close * 100.0, 2)
                by_date.setdefault(row["date"], []).append({"name": sector_name, "change_pct": ch})
            prev_close = close

    out: dict[str, dict] = {}
    for d, arr in by_date.items():
        if not arr:
            continue
        strong = sorted(arr, key=lambda x: x["change_pct"], reverse=True)[:top_n]
        weak = sorted(arr, key=lambda x: x["change_pct"])[:top_n]
        out[d] = {"strong": strong, "weak": weak}
    return out


def _calc_period_return_from_daily(series: list[dict], days: int) -> float | None:
    if not series:
        return None
    latest = series[-1]
    latest_close = float(latest["close"])
    latest_date = latest["d"]
    target = latest_date - datetime.timedelta(days=days)
    base_close = None
    for r in reversed(series):
        if r["d"] <= target:
            base_close = float(r["close"])
            break
    if not base_close or base_close <= 0:
        return None
    return round((latest_close - base_close) / base_close * 100.0, 2)


async def _build_stock_monitor_detail(stock_code: str):
    rows = await fetch_daily_stock_prices(stock_code, count=1600)
    cleaned = []
    for r in rows:
        d = (r.get("date") or "").strip()
        c = r.get("close")
        if not d or c in (None, 0):
            continue
        try:
            d_obj = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
            cleaned.append({"date": d, "d": d_obj, "close": float(c)})
        except Exception:
            continue
    cleaned.sort(key=lambda x: x["date"])
    if not cleaned:
        return None

    latest = cleaned[-1]
    returns = {
        "1w": _calc_period_return_from_daily(cleaned, 7),
        "1m": _calc_period_return_from_daily(cleaned, 30),
        "6m": _calc_period_return_from_daily(cleaned, 182),
        "1y": _calc_period_return_from_daily(cleaned, 365),
        "3y": _calc_period_return_from_daily(cleaned, 1095),
        "5y": _calc_period_return_from_daily(cleaned, 1825),
    }
    trend = [{"date": _to_iso_date(r["date"]), "close": r["close"]} for r in cleaned]
    return {
        "stock_code": stock_code,
        "as_of_date": _to_iso_date(latest["date"]),
        "latest_close": latest["close"],
        "returns": returns,
        "trend": trend,
    }


async def sync_quarterly_perf_data(auto_reason: bool = True, start: int = 0, limit: int | None = None):
    watch = get_quarterly_perf_watchlist()
    total_watch = len(watch)
    s_idx = max(0, int(start or 0))
    if limit is None:
        target_watch = watch[s_idx:]
    else:
        lmt = max(0, int(limit))
        target_watch = watch[s_idx : s_idx + lmt]
    inserted_or_updated = 0
    reason_upserts = 0
    for w in target_watch:
        code = (w.get("stock_code") or "").zfill(6)
        name = w.get("stock_name") or code
        try:
            rows = fetch_fnguide_quarterly(code)
        except Exception as e:
            print(f"[quarterly_perf] fetch error {code}: {e}")
            continue
        for r in rows:
            upsert_quarterly_perf_data(
                stock_code=code,
                stock_name=name,
                quarter_key=r["quarter_key"],
                revenue=r["revenue"],
                operating_profit=r["operating_profit"],
                net_income=r["net_income"],
                source_url=r.get("source_url", ""),
            )
            inserted_or_updated += 1

        if auto_reason and rows:
            latest_q = rows[0]["quarter_key"]
            ov = _build_quarterly_perf_overview(latest_q, "revenue")
            current = next((x for x in ov if x["stock_code"] == code), None)
            if current:
                snippets = []
                try:
                    snippets = search_reason_snippets(name, latest_q, max_results=5)
                except Exception as e:
                    print(f"[quarterly_perf] reason search error {code}: {e}")
                reason = _guess_quarter_reason(name, latest_q, current, snippets)
                if reason:
                    upsert_quarterly_perf_reason(code, latest_q, reason, auto_generated=True)
                    reason_upserts += 1

    return {
        "upserted_data": inserted_or_updated,
        "upserted_reasons": reason_upserts,
        "watch_count": total_watch,
        "processed_count": len(target_watch),
        "start": s_idx,
        "limit": limit,
    }


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
        scheduled_tourism_availability_check,
        "cron",
        hour=10,
        minute=10,
        timezone="Asia/Seoul",
        id="daily_tourism_availability",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_us_market_check,
        "cron",
        hour=8,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_us_market",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_kr_market_check,
        "cron",
        hour=16,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_kr_market",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_youtube_check,
        "interval",
        hours=1,
        id="youtube_check",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_trading_trend_check,
        "cron",
        hour=3,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_trading_trend",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_stock_monitor_check,
        "cron",
        hour=2,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_stock_monitor",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_usdc_supply_check,
        "cron",
        hour=3,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_usdc_supply",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_semiconductor_prices_check,
        "cron",
        hour=3,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_semiconductor_prices",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_overhang_check,
        "cron",
        hour=4,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_overhang",
        replace_existing=True,
    )
    scheduler.start()
    print(
        "[scheduler] Started - monthly fetch 17th 09:00, visit alarms 08:00, "
        "tourism availability 10:10, us-market 08:00, kr-market 16:00, youtube hourly, "
        "trading-trend 03:00, stock-monitor 02:00, usdc 03:00, semi-price 03:00, overhang 04:00"
    )
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


@app.get("/api/carbon/global")
async def api_get_global_carbon_prices(days: int = 180):
    """Fetch global carbon-related regional prices for US, Europe, and China."""
    if days <= 0:
        days = 365
    outputs = await asyncio.gather(
        fetch_yahoo_symbol_history("KCCA", range_str="1y", interval="1d"),
        fetch_sceex_international_history("ECX-EUA", max_pages=max(3, min(30, math.ceil(days / 10) + 2))),
        fetch_sceex_domestic_history("SHEA", max_pages=max(3, min(30, math.ceil(days / 14) + 2))),
        fetch_yahoo_symbol_history("USDKRW=X", range_str="1mo", interval="1d"),
        fetch_yahoo_symbol_history("EURKRW=X", range_str="1mo", interval="1d"),
        fetch_yahoo_symbol_history("CNYKRW=X", range_str="1mo", interval="1d"),
        return_exceptions=True,
    )
    us_history, eu_history, cn_history, usdkrw_history, eurkrw_history, cnykrw_history = [
        ([] if isinstance(item, Exception) else item) for item in outputs
    ]

    fx_rates = {
        "USD": ((usdkrw_history or [{}])[-1] or {}).get("close"),
        "EUR": ((eurkrw_history or [{}])[-1] or {}).get("close"),
        "CNY": ((cnykrw_history or [{}])[-1] or {}).get("close"),
    }

    def _trim(rows):
        if not rows:
            return []
        return rows[-days:] if days > 0 else rows

    def _pack(region_key, region_name, unit, rows, source_name, fx_code, is_proxy=False, note=None):
        trimmed = _trim(rows)
        fx_rate = fx_rates.get(fx_code)
        for row in trimmed:
            close = row.get("close")
            row["close_krw"] = round(close * fx_rate, 2) if close is not None and fx_rate is not None else None
        latest = trimmed[-1] if trimmed else None
        return {
            "region_key": region_key,
            "region_name": region_name,
            "unit": unit,
            "display_unit": "KRW/t",
            "fx_code": fx_code,
            "fx_rate_to_krw": fx_rate,
            "source_name": source_name,
            "is_proxy": is_proxy,
            "note": note,
            "latest": latest,
            "history": trimmed,
        }

    return {
        "days": days,
        "fx_rates": fx_rates,
        "partial": any(isinstance(item, Exception) for item in outputs),
        "regions": [
            _pack("us", "미국", "USD", us_history, "Yahoo Finance / KCCA", "USD", is_proxy=True, note="California Carbon Allowance ETF proxy"),
            _pack("eu", "유럽", "EUR/t", eu_history, "SCEEX 국제行情 / ECX-EUA", "EUR"),
            _pack("cn", "중국", "CNY/t", cn_history, "SCEEX 국내行情 / SHEA", "CNY", note="상하이 환경에너지거래소 기준"),
        ],
    }

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


def _escape_html_text(v: str) -> str:
    return (
        str(v or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


_AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".oga", ".webm", ".mp4", ".m4b", ".flac"}


def _is_audio_upload(filename: str, content_type: str | None) -> bool:
    name = (filename or "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    ctype = (content_type or "").lower().strip()
    return ext in _AUDIO_EXTS or ctype.startswith("audio/")


async def _transcribe_audio_file(filename: str, raw: bytes, content_type: str | None) -> str:
    gemini_api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    gemini_model = (os.environ.get("GEMINI_AUDIO_TRANSCRIBE_MODEL") or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    openai_api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    openai_model = (os.environ.get("OPENAI_AUDIO_TRANSCRIBE_MODEL") or "gpt-4o-mini-transcribe").strip() or "gpt-4o-mini-transcribe"
    language = (os.environ.get("OPENAI_AUDIO_LANGUAGE") or "").strip()
    file_name = filename or "audio.m4a"
    file_type = (content_type or "application/octet-stream").strip()

    async def _call_openai_transcribe(target_model: str) -> str:
        data = {"model": target_model}
        if language:
            data["language"] = language
        files = {"file": (file_name, raw, file_type)}
        headers = {"Authorization": f"Bearer {openai_api_key}"}
        async with httpx.AsyncClient(timeout=240) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
            )
        if resp.status_code >= 400:
            detail = ""
            try:
                j = resp.json()
                detail = (j.get("error") or {}).get("message") or ""
            except Exception:
                detail = (resp.text or "")[:300]
            raise RuntimeError(f"STT 실패({resp.status_code}): {detail or 'unknown error'}")
        payload = resp.json()
        text = (payload.get("text") or "").strip()
        if not text:
            raise RuntimeError("음성 전사 결과 텍스트가 비어 있습니다")
        return text

    async def _call_gemini_transcribe(target_model: str) -> str:
        prompt = (
            "다음 한국어 음성 파일을 가능한 한 원문 그대로 전사해 주세요. "
            "화자 구분이 가능하면 줄바꿈으로 분리하고, 불필요한 요약이나 해석 없이 텍스트만 반환하세요."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": file_type,
                                "data": base64.b64encode(raw).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.0},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent"
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(url, params={"key": gemini_api_key}, json=payload)
        if resp.status_code >= 400:
            detail = ""
            try:
                j = resp.json()
                detail = (j.get("error") or {}).get("message") or ""
            except Exception:
                detail = (resp.text or "")[:300]
            raise RuntimeError(f"Gemini STT 실패({resp.status_code}): {detail or 'unknown error'}")
        payload = resp.json()
        candidates = payload.get("candidates") or []
        parts = []
        if candidates:
            parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "\n".join((p.get("text") or "").strip() for p in parts if (p.get("text") or "").strip()).strip()
        if not text:
            raise RuntimeError("Gemini 전사 결과 텍스트가 비어 있습니다")
        return text

    errors = []

    if gemini_api_key:
        try:
            return await _call_gemini_transcribe(gemini_model)
        except Exception as e:
            errors.append(str(e))

    if openai_api_key:
        try:
            return await _call_openai_transcribe(openai_model)
        except Exception as first_error:
            if openai_model != "whisper-1":
                try:
                    return await _call_openai_transcribe("whisper-1")
                except Exception as second_error:
                    errors.append(str(second_error))
            else:
                errors.append(str(first_error))

    if not gemini_api_key and not openai_api_key:
        raise HTTPException(400, "음성 전사 API 키가 설정되지 않았습니다 (GEMINI_API_KEY 또는 OPENAI_API_KEY 필요)")
    raise HTTPException(400, f"음성 전사 실패: {' | '.join(errors)[:600] or 'unknown error'}")


def _extract_transcript_from_file(filename: str, raw: bytes) -> str:
    name = (filename or "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    text = _decode_text(raw)
    if ext in {".srt", ".vtt"}:
        lines = []
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                continue
            if re.match(r"^\d+$", s):
                continue
            if "-->" in s:
                continue
            if s.upper().startswith("WEBVTT"):
                continue
            lines.append(s)
        return "\n".join(lines).strip()
    if ext == ".csv":
        out = []
        for row in csv.reader(text.splitlines()):
            cells = [c.strip() for c in row if c and c.strip()]
            if cells:
                out.append(" | ".join(cells))
        return "\n".join(out).strip()
    if ext == ".json":
        try:
            obj = json.loads(text)
            parts = []
            stack = [obj]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    for v in cur.values():
                        stack.append(v)
                elif isinstance(cur, list):
                    for v in cur:
                        stack.append(v)
                elif isinstance(cur, str):
                    s = cur.strip()
                    if s:
                        parts.append(s)
            return "\n".join(parts).strip()
        except Exception:
            return text.strip()
    return text.strip()


async def _extract_transcript_from_link(url: str) -> str:
    if not re.match(r"^https?://", url or ""):
        raise HTTPException(400, "링크는 http/https 형식이어야 합니다")
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url)
    if resp.status_code >= 400:
        raise HTTPException(400, f"링크를 읽을 수 없습니다 ({resp.status_code})")
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]
    text = "\n".join(lines).strip()
    if len(text) >= 120:
        return text

    # JS 기반 페이지(예: 일부 클로바노트 공유 링크)는 본문이 script에만 존재할 수 있으므로 2차 추출
    soup_all = BeautifulSoup(resp.text, "html.parser")
    script_text = "\n".join((s.get_text(" ", strip=False) or "") for s in soup_all.find_all("script"))
    if script_text:
        try:
            decoded = bytes(script_text, "utf-8").decode("unicode_escape", errors="ignore")
        except Exception:
            decoded = script_text
        raw_lines = [ln.strip() for ln in decoded.splitlines() if ln.strip()]
        candidates = []
        seen = set()
        deny = (
            "static/chunks", "webpack", "__next_f", "sourceMappingURL", "module.exports",
            "/v2/w/:workspaceId", "function(", "=>", "className", "backgroundColor",
        )
        for ln in raw_lines:
            if len(ln) < 20:
                continue
            if any(tok in ln for tok in deny):
                continue
            if re.search(r"[가-힣A-Za-z]{4,}", ln):
                key = ln[:180]
                if key not in seen:
                    seen.add(key)
                    candidates.append(ln)
            if len(candidates) >= 1000:
                break
        extracted = "\n".join(candidates).strip()
        if len(extracted) >= 120:
            code_tokens = (
                "props", "className", "children", "workspaceId", "useCallback", "function",
                "const ", "=>", "/v2/", "_next/static", "chunk", "module", "jsx",
            )
            lines = [ln for ln in extracted.splitlines() if ln.strip()]
            code_like = 0
            for ln in lines:
                low = ln.lower()
                if any(tok in low for tok in code_tokens):
                    code_like += 1
                    continue
                if re.search(r"[{}<>;=]{2,}", ln):
                    code_like += 1
            ratio = (code_like / len(lines)) if lines else 1.0
            if ratio < 0.35:
                return extracted

    host = ""
    try:
        host = httpx.URL(url).host or ""
    except Exception:
        host = ""
    if "clovanote.naver.com" in host:
        raise HTTPException(
            400,
            "클로바노트 링크에서 본문 텍스트를 읽지 못했습니다. 공유 권한을 확인하거나, 클로바노트 텍스트 내보내기 파일(.txt/.srt/.vtt/.csv)을 업로드해 주세요.",
        )
    raise HTTPException(400, "링크에서 녹취 텍스트를 충분히 추출하지 못했습니다")


def _fallback_visit_transcript_analysis(company_name: str, transcript: str) -> str:
    lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
    sample = lines[:120]
    body = "\n".join(sample)
    return (
        f"1.회사 개요\n"
        f"- 회사명: {company_name or '미지정'}\n"
        f"- 녹취에서 확인된 핵심 배경/현황을 아래 원문 기반으로 검토 필요\n\n"
        f"2.사업 모델\n"
        f"- 제품/서비스, 매출 구조, 밸류체인 관련 발언을 중심으로 정리 필요\n\n"
        f"3.투자 포인트\n"
        f"- 성장동력, 실적 레버리지, 리스크 요인을 항목별로 점검 필요\n\n"
        f"4.Q&A\n"
        f"- 질의응답 핵심 포인트를 질문/답변 단위로 재구성 필요\n\n"
        f"[원문 발췌]\n{body}"
    )


def _split_plain_chunks(text: str, max_len: int = 3200) -> list[str]:
    text = (text or "").strip()
    if len(text) <= max_len:
        return [text] if text else []
    chunks = []
    cur = []
    cur_len = 0
    for para in text.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        add_len = len(p) + (2 if cur else 0)
        if cur and cur_len + add_len > max_len:
            chunks.append("\n\n".join(cur))
            cur = [p]
            cur_len = len(p)
        else:
            cur.append(p)
            cur_len += add_len
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def _build_visit_transcript_prompt(company_name: str, transcript: str) -> str:
    return (
        "다음은 기업 탐방 녹취록 원문입니다.\n"
        "요약을 최소화하고, 애널리스트 보고서처럼 상세하게 정리해 주세요.\n"
        "반드시 아래 형식과 번호를 그대로 사용하세요.\n"
        "1.회사 개요\n2.사업 모델\n3.투자 포인트\n4.Q&A\n\n"
        "작성 규칙:\n"
        "- 원문에 없는 사실은 단정하지 말고, 추정 시 '가능성'으로 표기\n"
        "- 숫자/가이던스/일정/고객사/CAPEX/리스크/경쟁사 언급은 최대한 보존\n"
        "- Q&A는 질문과 답변을 쌍으로 정리하고, 중요도를 표시\n"
        "- 불릿 위주로 구조화하되 내용은 충분히 상세히 작성\n\n"
        f"[회사명]\n{company_name or '미지정'}\n\n"
        f"[녹취록 원문]\n{transcript}"
    )


@app.post("/api/visit-transcript/analyze")
async def api_visit_transcript_analyze(
    company_name: str | None = Form(None),
    clova_url: str | None = Form(None),
    transcript_text: str | None = Form(None),
    send_to_telegram: bool = Form(True),
    transcript_file: UploadFile | None = File(None),
):
    source_texts = []
    source_tags = []

    if transcript_file is not None and (transcript_file.filename or "").strip():
        raw = await transcript_file.read()
        if not raw:
            raise HTTPException(400, "업로드 파일이 비어 있습니다")
        if len(raw) > 200 * 1024 * 1024:
            raise HTTPException(413, "파일이 너무 큽니다 (최대 200MB)")
        if _is_audio_upload(transcript_file.filename or "", transcript_file.content_type):
            text = await _transcribe_audio_file(
                transcript_file.filename or "",
                raw,
                transcript_file.content_type,
            )
        else:
            text = _extract_transcript_from_file(transcript_file.filename or "", raw)
        if not text:
            raise HTTPException(400, "파일에서 텍스트를 추출하지 못했습니다")
        source_texts.append(text)
        if _is_audio_upload(transcript_file.filename or "", transcript_file.content_type):
            source_tags.append(f"audio:{transcript_file.filename}")
        else:
            source_tags.append(f"file:{transcript_file.filename}")

    if (clova_url or "").strip():
        link_text = await _extract_transcript_from_link(clova_url.strip())
        source_texts.append(link_text)
        source_tags.append("link")

    if (transcript_text or "").strip():
        source_texts.append((transcript_text or "").strip())
        source_tags.append("text")

    if not source_texts:
        raise HTTPException(400, "클로바노트 링크 또는 녹취 파일을 하나 이상 입력하세요")

    transcript = "\n\n".join(source_texts).strip()
    if len(transcript) > 180000:
        transcript = transcript[:180000]

    if SUMMARIZE_ENABLED and _anthropic_client:
        try:
            resp = _anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=5000,
                messages=[{"role": "user", "content": _build_visit_transcript_prompt(company_name or "", transcript)}],
            )
            analysis = (resp.content[0].text or "").strip()
        except Exception:
            analysis = _fallback_visit_transcript_analysis(company_name or "", transcript)
    else:
        analysis = _fallback_visit_transcript_analysis(company_name or "", transcript)

    sent_count = 0
    if send_to_telegram:
        chunks = _split_plain_chunks(analysis, max_len=3000)
        total = len(chunks)
        for i, chunk in enumerate(chunks, start=1):
            header = f"탐방녹취 정리"
            if company_name:
                header += f" - {company_name}"
            part = f" ({i}/{total})" if total > 1 else ""
            msg = f"<b>{_escape_html_text(header + part)}</b>\n\n{_escape_html_text(chunk)}"
            await send_telegram(msg)
            sent_count += 1

    return {
        "status": "ok",
        "company_name": company_name or "",
        "analysis": analysis,
        "source": ", ".join(source_tags),
        "telegram_sent": sent_count,
    }

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


@app.post("/api/tourism/check-latest-availability")
async def api_tourism_check_latest_availability():
    """Check whether a newer monthly tourism dataset has been published and import it if available."""
    return await check_and_update_tourism_latest(max_probe_months=3)

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


def _to_iso_date_flexible(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    if re.match(r"^\d{8}$", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    m = re.match(r"^(\d{4})[./](\d{1,2})[./](\d{1,2})$", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def _parse_number_text(raw: str | None) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _extract_deposit_series_from_json(payload) -> list[dict]:
    date_keys = ("trading_date", "date", "dt", "base_date", "bsns_dt", "일자", "기준일")
    value_keys = ("deposit_fund", "amount", "value", "inv_deposit", "투자자예탁금", "예탁금")

    out = []
    stack = [payload]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            found_date = None
            found_val = None
            for k, v in cur.items():
                if found_date is None and str(k).lower() in date_keys:
                    found_date = _to_iso_date_flexible(str(v))
                if found_val is None and (str(k).lower() in value_keys or "예탁금" in str(k)):
                    found_val = _parse_number_text(str(v))
            if found_date and found_val is not None:
                out.append({"trading_date": found_date, "deposit_fund": found_val})
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for x in cur:
                if isinstance(x, (dict, list)):
                    stack.append(x)

    if not out:
        return []

    by_date = {}
    for r in out:
        by_date[r["trading_date"]] = float(r["deposit_fund"])
    return [{"trading_date": d, "deposit_fund": by_date[d]} for d in sorted(by_date.keys())]


def _extract_deposit_series_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.select("th,td")]
        if not cells:
            continue
        dt = None
        for c in cells:
            dt = _to_iso_date_flexible(c)
            if dt:
                break
        if not dt:
            continue
        nums = []
        for c in cells:
            v = _parse_number_text(c)
            if v is not None:
                nums.append(v)
        if not nums:
            continue
        # 투자자 예탁금 표는 일반적으로 양수 큰 수치(억원 단위)라서 가장 큰 수를 채택.
        val = max(nums)
        rows.append({"trading_date": dt, "deposit_fund": float(val)})

    if not rows:
        return []
    by_date = {}
    for r in rows:
        by_date[r["trading_date"]] = float(r["deposit_fund"])
    return [{"trading_date": d, "deposit_fund": by_date[d]} for d in sorted(by_date.keys())]


async def _fetch_deposit_fund_from_freesis(days: int = 400) -> tuple[list[dict], str]:
    base_url = "https://freesis.kofia.or.kr"
    service_id = "STATSCU0100000060"
    obj_nm = "STATSCU0100000060BO"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": f"{base_url}/stat/FreeSIS.do",
    }

    def _latest_daily_date(meta: dict) -> datetime.date:
        candidates = []
        for row in meta.get("dsListAppDt", []) or []:
            for key in ("TMPV1", "TMPV2", "TMPV3", "TMPV4", "TMPV5"):
                val = row.get(key)
                if isinstance(val, str) and re.fullmatch(r"\d{8}", val):
                    candidates.append(datetime.date(int(val[:4]), int(val[4:6]), int(val[6:8])))
        for row in meta.get("dsLatestDate", []) or []:
            if row.get("TMPV1") == "RD":
                val = row.get("TMPV2")
                if isinstance(val, str) and re.fullmatch(r"\d{8}", val):
                    candidates.append(datetime.date(int(val[:4]), int(val[4:6]), int(val[6:8])))
        return max(candidates) if candidates else datetime.date.today()

    def _parse_main_latest(html: str, end_date: datetime.date) -> tuple[str | None, float | None]:
        m = re.search(
            r"투자자예탁금</a></dt>\s*<dd class=\"etc\"><span class=\"dan\">[^<]+</span>\s*\|\s*<span class=\"date\">(\d{2}/\d{2})</span></dd>\s*<dd class=\"chart-num\">\s*<span class=\"num1\">([0-9,]+)</span>",
            html,
            re.S,
        )
        if not m:
            return None, None
        mmdd = m.group(1)
        value = _parse_number_text(m.group(2))
        if value is None:
            return None, None
        as_of = f"{end_date.year}-{mmdd[:2]}-{mmdd[3:5]}"
        return as_of, float(value)

    def _extract_masked_rows(text: str) -> list[dict]:
        out = []
        for dt_raw, val_raw in re.findall(r"\"TMPV1\":\"(\d{8})\",\"TMPV2\":([0-9#]+)", text):
            dt = _to_iso_date_flexible(dt_raw)
            m = re.match(r"(\d+)", val_raw)
            if not dt or not m:
                continue
            out.append({"trading_date": dt, "deposit_fund": float(m.group(1))})
        by_date = {}
        for row in out:
            by_date[row["trading_date"]] = row["deposit_fund"]
        return [{"trading_date": d, "deposit_fund": by_date[d]} for d in sorted(by_date.keys())]

    def _fetch_official_series() -> tuple[list[dict], str]:
        session = requests.Session()
        meta_resp = session.post(
            f"{base_url}/meta/getSrvData.do",
            headers=headers,
            data=json.dumps(
                {
                    "dmSearchData": {
                        "strSvrId": service_id,
                        "app_peron_yn": "Y",
                        "language_gb": "KOR",
                        "strGetCode": "Y",
                    }
                }
            ),
            timeout=20,
        )
        meta_resp.raise_for_status()
        end_date = _latest_daily_date(meta_resp.json())
        main_resp = session.get(f"{base_url}/stat/main.do", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        main_resp.raise_for_status()
        latest_iso, latest_exact = _parse_main_latest(main_resp.text, end_date)

        lookback_days = max(int(days or 400) * 2, 800)
        start_date = end_date - datetime.timedelta(days=lookback_days)
        data_resp = session.post(
            f"{base_url}/meta/getMetaDataList.do",
            headers=headers,
            data=json.dumps(
                {
                    "dmSearch": {
                        "OBJ_NM": obj_nm,
                        "tmpV1": "D",
                        "tmpV45": start_date.strftime("%Y%m%d"),
                        "tmpV46": end_date.strftime("%Y%m%d"),
                        "tmpV40": "06",
                        "tmpV41": "00",
                    }
                }
            ),
            timeout=20,
        )
        data_resp.raise_for_status()
        rows = _extract_masked_rows(data_resp.text)
        if not rows:
            return [], ""
        if latest_iso and latest_exact is not None:
            anchor = next((row for row in reversed(rows) if row["trading_date"] == latest_iso), rows[-1])
            anchor_value = float(anchor["deposit_fund"])
            if anchor_value > 0:
                scale = latest_exact / anchor_value
                for row in rows:
                    row["deposit_fund"] = round(float(row["deposit_fund"]) * scale, 0)
        return rows[-max(days, 1):], f"{base_url}/meta/getMetaDataList.do"

    try:
        rows, source_url = await asyncio.to_thread(_fetch_official_series)
        if len(rows) >= 20:
            return rows, source_url
    except Exception:
        pass

    # 레거시 HTML/JSON 파서도 남겨두되, 공식 JSON 경로 실패 시에만 폴백합니다.
    env_url = os.environ.get("FREESIS_DEPOSIT_API_URL", "").strip()
    candidates = [u for u in [env_url, f"{base_url}/statistics/investor-deposit-fund", f"{base_url}/main/main.do"] if u]
    legacy_headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=legacy_headers) as client:
        for url in candidates:
            try:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    continue
                ctype = (resp.headers.get("content-type") or "").lower()
                rows: list[dict] = []
                if "json" in ctype:
                    rows = _extract_deposit_series_from_json(resp.json())
                else:
                    text = resp.text or ""
                    rows = _extract_deposit_series_from_json(json.loads(text)) if text.strip().startswith(("{", "[")) else []
                    if not rows:
                        rows = _extract_deposit_series_from_html(text)
                if len(rows) >= 20:
                    return rows[-max(days, 1):], url
            except Exception:
                continue
    return [], ""


def _build_dummy_deposit_series(days: int = 400) -> list[dict]:
    # 약 50~65조원(=500,000~650,000억원) 수준의 완만한 일별 시계열 더미 데이터
    lookback = max(120, days)
    today = datetime.date.today()
    start = today - datetime.timedelta(days=lookback * 2)
    out = []
    value = 545000.0
    d = start
    seq = 0
    while d <= today:
        if d.weekday() < 5:
            drift = 15.0
            seasonal = 2200.0 * math.sin(seq / 17.0)
            wave = 1200.0 * math.sin(seq / 6.5)
            pulse = ((seq % 9) - 4) * 28.0
            value = max(420000.0, value + drift + (seasonal + wave) * 0.05 + pulse)
            out.append({"trading_date": d.isoformat(), "deposit_fund": round(value, 2)})
            seq += 1
        d += datetime.timedelta(days=1)
    return out[-lookback:]


def _pick_base_row(series: list[dict], target_date: datetime.date) -> dict | None:
    for row in reversed(series):
        try:
            d = datetime.date.fromisoformat(row["trading_date"])
        except Exception:
            continue
        if d <= target_date:
            return row
    return None


def _calc_change(curr: float, prev: float | None) -> dict | None:
    if prev is None:
        return None
    diff = curr - prev
    rate = (diff / prev * 100.0) if prev else None
    return {
        "diff": round(diff, 2),
        "diff_pct": round(rate, 3) if rate is not None else None,
    }


def _build_deposit_stats(series: list[dict]) -> dict:
    if not series:
        return {}
    ordered = sorted(series, key=lambda x: x["trading_date"])
    latest = ordered[-1]
    latest_date = datetime.date.fromisoformat(latest["trading_date"])
    latest_val = float(latest["deposit_fund"])

    prev_day = ordered[-2] if len(ordered) >= 2 else None
    month_base = _pick_base_row(ordered[:-1], latest_date - datetime.timedelta(days=30))
    year_base = _pick_base_row(ordered[:-1], latest_date - datetime.timedelta(days=365))

    return {
        "as_of_date": latest["trading_date"],
        "current": round(latest_val, 2),
        "change_day": _calc_change(latest_val, float(prev_day["deposit_fund"])) if prev_day else None,
        "change_1m": _calc_change(latest_val, float(month_base["deposit_fund"])) if month_base else None,
        "change_1y": _calc_change(latest_val, float(year_base["deposit_fund"])) if year_base else None,
        "base_day_date": prev_day["trading_date"] if prev_day else None,
        "base_1m_date": month_base["trading_date"] if month_base else None,
        "base_1y_date": year_base["trading_date"] if year_base else None,
    }


@app.get("/api/deposit-fund")
async def api_deposit_fund(days: int = 90, force_dummy: bool = False):
    """
    투자자 예탁금(일별) 조회.
    - 기본 90일 반환
    - 내부적으로 최소 400일 확보 시도(1년 비교 카드 계산용)
    - 실데이터 조회 실패 시 더미 데이터 폴백
    """
    req_days = max(20, min(int(days or 365), 2000))
    history_days = max(req_days, 400)

    source = "dummy"
    source_url = ""
    used_fallback = True
    rows: list[dict] = []

    if not force_dummy:
        rows, source_url = await _fetch_deposit_fund_from_freesis(days=history_days)
        if rows:
            source = "freesis"
            used_fallback = False

    if not rows:
        rows = _build_dummy_deposit_series(days=history_days)

    rows = sorted(rows, key=lambda x: x["trading_date"])
    trimmed = rows[-req_days:]
    stats = _build_deposit_stats(rows)

    return {
        "source": source,
        "source_url": source_url,
        "used_fallback": used_fallback,
        "unit": "억원",
        "days": req_days,
        "series": trimmed,
        "stats": stats,
    }


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


@app.get("/api/market/daily")
def api_market_daily(year: int, month: int):
    """월별 국내 시장 일일 데이터 (캘린더용)."""
    rows = get_kr_market_daily(year, month)
    for r in rows:
        try:
            r["key_factors"] = json.loads(r.get("key_factors") or "[]")
        except (json.JSONDecodeError, TypeError):
            r["key_factors"] = []
    return rows


@app.get("/api/market/daily/{trading_date}")
def api_market_daily_by_date(trading_date: str):
    """특정일 국내 시장 상세 데이터."""
    data = get_kr_market_daily_by_date(trading_date)
    if not data:
        raise HTTPException(404, "해당 날짜 데이터가 없습니다")
    try:
        data["key_factors"] = json.loads(data.get("key_factors") or "[]")
    except (json.JSONDecodeError, TypeError):
        data["key_factors"] = []
    return data


@app.post("/api/market/refresh-daily")
async def api_market_refresh_daily():
    """수동 새로고침: 국내 시장 일별 데이터 즉시 수집 + 최근 누락일 보완."""
    try:
        kospi_rows = await fetch_daily_index_prices("KOSPI", count=90)
        kosdaq_rows = await fetch_daily_index_prices("KOSDAQ", count=90)
        if not kospi_rows or not kosdaq_rows:
            raise RuntimeError("국내 지수 일별 데이터를 조회하지 못했습니다")

        kospi_map = {r["date"]: r for r in kospi_rows}
        kosdaq_map = {r["date"]: r for r in kosdaq_rows}
        common_dates = sorted(set(kospi_map.keys()) & set(kosdaq_map.keys()))
        if not common_dates:
            raise RuntimeError("KOSPI/KOSDAQ 공통 거래일 데이터가 없습니다")

        semi_rate = _latest_export_rate("semiconductor")
        total_rate = _latest_export_rate("total")
        sector_rank_by_date = await _fetch_kr_sector_rankings_by_date(count=90, top_n=2)

        upserted = 0
        inserted = 0
        for d in common_dates:
            k = kospi_map[d]
            q = kosdaq_map[d]
            summary, factors = _summarize_kr_market(k, q, semi_rate, total_rate)
            sector_row = sector_rank_by_date.get(d) or {}
            strong = sector_row.get("strong") or []
            weak = sector_row.get("weak") or []
            if strong:
                txt = ", ".join(f"{x['name']}({x['change_pct']:+.2f}%)" for x in strong[:2])
                factors.append(f"강세 섹터: {txt}")
            if weak:
                txt = ", ".join(f"{x['name']}({x['change_pct']:+.2f}%)" for x in weak[:2])
                factors.append(f"약세 섹터: {txt}")
            exists = get_kr_market_daily_by_date(_to_iso_date(d))
            upsert_kr_market_daily(
                trading_date=_to_iso_date(d),
                kospi_close=k.get("close", 0),
                kospi_change_pct=k.get("change_pct", 0),
                kosdaq_close=q.get("close", 0),
                kosdaq_change_pct=q.get("change_pct", 0),
                summary_text=summary,
                key_factors=json.dumps(factors, ensure_ascii=False),
            )
            upserted += 1
            if not exists:
                inserted += 1

        latest_date = _to_iso_date(common_dates[-1])
        return {
            "status": "refreshed",
            "trading_date": latest_date,
            "upserted_count": upserted,
            "backfilled_count": inserted,
        }
    except Exception as e:
        raise HTTPException(500, f"국내 시장 데이터 수집 실패: {str(e)}")

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


# --- Stablecoin Supply API ---

STABLECOIN_ASSET_IDS = {
    "USDC": "usdc-usd-coin",
    "USDT": "usdt-tether",
    "FDUSD": "fdusd-first-digital-usd",
}


def _parse_stablecoin_symbols(symbols: str | None):
    if not symbols:
        return ["USDC", "USDT", "FDUSD"]
    out = []
    for s in str(symbols).split(","):
        key = s.strip().upper()
        if key in STABLECOIN_ASSET_IDS and key not in out:
            out.append(key)
    return out or ["USDC", "USDT", "FDUSD"]


@app.get("/api/stablecoin/supply")
def api_stablecoin_supply(symbols: str = "USDC,USDT,FDUSD", days: int = 365):
    syms = _parse_stablecoin_symbols(symbols)
    return {
        "symbols": syms,
        "data": {s: get_stablecoin_supply_daily(s, days=days) for s in syms},
    }


@app.post("/api/stablecoin/refresh")
async def api_stablecoin_refresh(symbols: str = "USDC,USDT,FDUSD", days: int = 3650):
    syms = _parse_stablecoin_symbols(symbols)
    timeout_sec = 20
    result = {"status": "ok", "symbols": syms, "items": {}, "errors": {}}

    async def _refresh_one(sym: str):
        asset_id = STABLECOIN_ASSET_IDS[sym]
        rows = await asyncio.wait_for(
            fetch_stablecoin_supply_history(asset_id=asset_id, days=days),
            timeout=timeout_sec,
        )
        upserted = 0
        for r in rows:
            upsert_stablecoin_supply_daily(
                asset_symbol=sym,
                trading_date=r["trading_date"],
                supply_amount=r["supply_amount"],
                market_cap_usd=r["market_cap_usd"],
                price_usd=r["price_usd"],
            )
            upserted += 1
            if sym == "USDC":
                upsert_usdc_supply_daily(
                    trading_date=r["trading_date"],
                    supply_amount=r["supply_amount"],
                    market_cap_usd=r["market_cap_usd"],
                    price_usd=r["price_usd"],
                )
        return {
            "upserted": upserted,
            "from": rows[0]["trading_date"] if rows else None,
            "to": rows[-1]["trading_date"] if rows else None,
        }

    tasks = [asyncio.create_task(_refresh_one(sym)) for sym in syms]
    outputs = await asyncio.gather(*tasks, return_exceptions=True)

    success = 0
    for sym, out in zip(syms, outputs):
        if isinstance(out, Exception):
            result["errors"][sym] = str(out)
            result["items"][sym] = {"upserted": 0, "from": None, "to": None}
        else:
            success += 1
            result["items"][sym] = out

    if success == 0:
        raise HTTPException(500, "스테이블코인 유통량 데이터 수집 실패: 모든 심볼 요청 실패")
    if success < len(syms):
        result["status"] = "partial"
    return result


@app.get("/api/usdc/supply")
def api_usdc_supply(days: int = 365):
    rows = get_stablecoin_supply_daily("USDC", days=days)
    if rows:
        return rows
    return get_usdc_supply_daily(days=days)


@app.post("/api/usdc/refresh")
async def api_usdc_refresh(days: int = 3650):
    out = await api_stablecoin_refresh(symbols="USDC", days=days)
    item = (out.get("items") or {}).get("USDC", {})
    return {
        "status": "ok",
        "upserted": item.get("upserted", 0),
        "from": item.get("from"),
        "to": item.get("to"),
    }


async def scheduled_usdc_supply_check():
    """매일 오전 3시: 주요 스테이블코인 유통량 데이터 갱신."""
    try:
        result = await api_stablecoin_refresh(symbols="USDC,USDT,FDUSD", days=3650)
        items = result.get("items") or {}
        print(
            "[stablecoin] Updated "
            f"(USDC={items.get('USDC', {}).get('upserted', 0)}, "
            f"USDT={items.get('USDT', {}).get('upserted', 0)}, "
            f"FDUSD={items.get('FDUSD', {}).get('upserted', 0)})"
        )
    except Exception as e:
        print(f"[stablecoin] Error: {e}")


# --- Semiconductor Price API ---

async def _refresh_semiconductor_prices_internal():
    fetched = await fetch_semiconductor_contract_prices()
    trading_date = datetime.datetime.now().strftime("%Y-%m-%d")
    inserted = 0
    by_market = {}
    for market_type, payload in fetched.items():
        items = payload.get("items") or []
        src_updated = payload.get("source_updated_at") or ""
        src_url = payload.get("source_url") or ""
        for row in items:
            upsert_semiconductor_price_daily(
                market_type=market_type,
                trading_date=trading_date,
                product_name=row.get("product_name"),
                daily_high=row.get("daily_high"),
                daily_low=row.get("daily_low"),
                session_high=row.get("session_high"),
                session_low=row.get("session_low"),
                session_avg=row.get("session_avg"),
                session_change_pct=row.get("session_change_pct"),
                change_direction=row.get("change_direction"),
                source_updated_at=src_updated,
                source_url=src_url,
            )
            inserted += 1
        by_market[market_type] = {
            "count": len(items),
            "source_updated_at": src_updated,
            "source_url": src_url,
        }

    if inserted <= 0:
        raise RuntimeError("수집된 반도체 가격 데이터가 없습니다")

    return {
        "status": "ok",
        "trading_date": trading_date,
        "inserted": inserted,
        "markets": by_market,
    }


async def scheduled_semiconductor_prices_check():
    """매일 오전 3시: 반도체(DRAM/NAND) 가격 스냅샷 수집."""
    try:
        result = await _refresh_semiconductor_prices_internal()
        print(
            f"[semi_price] Updated {result.get('trading_date')} "
            f"(rows={result.get('inserted', 0)})"
        )
    except Exception as e:
        print(f"[semi_price] Error: {e}")


def _safe_float(value):
    raw = (str(value or "")).strip().replace(",", "")
    if raw == "":
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _safe_direction(value, pct):
    raw = (str(value or "")).strip().lower()
    if raw in {"up", "down", "flat"}:
        return raw
    num = _safe_float(pct)
    if num is None:
        return "flat"
    if num > 0:
        return "up"
    if num < 0:
        return "down"
    return "flat"


@app.get("/api/semiconductor-prices")
def api_semiconductor_prices(market: str = "ALL", days: int = 90, trading_date: str | None = None):
    mk = (market or "ALL").strip().upper()
    market_type = mk if mk in {"DRAM", "NAND"} else None
    rows = get_semiconductor_price_daily(market_type=market_type, days=days, trading_date=trading_date)
    latest_date = get_latest_semiconductor_price_date(market_type=market_type)
    return {
        "market": market_type or "ALL",
        "days": int(days),
        "latest_date": latest_date,
        "rows": rows,
    }


@app.post("/api/semiconductor-prices/refresh")
async def api_semiconductor_prices_refresh():
    try:
        return await _refresh_semiconductor_prices_internal()
    except Exception as e:
        raise HTTPException(500, f"반도체 가격 데이터 수집 실패: {str(e)}")


@app.post("/api/semiconductor-prices/import-csv")
async def api_semiconductor_prices_import_csv(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if not name.endswith(".csv"):
        raise HTTPException(400, "CSV 파일만 업로드할 수 있습니다")

    try:
        raw = await file.read()
        text = raw.decode("utf-8-sig")
    except Exception:
        raise HTTPException(400, "CSV 파일 인코딩을 읽을 수 없습니다 (UTF-8 권장)")

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise HTTPException(400, "CSV 헤더가 없습니다")

    lower_map = {str(h).strip().lower(): h for h in reader.fieldnames if str(h).strip()}

    aliases = {
        "trading_date": ["trading_date", "date", "일자", "날짜"],
        "market_type": ["market_type", "market", "구분"],
        "product_name": ["product_name", "product", "품목", "제품명"],
        "session_avg": ["session_avg", "price", "avg_price", "average_price", "평균가", "가격"],
        "session_change_pct": ["session_change_pct", "change_pct", "change", "등락률", "변동률"],
        "daily_high": ["daily_high", "high", "고가"],
        "daily_low": ["daily_low", "low", "저가"],
        "session_high": ["session_high"],
        "session_low": ["session_low"],
        "change_direction": ["change_direction", "direction", "방향"],
        "source_updated_at": ["source_updated_at", "updated_at", "수집시각"],
        "source_url": ["source_url", "url", "링크"],
    }

    def find_col(key: str):
        for cand in aliases.get(key, [key]):
            h = lower_map.get(str(cand).strip().lower())
            if h:
                return h
        return None

    col = {k: find_col(k) for k in aliases.keys()}

    required = ["trading_date", "market_type", "product_name"]
    missing = [k for k in required if not col.get(k)]
    if missing:
        raise HTTPException(400, f"필수 컬럼 누락: {', '.join(missing)}")

    imported = 0
    skipped = 0
    errors = []

    for idx, row in enumerate(reader, start=2):
        try:
            trading_date = (row.get(col["trading_date"]) or "").strip()
            market_type = (row.get(col["market_type"]) or "").strip().upper()
            product_name = (row.get(col["product_name"]) or "").strip()

            if not re.match(r"^\d{4}-\d{2}-\d{2}$", trading_date):
                skipped += 1
                errors.append(f"{idx}행: trading_date 형식 오류(YYYY-MM-DD)")
                continue
            if market_type not in {"DRAM", "NAND"}:
                skipped += 1
                errors.append(f"{idx}행: market_type은 DRAM/NAND만 허용")
                continue
            if not product_name:
                skipped += 1
                errors.append(f"{idx}행: product_name 비어있음")
                continue

            def getv(key):
                h = col.get(key)
                return row.get(h) if h else None

            change_pct = _safe_float(getv("session_change_pct"))
            upsert_semiconductor_price_daily(
                market_type=market_type,
                trading_date=trading_date,
                product_name=product_name,
                daily_high=_safe_float(getv("daily_high")),
                daily_low=_safe_float(getv("daily_low")),
                session_high=_safe_float(getv("session_high")),
                session_low=_safe_float(getv("session_low")),
                session_avg=_safe_float(getv("session_avg")),
                session_change_pct=change_pct,
                change_direction=_safe_direction(getv("change_direction"), change_pct),
                source_updated_at=(getv("source_updated_at") or "").strip(),
                source_url=(getv("source_url") or "").strip(),
            )
            imported += 1
        except Exception as e:
            skipped += 1
            errors.append(f"{idx}행: {e}")

    return {
        "status": "ok",
        "imported": imported,
        "skipped": skipped,
        "error_count": len(errors),
        "errors": errors[:30],
        "required_columns": ["trading_date", "market_type", "product_name"],
        "optional_columns": [
            "daily_high", "daily_low", "session_high", "session_low", "session_avg(price 별칭 지원)",
            "session_change_pct", "change_direction", "source_updated_at", "source_url",
        ],
    }


@app.get("/api/semiconductor-prices/template-csv")
def api_semiconductor_prices_template_csv():
    content = (
        "trading_date,market_type,product_name,daily_high,daily_low,session_high,session_low,session_avg,session_change_pct,change_direction,source_updated_at,source_url\n"
        "2025-03-19,DRAM,DDR4 8Gb (1Gx8) 3200,48.00,11.70,48.00,11.70,30.000,1.25,up,2025-03-19 14:40 (GMT+8),https://example.com/dram\n"
        "2025-03-19,NAND,SLC 2Gb 256MBx8,3.00,2.00,3.00,2.00,2.467,-0.50,down,2025-03-19 14:40 (GMT+8),https://example.com/nand\n"
    )
    headers = {"Content-Disposition": "attachment; filename=semiconductor_prices_template.csv"}
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)


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


class InsiderBuyCreate(BaseModel):
    trade_date: str
    company_name: str
    related_party: str
    stock_code: str = ""
    relation_type: str = ""
    change_shares: int = 0
    change_ratio: float = 0
    avg_price: float = 0
    amount_krw: float = 0
    source_title: str = ""
    source_url: str = ""
    note: str = ""


class QuarterlyPerfWatchCreate(BaseModel):
    stock_code: str
    stock_name: str


class QuarterlyPerfReasonUpdate(BaseModel):
    stock_code: str
    quarter_key: str
    reason_text: str


class OverhangLockupCreate(BaseModel):
    stock_code: str
    stock_name: str
    holder_name: str
    holder_type: str = ""
    lockup_end_date: str
    quantity: int
    source_note: str = ""


class OverhangExerciseCreate(BaseModel):
    stock_code: str
    stock_name: str
    exercise_date: str
    quantity: int
    note: str = ""


class OverhangDartSyncRequest(BaseModel):
    stock_code: str
    stock_name: str = ""


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


# --- US Market API ---

@app.get("/api/us-market/daily")
def api_us_market_daily(year: int, month: int):
    """월별 미국 시장 데이터 (캘린더용)."""
    rows = get_us_market_daily(year, month)
    for r in rows:
        try:
            r["key_factors"] = json.loads(r.get("key_factors") or "[]")
            r["sectors_strong"] = json.loads(r.get("sectors_strong") or "[]")
            r["sectors_weak"] = json.loads(r.get("sectors_weak") or "[]")
        except (json.JSONDecodeError, TypeError):
            pass
    return rows


@app.get("/api/us-market/daily/{trading_date}")
def api_us_market_daily_by_date(trading_date: str):
    """특정일 미국 시장 상세 데이터."""
    data = get_us_market_daily_by_date(trading_date)
    if not data:
        raise HTTPException(404, "해당 날짜 데이터가 없습니다")
    try:
        data["key_factors"] = json.loads(data.get("key_factors") or "[]")
        data["sectors_strong"] = json.loads(data.get("sectors_strong") or "[]")
        data["sectors_weak"] = json.loads(data.get("sectors_weak") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    return data


@app.post("/api/us-market/refresh")
async def api_us_market_refresh():
    """수동 새로고침: 미국 시장 데이터 즉시 수집 + AI 요약."""
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "ALPHA_VANTAGE_API_KEY가 서버에 설정되지 않았습니다")
    try:
        # Use series once and derive latest + backfill to minimize API calls.
        spy_rows = await fetch_daily_index_series("SPY", api_key, limit=15)
        await asyncio.sleep(1.1)
        qqq_rows = await fetch_daily_index_series("QQQ", api_key, limit=15)
        if not spy_rows or not qqq_rows:
            raise RuntimeError("미국 지수 데이터를 조회하지 못했습니다")
        sp500 = spy_rows[0]
        nasdaq = qqq_rows[0]

        await asyncio.sleep(1.1)
        sector_warning = ""
        try:
            sectors = await fetch_sector_performance(api_key)
        except Exception as se:
            sectors = {}
            if _is_alpha_limit_error(se):
                sector_warning = "섹터 데이터는 API 한도로 인해 이번 새로고침에서 제외되었습니다."
            else:
                sector_warning = f"섹터 데이터 조회 실패: {str(se)}"

        result = _summarize_us_market(sp500, nasdaq, sectors)

        trading_date = sp500["date"]
        upsert_us_market_daily(
            trading_date=trading_date,
            sp500_close=sp500["close"],
            sp500_change_pct=sp500["change_pct"],
            nasdaq_close=nasdaq["close"],
            nasdaq_change_pct=nasdaq["change_pct"],
            summary_text=result.get("summary", ""),
            key_factors=json.dumps(result.get("key_factors", []), ensure_ascii=False),
            sectors_strong=json.dumps(result.get("sectors_strong", []), ensure_ascii=False),
            sectors_weak=json.dumps(result.get("sectors_weak", []), ensure_ascii=False),
            earnings_text=result.get("earnings_text", ""),
        )
        backfilled_dates = await _backfill_us_market_missing_dates(
            api_key=api_key,
            lookback_trading_days=7,
            skip_date=trading_date,
            spy_rows=spy_rows,
            qqq_rows=qqq_rows,
        )
        out = {
            "status": "refreshed",
            "trading_date": trading_date,
            "backfilled_count": len(backfilled_dates),
            "backfilled_dates": backfilled_dates,
        }
        if sector_warning:
            out["warning"] = sector_warning
        return out
    except Exception as e:
        if _is_alpha_limit_error(e):
            raise HTTPException(
                429,
                "Alpha Vantage 무료 키 한도(일 25회)에 도달했습니다. 잠시 후(또는 다음 거래일) 다시 시도해 주세요.",
            )
        raise HTTPException(500, f"미국 시장 데이터 수집 실패: {str(e)}")


# --- Trading Trend API ---

@app.get("/api/trading-trend/items")
def api_trading_trend_items(days: int = 30, keyword: str = "", stock_code: str = ""):
    """최근 특수관계인 지분 매수 모니터링 데이터 조회."""
    days = max(1, min(days, 3650))
    rows = get_insider_buy_records(days=days, keyword=keyword.strip() or None, stock_code=stock_code.strip() or None)
    return rows


@app.post("/api/trading-trend/items")
def api_trading_trend_add_item(req: InsiderBuyCreate):
    """특수관계인 지분 매수 기록 수동 등록."""
    if not req.trade_date or len(req.trade_date) != 10:
        raise HTTPException(400, "trade_date는 YYYY-MM-DD 형식이어야 합니다")
    if not req.company_name.strip():
        raise HTTPException(400, "company_name은 필수입니다")
    if not req.related_party.strip():
        raise HTTPException(400, "related_party는 필수입니다")

    row_id = add_insider_buy_record(
        trade_date=req.trade_date.strip(),
        company_name=req.company_name.strip(),
        stock_code=req.stock_code.strip(),
        related_party=req.related_party.strip(),
        relation_type=req.relation_type.strip(),
        change_shares=req.change_shares,
        change_ratio=req.change_ratio,
        avg_price=req.avg_price,
        amount_krw=req.amount_krw,
        source_title=req.source_title.strip(),
        source_url=req.source_url.strip(),
        note=req.note.strip(),
    )
    return {"id": row_id}


@app.delete("/api/trading-trend/items/{record_id}")
def api_trading_trend_delete_item(record_id: int):
    delete_insider_buy_record(record_id)
    return {"ok": True}


@app.post("/api/trading-trend/refresh")
async def api_trading_trend_refresh(days: int = 14):
    """DART 공시 기반 자동 동기화."""
    days = max(1, min(days, 90))
    try:
        return await sync_trading_trend_from_dart(days=days)
    except Exception as e:
        print(f"[trading_trend] refresh failed: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(500, f"자동 동기화 실패: {str(e)}")


# --- Quarterly Performance API ---

@app.get("/api/quarterly-performance/watchlist")
def api_quarterly_perf_watchlist():
    return get_quarterly_perf_watchlist()


@app.post("/api/quarterly-performance/watchlist")
def api_quarterly_perf_add_watch(req: QuarterlyPerfWatchCreate):
    code = (req.stock_code or "").strip().zfill(6)
    name = (req.stock_name or "").strip()
    if not code.isdigit():
        raise HTTPException(400, "stock_code는 숫자 6자리여야 합니다")
    if not name:
        raise HTTPException(400, "stock_name은 필수입니다")
    add_quarterly_perf_watch(code, name)
    return {"ok": True}


@app.delete("/api/quarterly-performance/watchlist/{stock_code}")
def api_quarterly_perf_delete_watch(stock_code: str):
    delete_quarterly_perf_watch(stock_code.zfill(6))
    return {"ok": True}


@app.get("/api/quarterly-performance/quarters")
def api_quarterly_perf_quarters():
    return get_quarterly_perf_quarters()


@app.post("/api/quarterly-performance/refresh")
async def api_quarterly_perf_refresh(auto_reason: bool = True, start: int = 0, limit: int | None = None):
    if start < 0:
        raise HTTPException(400, "start는 0 이상이어야 합니다")
    if limit is not None and limit < 1:
        raise HTTPException(400, "limit는 1 이상이어야 합니다")
    try:
        return await sync_quarterly_perf_data(auto_reason=auto_reason, start=start, limit=limit)
    except Exception as e:
        raise HTTPException(500, f"분기실적 동기화 실패: {str(e)}")


@app.post("/api/quarterly-performance/refresh/async")
async def api_quarterly_perf_refresh_async(auto_reason: bool = False, start: int = 0, limit: int | None = None):
    if start < 0:
        raise HTTPException(400, "start는 0 이상이어야 합니다")
    if limit is not None and limit < 1:
        raise HTTPException(400, "limit는 1 이상이어야 합니다")
    if quarterly_refresh_job.get("running"):
        raise HTTPException(409, "이미 분기실적 동기화 작업이 실행 중입니다")
    t = threading.Thread(
        target=_run_quarterly_refresh_job,
        args=(auto_reason, start, limit),
        daemon=True,
    )
    t.start()
    return {"ok": True, "message": "분기실적 동기화 작업을 시작했습니다", "params": {"auto_reason": auto_reason, "start": start, "limit": limit}}


@app.get("/api/quarterly-performance/refresh/status")
def api_quarterly_perf_refresh_status():
    return quarterly_refresh_job


@app.get("/api/quarterly-performance/overview")
def api_quarterly_perf_overview(quarter_key: str, sort_by: str = "revenue"):
    if not re.match(r"^\d{4}Q[1-4]$", quarter_key or ""):
        raise HTTPException(400, "quarter_key는 YYYYQn 형식이어야 합니다")
    return _build_quarterly_perf_overview(quarter_key, sort_by)


@app.get("/api/quarterly-performance/stock-detail")
def api_quarterly_perf_stock_detail(quarter_key: str, stock_code: str):
    if not re.match(r"^\d{4}Q[1-4]$", quarter_key or ""):
        raise HTTPException(400, "quarter_key는 YYYYQn 형식이어야 합니다")
    code = (stock_code or "").strip().zfill(6)
    if not re.match(r"^\d{6}$", code):
        raise HTTPException(400, "stock_code는 6자리 숫자여야 합니다")
    row = _build_quarterly_perf_stock_detail(quarter_key, code)
    if not row:
        raise HTTPException(404, "해당 종목/분기 데이터가 없습니다")
    return row


@app.put("/api/quarterly-performance/reason")
def api_quarterly_perf_update_reason(req: QuarterlyPerfReasonUpdate):
    code = (req.stock_code or "").strip().zfill(6)
    qk = (req.quarter_key or "").strip()
    if not re.match(r"^\d{4}Q[1-4]$", qk):
        raise HTTPException(400, "quarter_key는 YYYYQn 형식이어야 합니다")
    upsert_quarterly_perf_reason(code, qk, (req.reason_text or "").strip(), auto_generated=False)
    return {"ok": True}


# --- Stock Monitor API ---

@app.get("/api/stock-monitor/watchlist")
def api_stock_monitor_watchlist():
    return get_quarterly_perf_watchlist()


@app.get("/api/stock-monitor/search")
async def api_stock_monitor_search(name: str):
    q = (name or "").strip()
    if len(q) < 1:
        return []
    results = await search_stock_by_name(q)
    return results[:20]


async def _refresh_stock_monitor_range(start: int = 0, limit: int = 200):
    watch = get_quarterly_perf_watchlist()
    target = watch[start:start + limit]
    upserted = 0
    failed = 0
    for w in target:
        code = (w.get("stock_code") or "").zfill(6)
        name = (w.get("stock_name") or code).strip()
        try:
            detail = await _build_stock_monitor_detail(code)
            if not detail:
                failed += 1
                continue
            ret = detail["returns"]
            upsert_stock_monitor_return(
                stock_code=code,
                stock_name=name,
                as_of_date=detail["as_of_date"],
                latest_close=detail["latest_close"],
                ret_5y=ret.get("5y"),
                ret_3y=ret.get("3y"),
                ret_1y=ret.get("1y"),
                ret_6m=ret.get("6m"),
                ret_1m=ret.get("1m"),
                ret_1w=ret.get("1w"),
            )
            upserted += 1
        except Exception:
            failed += 1
    return {
        "watch_count": len(watch),
        "processed_count": len(target),
        "upserted": upserted,
        "failed": failed,
        "start": start,
        "limit": limit,
    }


@app.post("/api/stock-monitor/refresh")
async def api_stock_monitor_refresh(start: int = 0, limit: int = 200):
    if start < 0:
        raise HTTPException(400, "start는 0 이상이어야 합니다")
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit는 1~1000 범위여야 합니다")
    return await _refresh_stock_monitor_range(start=start, limit=limit)


@app.get("/api/stock-monitor/overview")
def api_stock_monitor_overview(sort_by: str = "1w", order: str = "desc"):
    rows = get_stock_monitor_returns()
    sort_map = {
        "5y": "ret_5y",
        "3y": "ret_3y",
        "1y": "ret_1y",
        "6m": "ret_6m",
        "1m": "ret_1m",
        "1w": "ret_1w",
    }
    key = sort_map.get(sort_by, "ret_1w")
    reverse = (order or "desc").lower() != "asc"
    present = [r for r in rows if r.get(key) is not None]
    missing = [r for r in rows if r.get(key) is None]
    present.sort(key=lambda x: x.get(key), reverse=reverse)
    return present + missing


@app.get("/api/stock-monitor/detail")
async def api_stock_monitor_detail(stock_code: str):
    code = (stock_code or "").strip().zfill(6)
    if not re.match(r"^\d{6}$", code):
        raise HTTPException(400, "stock_code는 6자리 숫자여야 합니다")
    watch = {w["stock_code"]: w for w in get_quarterly_perf_watchlist()}
    name = (watch.get(code) or {}).get("stock_name", code)
    try:
        detail = await _build_stock_monitor_detail(code)
    except Exception as e:
        raise HTTPException(500, f"주가 데이터 조회 실패: {str(e)}")
    if not detail:
        raise HTTPException(404, "해당 종목 주가 데이터가 없습니다")
    detail["stock_name"] = name
    return detail


# --- Overhang Monitor API ---

DART_BASE_URL = "https://opendart.fss.or.kr/api"
DART_TIMEOUT = 30
OVERHANG_REPORT_HINTS = (
    "증권신고서",
    "투자설명서",
    "증권발행실적보고서",
    "신규상장",
    "코스닥시장 상장",
    "유통가능",
    "의무보유",
    "보호예수",
)
LOCKUP_TEXT_HINTS = (
    "의무보유",
    "보호예수",
    "매각제한",
    "락업",
    "유통가능",
    "확약",
)
SELL_TEXT_HINTS = ("매도", "처분", "감소", "해지", "종결")
OVERHANG_EXERCISE_HINTS = ("의무보유", "보호예수", "락업", "확약", "유통가능")
HOLDER_TEXT_HINTS = ("기관", "주주", "투자", "벤처", "캐피탈", "증권", "운용", "보험", "은행", "연기금", "최대주주", "특수관계")
HOLDER_BAD_HINTS = ("위험", "인한", "합병", "재무", "매출", "영업", "당기", "손익", "증감", "비율", "상장일로부터")
TABLE_SKIP_HINTS = ("금융감독원", "공고", "홈페이지", "전자공시", "청약", "배정", "귀하")
LARGE_HOLDING_REPORT_HINTS = (
    "주식등의 대량보유 상황보고서",
    "주식등의대량보유상황보고서",
    "대량보유 상황보고서",
    "대량보유상황보고서",
)
KIS_DEFAULT_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_TOKEN_CACHE = {"token": "", "expires_at": datetime.datetime(1970, 1, 1)}


def _normalize_report_class(report_nm: str) -> str:
    nm = _clean_text(report_nm)
    nm = re.sub(r"^\[[^\]]+\]\s*", "", nm)
    if "투자설명서" in nm:
        return "투자설명서"
    if "증권신고서" in nm:
        return "증권신고서"
    if "증권발행실적보고서" in nm:
        return "증권발행실적보고서"
    return nm[:20]


def _is_large_holding_report_name(report_nm: str) -> bool:
    nm = _clean_text(report_nm).replace(" ", "")
    return any(h.replace(" ", "") in nm for h in LARGE_HOLDING_REPORT_HINTS)


def _normalize_stock_code_any(stock_code: str) -> str:
    s = (stock_code or "").strip().upper()
    if len(s) < 6 and s.isdigit():
        s = s.zfill(6)
    return s


def _is_valid_stock_code_any(stock_code: str) -> bool:
    return bool(re.match(r"^[0-9A-Z]{6}$", _normalize_stock_code_any(stock_code)))


def _safe_int(v) -> int:
    s = str(v or "").strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def _get_kis_config() -> dict:
    app_key = (os.environ.get("KIS_APP_KEY") or os.environ.get("KIS_APPKEY") or "").strip()
    app_secret = (os.environ.get("KIS_APP_SECRET") or os.environ.get("KIS_APPSECRET") or "").strip()
    base_url = (os.environ.get("KIS_BASE_URL") or KIS_DEFAULT_BASE_URL).strip().rstrip("/")
    return {
        "app_key": app_key,
        "app_secret": app_secret,
        "base_url": base_url or KIS_DEFAULT_BASE_URL,
    }


async def _kis_issue_token(app_key: str, app_secret: str, base_url: str) -> str:
    now = datetime.datetime.now()
    token = str(KIS_TOKEN_CACHE.get("token") or "")
    exp = KIS_TOKEN_CACHE.get("expires_at")
    if token and isinstance(exp, datetime.datetime) and exp > (now + datetime.timedelta(minutes=3)):
        return token

    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret,
    }
    headers = {
        "content-type": "application/json; charset=UTF-8",
        "accept": "text/plain",
    }
    def _post_token():
        return requests.post(
            f"{base_url}/oauth2/tokenP",
            data=json.dumps(payload),
            headers=headers,
            timeout=20,
        )

    resp = await asyncio.to_thread(_post_token)
    resp.raise_for_status()
    data = resp.json()
    access_token = (data.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError(f"KIS 토큰 발급 실패: {data}")
    KIS_TOKEN_CACHE["token"] = access_token
    KIS_TOKEN_CACHE["expires_at"] = now + datetime.timedelta(hours=23)
    return access_token


def _parse_yyyymmdd(s: str) -> datetime.date | None:
    t = str(s or "").strip()
    if not re.match(r"^\d{8}$", t):
        return None
    try:
        return datetime.date(int(t[0:4]), int(t[4:6]), int(t[6:8]))
    except Exception:
        return None


async def _fetch_stock_listing_date_from_price(stock_code: str) -> datetime.date | None:
    code = _normalize_stock_code_any(stock_code)
    if not re.match(r"^[0-9A-Z]{6}$", code):
        return None
    try:
        rows = await fetch_daily_stock_prices(code, count=260)
    except Exception:
        return None
    dates = []
    for r in rows or []:
        d = _parse_yyyymmdd(r.get("date"))
        if d:
            dates.append(d)
    if not dates:
        return None
    return min(dates)


async def _fetch_stock_latest_trade_date_from_price(stock_code: str) -> datetime.date | None:
    code = _normalize_stock_code_any(stock_code)
    if not re.match(r"^[0-9A-Z]{6}$", code):
        return None
    try:
        rows = await fetch_daily_stock_prices(code, count=15)
    except Exception:
        return None
    dates = []
    for r in rows or []:
        d = _parse_yyyymmdd(r.get("date"))
        if d:
            dates.append(d)
    if not dates:
        return None
    today = datetime.date.today()
    historical = [d for d in dates if d < today]
    if historical:
        return max(historical)
    return max(dates)


async def _fetch_kis_institution_cum_net_sell_qty(stock_code: str, since_date: datetime.date) -> int:
    series = await _fetch_kis_institution_daily_series(stock_code, since_date)
    return sum(max(0, -int(row.get("orgn_ntby_qty") or 0)) for row in series)


async def _fetch_kis_institution_daily_series(
    stock_code: str,
    since_date: datetime.date,
    end_date: datetime.date | None = None,
    max_pages: int = 8,
) -> list[dict]:
    try:
        conf = _get_kis_config()
        app_key = conf["app_key"]
        app_secret = conf["app_secret"]
        base_url = conf["base_url"]
        if (not app_key) or (not app_secret):
            return 0

        token = await _kis_issue_token(app_key, app_secret, base_url)
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHPTJ04160001",
            "custtype": "P",
        }
        latest_trade_date = end_date or await _fetch_stock_latest_trade_date_from_price(stock_code)
        final_end_date = latest_trade_date or (datetime.date.today() - datetime.timedelta(days=1))
        query_date = final_end_date
        seen_dates = set()
        series = []

        for _ in range(max_pages):
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": _normalize_stock_code_any(stock_code),
                "FID_INPUT_DATE_1": query_date.strftime("%Y%m%d"),
                "FID_ORG_ADJ_PRC": "",
                "FID_ETC_CLS_CODE": "",
            }

            def _fetch_daily():
                return requests.get(
                    f"{base_url}/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily",
                    params=params,
                    headers=headers,
                    timeout=25,
                )

            resp = await asyncio.to_thread(_fetch_daily)
            resp.raise_for_status()
            payload = resp.json()
            out2 = payload.get("output2") or []
            if isinstance(out2, dict):
                out2 = [out2]
            if not out2:
                break

            page_rows = []
            for r in out2:
                d = _parse_yyyymmdd(r.get("stck_bsop_date"))
                if not d:
                    continue
                if d in seen_dates:
                    continue
                seen_dates.add(d)
                row = {
                    "date": d,
                    "orgn_ntby_qty": _safe_int(r.get("orgn_ntby_qty")),
                }
                page_rows.append(row)
            if not page_rows:
                break

            series.extend(page_rows)
            oldest = min(row["date"] for row in page_rows)
            if oldest <= since_date:
                break
            query_date = oldest - datetime.timedelta(days=1)

        filtered = [row for row in series if since_date <= row["date"] <= final_end_date]
        filtered.sort(key=lambda x: x["date"])
        return filtered
    except Exception:
        return []


def _normalize_ymd(raw: str) -> str:
    t = str(raw or "").strip()
    if re.match(r"^\d{8}$", t):
        return f"{t[0:4]}-{t[4:6]}-{t[6:8]}"
    m = re.search(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", t)
    if not m:
        return ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime.date(y, mo, d).isoformat()
    except Exception:
        return ""


def _add_months(base: datetime.date, months: int) -> datetime.date:
    y = base.year + (base.month - 1 + months) // 12
    m = (base.month - 1 + months) % 12 + 1
    last_day = 31
    while True:
        try:
            return datetime.date(y, m, min(base.day, last_day))
        except ValueError:
            last_day -= 1


def _decode_bytes_any(b: bytes) -> str:
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            return (b or b"").decode(enc)
        except Exception:
            continue
    return (b or b"").decode("utf-8", errors="ignore")


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _find_listing_date(lines: list[str], report_dt: datetime.date | None) -> datetime.date | None:
    listing_candidates = []
    for line in lines:
        if ("상장예정일" not in line) and ("신규상장일" not in line) and ("상장일" not in line):
            continue
        if "상장일로부터" in line:
            continue
        dt_s = _normalize_ymd(line)
        if not dt_s:
            continue
        try:
            listing_candidates.append(datetime.date.fromisoformat(dt_s))
        except Exception:
            continue
    if not listing_candidates:
        return None
    if report_dt:
        listing_candidates.sort(key=lambda d: abs((d - report_dt).days))
        return listing_candidates[0]
    return max(listing_candidates)


def _resolve_unlock_date(raw: str, listing_date: datetime.date | None) -> str:
    t = _clean_text(raw)
    abs_dt = _normalize_ymd(t)
    if abs_dt:
        return abs_dt
    if listing_date:
        m = re.search(r"(?P<num>\d{1,2})\s*(?P<unit>개월|년|일)", t)
        if m:
            num = _safe_int(m.group("num"))
            unit = (m.group("unit") or "").strip()
            if num > 0:
                if unit == "개월":
                    return _add_months(listing_date, num).isoformat()
                if unit == "년":
                    return _add_months(listing_date, num * 12).isoformat()
                return (listing_date + datetime.timedelta(days=num)).isoformat()
    return ""


def _extract_qty_from_text(raw: str) -> int:
    t = _clean_text(raw)
    if not t:
        return 0
    if "%" in t and "주" not in t:
        return 0
    if ("주" not in t) and not re.search(r"\d{1,3}(?:,\d{3})+", t):
        return 0
    m = re.search(r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{4,})(?:\s*주)?(?!\d)", t)
    if not m:
        return 0
    n = max(0, _safe_int(m.group(1)))
    if 1900 <= n <= 2100:
        return 0
    if n < 1000 and "주" not in t:
        return 0
    return n


def _series_to_increment_rows(series: dict[str, int], holder_name: str) -> list[dict]:
    if not series:
        return []
    dates = sorted(series.keys())
    vals = [int(series[d]) for d in dates]
    non_decreasing = sum(1 for i in range(1, len(vals)) if vals[i] >= vals[i - 1])
    looks_cumulative = len(vals) >= 3 and non_decreasing >= (len(vals) - 1)

    out = []
    prev = 0
    for d in dates:
        q = int(series[d])
        inc = max(0, q - prev) if looks_cumulative else q
        prev = max(prev, q)
        if inc <= 0:
            continue
        row = _build_lockup_row(holder_name, d, inc)
        if row:
            out.append(row)
    return out


def _build_lockup_row(holder_name: str, lockup_end_date: str, quantity: int) -> dict | None:
    holder = _clean_holder_name(holder_name)
    if (not holder) or any(b in holder for b in HOLDER_BAD_HINTS) or len(holder) > 40:
        holder = "기관투자자"
    if holder in {"주식", "주식수", "보통주식", "합계", "계"}:
        holder = "기관투자자"
    if not lockup_end_date or int(quantity or 0) <= 0:
        return None
    if int(quantity or 0) < 100000:
        return None
    return {
        "holder_name": holder,
        "holder_type": _classify_holder_type(holder),
        "lockup_end_date": lockup_end_date,
        "quantity": int(quantity),
    }


def _extract_dates(text: str) -> list[str]:
    dates = []
    seen = set()
    for m in re.finditer(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", text or ""):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dt = datetime.date(y, mo, d).isoformat()
        except Exception:
            continue
        if dt not in seen:
            seen.add(dt)
            dates.append(dt)
    return dates


def _extract_qtys(text: str) -> list[int]:
    out = []
    seen = set()
    for m in re.finditer(r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{4,})\s*주", text or ""):
        n = _safe_int(m.group(1))
        if n > 0 and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _clean_holder_name(raw: str) -> str:
    s = str(raw or "").strip()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"(20\d{2})[.\-/년\s]+\d{1,2}[.\-/월\s]+\d{1,2}", " ", s)
    s = re.sub(r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{4,})\s*주", " ", s)
    for tok in LOCKUP_TEXT_HINTS:
        s = s.replace(tok, " ")
    s = re.sub(r"[\|\[\]<>:;·•※]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_/,")
    if len(s) > 60:
        s = s[:60].strip()
    return s


def _normalize_holder_for_match(raw: str) -> str:
    s = _clean_holder_name(raw).lower()
    s = s.replace("주식회사", "")
    s = s.replace("(주)", "")
    s = s.replace("㈜", "")
    s = re.sub(r"[^0-9a-z가-힣]", "", s)
    return s


def _is_generic_holder_key(holder_key: str) -> bool:
    h = _normalize_holder_for_match(holder_key)
    if not h:
        return True
    generic_tokens = (
        "기관투자자",
        "미상기관",
        "유통가능주식시점별",
        "유통가능주식",
        "보호예수",
        "의무보유",
        "합계",
    )
    if any(tok in h for tok in generic_tokens):
        return True
    return len(h) <= 2


def _is_institution_like_holder(name: str) -> bool:
    n = _clean_text(name)
    return any(
        k in n
        for k in (
            "투자",
            "인베스트",
            "인베스트먼트",
            "벤처스",
            "파트너스",
            "캐피탈",
            "증권",
            "운용",
            "보험",
            "은행",
            "연기금",
            "자산",
            "fund",
            "partners",
            "capital",
            "investment",
            "ventures",
        )
    )


def _classify_holder_type(name: str) -> str:
    n = str(name or "")
    if any(k in n for k in ("벤처", "VC", "캐피탈", "창투", "투자조합", "사모")):
        return "재무적투자자"
    if any(k in n for k in ("최대주주", "대표", "임원", "특수관계", "창업")):
        return "내부자/특수관계인"
    if any(k in n for k in ("기관", "연기금", "운용", "보험", "은행", "증권")):
        return "기관투자자"
    return "기타"


def _extract_lockups_from_document(text: str, report_date: str = "") -> list[dict]:
    lines = []
    for ln in (text or "").split("\n"):
        t = re.sub(r"\s+", " ", ln).strip()
        if len(t) < 6:
            continue
        lines.append(t)

    report_dt = None
    try:
        if re.match(r"^\d{8}$", str(report_date or "")):
            report_dt = datetime.date(int(report_date[0:4]), int(report_date[4:6]), int(report_date[6:8]))
    except Exception:
        report_dt = None

    listing_date = _find_listing_date(lines, report_dt)

    candidates = []
    keyword_window = 0

    for idx, line in enumerate(lines):
        has_hint = any(h in line for h in LOCKUP_TEXT_HINTS)
        has_holder_hint = any(h in line for h in HOLDER_TEXT_HINTS)
        if has_hint:
            keyword_window = 10
        active = has_hint or (keyword_window > 0 and has_holder_hint)
        if keyword_window > 0:
            keyword_window -= 1
        if not active:
            continue

        # Relative lockup period rows (e.g. 상장일로부터 1개월 / 3개월)
        if listing_date:
            period_hits = re.finditer(
                r"(?P<prefix>.*?)(?P<period>(?:상장일로부터\s*)?(?P<num>\d{1,2})\s*(?P<unit>개월|년|일))(?:[^0-9]{0,24})(?P<qty>\d{1,3}(?:,\d{3})+|\d{4,})\s*주",
                line,
            )
            for m in period_hits:
                num = _safe_int(m.group("num"))
                unit = (m.group("unit") or "").strip()
                qty2 = _safe_int(m.group("qty"))
                if num <= 0 or qty2 <= 0:
                    continue
                if unit == "개월":
                    unlock_dt = _add_months(listing_date, num)
                elif unit == "년":
                    unlock_dt = _add_months(listing_date, num * 12)
                else:
                    unlock_dt = listing_date + datetime.timedelta(days=num)
                holder2 = _clean_holder_name(m.group("prefix") or "")
                if (not holder2) or any(b in holder2 for b in HOLDER_BAD_HINTS) or len(holder2) > 30:
                    holder2 = "기관투자자"
                if not any(h in holder2 for h in HOLDER_TEXT_HINTS):
                    holder2 = "기관투자자"
                row = _build_lockup_row(holder2, unlock_dt.isoformat(), int(qty2))
                if row:
                    candidates.append(row)

        dates = _extract_dates(line)
        qtys = _extract_qtys(line)
        if not dates or not qtys:
            continue

        holder_part = re.split(r"(20\d{2})[.\-/년\s]+\d{1,2}[.\-/월\s]+\d{1,2}", line, maxsplit=1)[0]
        holder = _clean_holder_name(holder_part)
        if not holder and idx > 0:
            holder = _clean_holder_name(lines[idx - 1])
        if not holder:
            holder = "미상 기관"
        if not any(h in holder for h in HOLDER_TEXT_HINTS):
            continue
        if any(b in holder for b in HOLDER_BAD_HINTS):
            continue
        if len(holder) > 30:
            continue

        qty = max(qtys)
        if qty <= 0:
            continue

        lockup_end = dates[0]
        if report_dt:
            try:
                unlock_dt = datetime.date.fromisoformat(lockup_end)
                if unlock_dt < (report_dt - datetime.timedelta(days=30)):
                    continue
            except Exception:
                pass

        row = _build_lockup_row(holder, lockup_end, int(qty))
        if row:
            candidates.append(row)

    dedup = {}
    for r in candidates:
        if report_dt:
            try:
                unlock_dt = datetime.date.fromisoformat(r.get("lockup_end_date", ""))
                if unlock_dt < (report_dt - datetime.timedelta(days=30)):
                    continue
            except Exception:
                continue
        key = (r["holder_name"], r["lockup_end_date"], int(r["quantity"]))
        if key not in dedup:
            dedup[key] = r
    return list(dedup.values())


def _extract_holder_from_window(lines: list[str]) -> str:
    cand = []
    for ln in lines:
        t = _clean_text(ln)
        if len(t) < 2:
            continue
        if any(k in t for k in ("합병상장일", "합병기일", "코스닥시장", "증권신고서", "제출일", "의무보유", "보호예수")):
            continue
        if re.search(r"(㈜|주식회사|투자조합|벤처|캐피탈|증권|파트너스|홀딩스|인베스트)", t):
            cand.append(t)
    if cand:
        return cand[0][:40]
    return "기관투자자"


def _extract_lockups_from_section_blocks(text: str, report_date: str = "") -> list[dict]:
    report_dt = None
    try:
        if re.match(r"^\d{8}$", str(report_date or "")):
            report_dt = datetime.date(int(report_date[0:4]), int(report_date[4:6]), int(report_date[6:8]))
    except Exception:
        report_dt = None

    lines = [_clean_text(ln) for ln in (text or "").split("\n") if _clean_text(ln)]
    if not lines:
        return []

    anchor_idx = [
        i for i, ln in enumerate(lines)
        if ("보호예수 현황" in ln) or ("의무보유 주식 내역" in ln)
    ]
    if not anchor_idx:
        return []

    out = []
    for aidx in anchor_idx:
        block = lines[aidx:min(len(lines), aidx + 140)]
        for j, ln in enumerate(block):
            qty = _extract_qty_from_text(ln)
            if qty <= 0:
                continue
            # Guard: skip known non-overhang-like tiny/ambiguous rows.
            if qty < 5000:
                continue
            if qty > 100_000_000:
                continue

            near = block[max(0, j - 4):min(len(block), j + 8)]
            near_join = " ".join(near)
            if not any(k in near_join for k in ("의무보유", "보호예수", "합병상장일", "합병기일", "주식 내역")):
                continue
            if any(k in near_join for k in ("전환사채 발행 내역", "예치", "신탁", "억원", "백만원", " 단위 : 원", "평가", "비용", "운영자금")):
                continue
            dates = _extract_dates(near_join)
            if not dates:
                continue

            # Prefer the latest explicit date around quantity as lockup-end.
            unlock = sorted(dates)[-1]
            try:
                unlock_dt = datetime.date.fromisoformat(unlock)
            except Exception:
                continue
            if report_dt and unlock_dt < (report_dt - datetime.timedelta(days=3650)):
                continue

            holder = _extract_holder_from_window(near)
            row = _build_lockup_row(holder, unlock, qty)
            if row:
                out.append(row)

    dedup = {}
    for r in out:
        key = (r["holder_name"], r["lockup_end_date"], int(r["quantity"]))
        if key not in dedup:
            dedup[key] = r
    return list(dedup.values())


def _extract_lockups_from_html_tables(raw_docs: list[str], report_date: str = "") -> list[dict]:
    report_dt = None
    try:
        if re.match(r"^\d{8}$", str(report_date or "")):
            report_dt = datetime.date(int(report_date[0:4]), int(report_date[4:6]), int(report_date[6:8]))
    except Exception:
        report_dt = None

    all_lines = []
    for raw in raw_docs:
        soup = BeautifulSoup(raw or "", "html.parser")
        txt = _clean_text(soup.get_text(" "))
        if txt:
            all_lines.append(txt)
    listing_date = _find_listing_date(all_lines, report_dt)

    out = []
    for raw in raw_docs:
        soup = BeautifulSoup(raw or "", "html.parser")
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            header_cells = rows[0].find_all(["th", "td"])
            headers = [_clean_text(c.get_text(" ")) for c in header_cells]
            header_text = " | ".join(headers)
            if not any(k in header_text for k in ("의무보유", "보호예수", "유통가능", "확약", "매각제한", "락업", "보유기간")):
                continue
            qty_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ("수량", "주식수", "(주)", "물량"))), -1)
            date_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ("해제", "유통", "보유기간", "기간", "확약"))), -1)
            holder_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ("기관", "투자자", "구분", "주주", "성명", "보유자"))), -1)

            for tr in rows[1:]:
                cells = [_clean_text(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                row_text = " | ".join(cells)
                if not any(h in row_text for h in LOCKUP_TEXT_HINTS) and not re.search(r"\d+\s*(개월|년|일)", row_text):
                    continue
                if any(k in row_text for k in TABLE_SKIP_HINTS):
                    continue

                qty = 0
                if 0 <= qty_idx < len(cells):
                    qty = _extract_qty_from_text(cells[qty_idx])
                if qty <= 0 and qty_idx < 0:
                    # Fallback only when quantity column is unknown.
                    for c in cells:
                        qty = max(qty, _extract_qty_from_text(c))
                if qty <= 0:
                    continue

                unlock = ""
                if 0 <= date_idx < len(cells):
                    unlock = _resolve_unlock_date(cells[date_idx], listing_date)
                if not unlock:
                    for c in cells:
                        unlock = _resolve_unlock_date(c, listing_date)
                        if unlock:
                            break
                if not unlock:
                    continue

                holder = ""
                if 0 <= holder_idx < len(cells):
                    holder = cells[holder_idx]
                if not holder:
                    holder = cells[0]
                if any(k in holder for k in TABLE_SKIP_HINTS):
                    holder = "기관투자자"

                row = _build_lockup_row(holder, unlock, qty)
                if row:
                    out.append(row)

    dedup = {}
    for r in out:
        if report_dt:
            try:
                unlock_dt = datetime.date.fromisoformat(r.get("lockup_end_date", ""))
                if unlock_dt < (report_dt - datetime.timedelta(days=30)):
                    continue
            except Exception:
                continue
        key = (r["holder_name"], r["lockup_end_date"], int(r["quantity"]))
        if key not in dedup:
            dedup[key] = r
    return list(dedup.values())


def _extract_rows_from_ipo_float_section_text(text: str, report_date: str = "") -> list[dict]:
    """
    Parse lines around "상장 후 시점별 유통가능주식 현황" section.
    This section is typically IPO overhang core data.
    """
    report_dt = None
    try:
        if re.match(r"^\d{8}$", str(report_date or "")):
            report_dt = datetime.date(int(report_date[0:4]), int(report_date[4:6]), int(report_date[6:8]))
    except Exception:
        report_dt = None

    lines = [_clean_text(ln) for ln in (text or "").split("\n") if _clean_text(ln)]
    if not lines:
        return []
    listing_date = _find_listing_date(lines, report_dt)

    anchors = [
        i for i, ln in enumerate(lines)
        if ("시점별 유통가능주식" in ln)
        or ("유통가능주식 현황" in ln and "상장" in ln)
        or ("상장 후 유통가능 및 매각제한 물량" in ln)
    ]
    if not anchors:
        return []

    out = []
    for aidx in anchors:
        block = lines[aidx:min(len(lines), aidx + 140)]
        current_unlock = ""
        date_series: dict[str, int] = {}
        for ln in block:
            if any(k in ln for k in ("유통가능시점", "시점별", "비율", "주석", "기준일")):
                continue

            # 1) detect unlock timing label
            unlock = _resolve_unlock_date(ln, listing_date)
            if unlock:
                current_unlock = unlock
                continue
            if ("상장당일" in ln or "상장일" in ln) and listing_date:
                current_unlock = listing_date.isoformat()
                continue

            # 2) quantity candidate
            qty = _extract_qty_from_text(ln)
            if qty <= 0:
                continue
            if qty > 300_000_000:
                continue
            if not current_unlock:
                continue

            date_series[current_unlock] = max(date_series.get(current_unlock, 0), int(qty))

        out.extend(_series_to_increment_rows(date_series, "유통가능주식(시점별)"))

        # Fallback parser for sentence-like flattened rows:
        # "9,742,226 ... 상장일로부터 12개월 타임폴리오 ... 상장일로부터 12개월 ..."
        if listing_date:
            block_text = " ".join(block)
            flat_pat = re.compile(
                r"(?P<qty>\d{1,3}(?:,\d{3})+)"
                r"(?:\s+\d{1,3}(?:,\d{3})+){0,2}"
                r"\s+(?:상장일로부터\s*)?(?P<num>\d{1,2})\s*(?P<unit>개월|년|일)"
                r"\s+(?P<holder>.*?)(?=\s+(?:상장일로부터\s*)?\d{1,2}\s*(?:개월|년|일)\s+|$)"
            )
            for m in flat_pat.finditer(block_text):
                qty = _safe_int(m.group("qty"))
                if qty <= 0 or qty > 300_000_000:
                    continue
                num = _safe_int(m.group("num"))
                unit = (m.group("unit") or "").strip()
                if num <= 0:
                    continue
                if unit == "개월":
                    unlock_dt = _add_months(listing_date, num)
                elif unit == "년":
                    unlock_dt = _add_months(listing_date, num * 12)
                else:
                    unlock_dt = listing_date + datetime.timedelta(days=num)
                holder = _clean_holder_name(m.group("holder") or "")
                row = _build_lockup_row(holder or "기관투자자", unlock_dt.isoformat(), qty)
                if row:
                    out.append(row)

    dedup = {}
    for r in out:
        key = (r["holder_name"], r["lockup_end_date"], int(r["quantity"]))
        if key not in dedup:
            dedup[key] = r
    return list(dedup.values())


def _extract_rows_from_ipo_float_section_tables(raw_docs: list[str], report_date: str = "") -> list[dict]:
    """
    Parse table rows that look like IPO float schedule table.
    """
    report_dt = None
    try:
        if re.match(r"^\d{8}$", str(report_date or "")):
            report_dt = datetime.date(int(report_date[0:4]), int(report_date[4:6]), int(report_date[6:8]))
    except Exception:
        report_dt = None

    all_lines = []
    for raw in raw_docs:
        soup = BeautifulSoup(raw or "", "html.parser")
        t = _clean_text(soup.get_text(" "))
        if t:
            all_lines.append(t)
    listing_date = _find_listing_date(all_lines, report_dt)

    out = []
    for raw in raw_docs:
        soup = BeautifulSoup(raw or "", "html.parser")
        for table in soup.find_all("table"):
            ttxt = _clean_text(table.get_text(" "))
            if not (("시점별 유통가능주식" in ttxt) or ("유통가능주식 현황" in ttxt and "상장" in ttxt)):
                continue
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            header = [_clean_text(c.get_text(" ")) for c in rows[0].find_all(["th", "td"])]
            qty_idx = next((i for i, h in enumerate(header) if any(k in h for k in ("유통가능주식수", "주식수", "수량"))), -1)
            date_idx = next((i for i, h in enumerate(header) if any(k in h for k in ("시점", "기간", "구분", "해제"))), -1)
            cum_idx = next((i for i, h in enumerate(header) if "누적" in h), -1)

            cumulative_mode = cum_idx >= 0 and qty_idx >= 0 and cum_idx == qty_idx
            date_series: dict[str, int] = {}
            for tr in rows[1:]:
                cells = [_clean_text(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                row_text = " | ".join(cells)
                unlock = ""
                if 0 <= date_idx < len(cells):
                    unlock = _resolve_unlock_date(cells[date_idx], listing_date)
                if not unlock:
                    unlock = _resolve_unlock_date(row_text, listing_date)
                if not unlock and listing_date and ("상장당일" in row_text or "상장일" in row_text):
                    unlock = listing_date.isoformat()
                if not unlock:
                    continue

                qty = 0
                if 0 <= qty_idx < len(cells):
                    qty = _extract_qty_from_text(cells[qty_idx])
                if qty <= 0 and qty_idx < 0:
                    for c in cells:
                        qty = max(qty, _extract_qty_from_text(c))
                if qty <= 0 or qty > 300_000_000:
                    continue

                date_series[unlock] = max(date_series.get(unlock, 0), int(qty))

            if cumulative_mode:
                out.extend(_series_to_increment_rows(date_series, "유통가능주식(시점별)"))
            else:
                out.extend(_series_to_increment_rows(date_series, "유통가능주식(시점별)"))

    dedup = {}
    for r in out:
        key = (r["holder_name"], r["lockup_end_date"], int(r["quantity"]))
        if key not in dedup:
            dedup[key] = r
    return list(dedup.values())


async def _fetch_disclosure_document_raw_docs(api_key: str, rcept_no: str) -> list[str]:
    params = {"crtfc_key": api_key, "rcept_no": str(rcept_no)}
    async with httpx.AsyncClient(timeout=DART_TIMEOUT) as client:
        resp = await client.get(f"{DART_BASE_URL}/document.xml", params=params)
        resp.raise_for_status()
        content = resp.content or b""

    docs = []
    if content.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                lower = name.lower()
                if not (lower.endswith(".xml") or lower.endswith(".xhtml") or lower.endswith(".html") or lower.endswith(".htm")):
                    continue
                raw = _decode_bytes_any(zf.read(name))
                if raw and len(raw.strip()) > 20:
                    docs.append(raw)
        return docs

    raw = _decode_bytes_any(content)
    if raw and len(raw.strip()) > 20:
        docs.append(raw)
    return docs


async def _fetch_overhang_candidate_reports(api_key: str, corp_code: str, max_pages: int = 6) -> list[dict]:
    end_de = datetime.date.today().strftime("%Y%m%d")
    bgn_de = (datetime.date.today() - datetime.timedelta(days=3650)).strftime("%Y%m%d")
    out = []

    async with httpx.AsyncClient(timeout=DART_TIMEOUT) as client:
        for page_no in range(1, max_pages + 1):
            params = {
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_count": "100",
                "page_no": str(page_no),
            }
            resp = await client.get(f"{DART_BASE_URL}/list.json", params=params)
            resp.raise_for_status()
            payload = resp.json()
            status = str(payload.get("status", ""))
            if status not in {"000", "013"}:
                raise RuntimeError(f"DART list 조회 실패({status}): {payload.get('message', '')}")
            rows = payload.get("list", []) or []
            if not rows:
                break
            for r in rows:
                nm = (r.get("report_nm") or "").strip()
                if any(h in nm for h in OVERHANG_REPORT_HINTS):
                    out.append({
                        "rcept_no": (r.get("rcept_no") or "").strip(),
                        "rcept_dt": (r.get("rcept_dt") or "").strip(),
                        "report_nm": nm,
                    })
            if len(rows) < 100:
                break

    uniq = {}
    for r in sorted(out, key=lambda x: x.get("rcept_dt", ""), reverse=True):
        key = r.get("rcept_no")
        if key and key not in uniq:
            uniq[key] = r
    rows = list(uniq.values())

    by_class = {}
    for r in sorted(rows, key=lambda x: x.get("rcept_dt", ""), reverse=True):
        cls = _normalize_report_class(r.get("report_nm", ""))
        if cls not in by_class:
            by_class[cls] = r
    if "투자설명서" in by_class:
        return [by_class["투자설명서"]]
    if "증권신고서" in by_class:
        return [by_class["증권신고서"]]
    if "증권발행실적보고서" in by_class:
        return [by_class["증권발행실적보고서"]]
    ordered = sorted(by_class.values(), key=lambda x: x.get("rcept_dt", ""), reverse=True)
    return ordered[:2]


async def _fetch_large_holding_rcept_map(api_key: str, corp_code: str, max_pages: int = 8) -> dict[str, str]:
    end_de = datetime.date.today().strftime("%Y%m%d")
    bgn_de = (datetime.date.today() - datetime.timedelta(days=3650)).strftime("%Y%m%d")
    out = {}

    async with httpx.AsyncClient(timeout=DART_TIMEOUT) as client:
        for page_no in range(1, max_pages + 1):
            params = {
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_count": "100",
                "page_no": str(page_no),
                "pblntf_ty": "D",
            }
            resp = await client.get(f"{DART_BASE_URL}/list.json", params=params)
            resp.raise_for_status()
            payload = resp.json()
            status = str(payload.get("status", ""))
            if status not in {"000", "013"}:
                break

            rows = payload.get("list", []) or []
            for r in rows:
                rcept_no = str(r.get("rcept_no", "")).strip()
                report_nm = (r.get("report_nm") or "").strip()
                if not re.match(r"^\d{14}$", rcept_no):
                    continue
                if not _is_large_holding_report_name(report_nm):
                    continue
                if rcept_no not in out:
                    out[rcept_no] = report_nm
            if len(rows) < 100:
                break
    return out


async def _fetch_overhang_lockup_candidates(api_key: str, corp_code: str) -> tuple[list[dict], list[dict]]:
    reports = await _fetch_overhang_candidate_reports(api_key, corp_code)
    lockups = []
    parsed_reports = []

    for rep in reports[:4]:
        rcept_no = rep.get("rcept_no", "")
        if not re.match(r"^\d{14}$", rcept_no):
            continue
        try:
            raw_docs = await _fetch_disclosure_document_raw_docs(api_key, rcept_no)
            text = await fetch_disclosure_document_text(api_key, rcept_no)
        except Exception:
            continue
        rows_from_table = _extract_lockups_from_html_tables(raw_docs, report_date=rep.get("rcept_dt", ""))
        rows_from_text = _extract_lockups_from_document(text, report_date=rep.get("rcept_dt", ""))
        rows_from_block = _extract_lockups_from_section_blocks(text, report_date=rep.get("rcept_dt", ""))
        rows_from_ipo_table = _extract_rows_from_ipo_float_section_tables(raw_docs, report_date=rep.get("rcept_dt", ""))
        rows_from_ipo_text = _extract_rows_from_ipo_float_section_text(text, report_date=rep.get("rcept_dt", ""))
        rows = rows_from_ipo_table + rows_from_ipo_text + rows_from_table + rows_from_text + rows_from_block
        dedup_rows = {}
        for r in rows:
            key = (
                (r.get("holder_name") or "").strip(),
                (r.get("lockup_end_date") or "").strip(),
                int(r.get("quantity") or 0),
            )
            if key not in dedup_rows:
                dedup_rows[key] = r
        rows = list(dedup_rows.values())
        if not rows:
            continue
        source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
        for r in rows:
            lockups.append({
                **r,
                "source_note": f"자동수집(DART): {rep.get('report_nm', '')} / {rep.get('rcept_dt', '')} / {source_url}",
            })
        parsed_reports.append({
            "rcept_no": rcept_no,
            "rcept_dt": rep.get("rcept_dt", ""),
            "report_nm": rep.get("report_nm", ""),
            "parsed_rows": len(rows),
            "table_rows": len(rows_from_table),
            "text_rows": len(rows_from_text),
            "block_rows": len(rows_from_block),
            "ipo_table_rows": len(rows_from_ipo_table),
            "ipo_text_rows": len(rows_from_ipo_text),
        })

    dedup = {}
    for r in lockups:
        key = (
            (r.get("holder_name") or "").strip(),
            (r.get("lockup_end_date") or "").strip(),
            int(r.get("quantity") or 0),
        )
        if key not in dedup:
            dedup[key] = r
    rows = list(dedup.values())

    # Conservative collapse: when holder is generic(기관투자자), keep max qty per unlock date.
    grouped_generic = {}
    kept = []
    for r in rows:
        holder = (r.get("holder_name") or "").strip()
        d = (r.get("lockup_end_date") or "").strip()
        q = int(r.get("quantity") or 0)
        if holder == "기관투자자" and d:
            old = grouped_generic.get(d)
            if (not old) or q > int(old.get("quantity") or 0):
                grouped_generic[d] = r
        else:
            kept.append(r)
    kept.extend(grouped_generic.values())
    kept.sort(key=lambda x: ((x.get("lockup_end_date") or ""), -(int(x.get("quantity") or 0))))
    return kept, parsed_reports


async def _fetch_overhang_exercise_candidates(api_key: str, corp_code: str, lockup_holders: list[str] | None = None) -> list[dict]:
    holding_reports = await _fetch_large_holding_rcept_map(api_key, corp_code)
    if not holding_reports:
        return []

    holder_keys = {
        _normalize_holder_for_match(h)
        for h in (lockup_holders or [])
        if _normalize_holder_for_match(h)
    }
    specific_holder_keys = {h for h in holder_keys if not _is_generic_holder_key(h)}

    params = {"crtfc_key": api_key, "corp_code": corp_code}
    async with httpx.AsyncClient(timeout=DART_TIMEOUT) as client:
        resp = await client.get(f"{DART_BASE_URL}/majorstock.json", params=params)
        resp.raise_for_status()
        payload = resp.json()

    status = str(payload.get("status", ""))
    if status not in {"000", "013"}:
        return []

    rows = payload.get("list", []) or []
    out = []
    for r in rows:
        rcept_no = str(r.get("rcept_no", "")).strip()
        if rcept_no not in holding_reports:
            continue
        delta = _safe_int(r.get("stkqy_irds"))
        if delta >= 0:
            continue
        ex_date = _normalize_ymd(r.get("rcept_dt"))
        if not ex_date:
            continue
        qty = abs(delta)
        if qty <= 0:
            continue
        reason = (r.get("report_resn") or "").strip()
        holder = (r.get("repror") or "").strip()
        holder_norm = _normalize_holder_for_match(holder)
        holder_match = False
        if specific_holder_keys:
            holder_match = any((k in holder_norm) or (holder_norm in k) for k in specific_holder_keys if holder_norm)
            if (not holder_match) and _is_institution_like_holder(holder):
                holder_match = True
        else:
            holder_match = _is_institution_like_holder(holder)

        reason_match = bool(reason and any(k in reason for k in OVERHANG_EXERCISE_HINTS))
        if reason and not any(k in reason for k in SELL_TEXT_HINTS) and not reason_match and not holder_match:
            continue
        if (not reason_match) and (not holder_match):
            continue

        source_url = ""
        if re.match(r"^\d{14}$", rcept_no):
            source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
        note = f"자동수집(DART 대량보유보고서 기반): 변동수량 음수(오버행 행사 후보) / 보고서:{holding_reports.get(rcept_no, '')}"
        if holder:
            note += f" / 보고자:{holder}"
        if reason:
            note += f" / 사유:{reason[:80]}"
        if source_url:
            note += f" / {source_url}"
        out.append({
            "exercise_date": ex_date,
            "quantity": qty,
            "note": note,
        })

    dedup = {}
    for r in out:
        key = (r.get("exercise_date"), int(r.get("quantity") or 0))
        if key not in dedup:
            dedup[key] = r
    return sorted(dedup.values(), key=lambda x: x.get("exercise_date", ""))


async def _sync_overhang_from_dart(stock_code: str, stock_name: str) -> dict:
    code = _normalize_stock_code_any(stock_code)
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(500, "DART_API_KEY not configured")

    corp_code = await get_corp_code_by_stock(api_key, code)
    if not corp_code:
        raise HTTPException(404, "해당 종목의 DART corp_code를 찾지 못했습니다")

    existing_lockups = get_overhang_lockups(code)
    lockup_candidates, parsed_reports = await _fetch_overhang_lockup_candidates(api_key, corp_code)
    lockup_holder_pool = [r.get("holder_name", "") for r in lockup_candidates] + [r.get("holder_name", "") for r in existing_lockups]
    exercise_candidates = await _fetch_overhang_exercise_candidates(api_key, corp_code, lockup_holders=lockup_holder_pool)

    existing_lockup_keys = {
        (
            (r.get("holder_name") or "").strip(),
            (r.get("lockup_end_date") or "").strip(),
            int(r.get("quantity") or 0),
        )
        for r in existing_lockups
    }
    existing_exercises = get_overhang_exercises(code)
    existing_exercise_keys = {
        (
            (r.get("exercise_date") or "").strip(),
            int(r.get("quantity") or 0),
        )
        for r in existing_exercises
    }

    inserted_lockups = 0
    skipped_lockups = 0
    stock_name_final = (stock_name or "").strip()
    if not stock_name_final:
        if existing_lockups:
            stock_name_final = existing_lockups[0].get("stock_name") or ""
        elif existing_exercises:
            stock_name_final = existing_exercises[0].get("stock_name") or ""

    for r in lockup_candidates:
        key = (
            (r.get("holder_name") or "").strip(),
            (r.get("lockup_end_date") or "").strip(),
            int(r.get("quantity") or 0),
        )
        if key in existing_lockup_keys:
            skipped_lockups += 1
            continue
        add_overhang_lockup(
            stock_code=code,
            stock_name=stock_name_final,
            holder_name=(r.get("holder_name") or "미상 기관").strip(),
            holder_type=(r.get("holder_type") or "").strip(),
            lockup_end_date=(r.get("lockup_end_date") or "").strip(),
            quantity=int(r.get("quantity") or 0),
            source_note=(r.get("source_note") or "").strip(),
        )
        existing_lockup_keys.add(key)
        inserted_lockups += 1

    inserted_exercises = 0
    skipped_exercises = 0
    for r in exercise_candidates:
        key = (
            (r.get("exercise_date") or "").strip(),
            int(r.get("quantity") or 0),
        )
        if key in existing_exercise_keys:
            skipped_exercises += 1
            continue
        add_overhang_exercise(
            stock_code=code,
            stock_name=stock_name_final,
            exercise_date=(r.get("exercise_date") or "").strip(),
            quantity=int(r.get("quantity") or 0),
            note=(r.get("note") or "").strip(),
        )
        existing_exercise_keys.add(key)
        inserted_exercises += 1

    return {
        "stock_code": code,
        "stock_name": stock_name_final,
        "corp_code": corp_code,
        "reports_parsed": parsed_reports,
        "lockup_candidates": len(lockup_candidates),
        "exercise_candidates": len(exercise_candidates),
        "inserted_lockups": inserted_lockups,
        "skipped_lockups": skipped_lockups,
        "inserted_exercises": inserted_exercises,
        "skipped_exercises": skipped_exercises,
    }


async def _build_overhang_status(stock_code: str):
    lockups = get_overhang_lockups(stock_code)
    exercises = get_overhang_exercises(stock_code)
    today = datetime.date.today().isoformat()

    for r in lockups:
        r["quantity"] = int(r.get("quantity") or 0)
    for r in exercises:
        r["quantity"] = int(r.get("quantity") or 0)

    lockups_sorted = sorted(lockups, key=lambda x: (x.get("lockup_end_date") or "", x.get("id") or 0))
    exercises_sorted = sorted(exercises, key=lambda x: (x.get("exercise_date") or "", x.get("id") or 0))

    total_lockup_qty = sum(max(0, int(r.get("quantity") or 0)) for r in lockups_sorted)
    exercised_to_date = sum(
        max(0, int(r.get("quantity") or 0))
        for r in exercises_sorted
        if (r.get("exercise_date") or "") <= today
    )
    unlocked_to_date = sum(
        max(0, int(r.get("quantity") or 0))
        for r in lockups_sorted
        if (r.get("lockup_end_date") or "") <= today
    )

    remaining_total = max(0, total_lockup_qty - exercised_to_date)
    currently_unlocked_remaining = max(0, unlocked_to_date - exercised_to_date)

    listing_date = await _fetch_stock_listing_date_from_price(stock_code)
    listing_age_days = None
    is_recent_ipo_under_6m = False
    kis_inst_cum_net_sell_qty = 0
    kis_assumed_exercise_qty = 0
    if listing_date:
        listing_age_days = (datetime.date.today() - listing_date).days
        is_recent_ipo_under_6m = listing_age_days < 183
    kis_milestone_rows = []
    if is_recent_ipo_under_6m:
        try:
            latest_trade_date = await _fetch_stock_latest_trade_date_from_price(stock_code)
            kis_series = await _fetch_kis_institution_daily_series(stock_code, listing_date, latest_trade_date)
            kis_inst_cum_net_sell_qty = sum(max(0, -int(row.get("orgn_ntby_qty") or 0)) for row in kis_series)
        except Exception:
            kis_series = []
            kis_inst_cum_net_sell_qty = 0
        kis_assumed_exercise_qty = min(remaining_total, max(0, int(kis_inst_cum_net_sell_qty)))
        unlock_dates = sorted(
            {
                datetime.date.fromisoformat(r.get("lockup_end_date"))
                for r in lockups_sorted
                if (r.get("lockup_end_date") or "")
            }
        )
        cutoff_rows = [
            (d.isoformat(), d)
            for d in unlock_dates
            if d <= datetime.date.today()
        ]
        current_cutoff = latest_trade_date or datetime.date.today()
        cutoff_rows.append(("현재", current_cutoff))

        seen_cutoffs = set()
        for label, cutoff in cutoff_rows:
            if cutoff in seen_cutoffs:
                continue
            seen_cutoffs.add(cutoff)
            unlocked_qty_at_cutoff = sum(
                max(0, int(r.get("quantity") or 0))
                for r in lockups_sorted
                if (r.get("lockup_end_date") or "") and (r.get("lockup_end_date") <= cutoff.isoformat())
            )
            kis_sell_at_cutoff = sum(
                max(0, -int(row.get("orgn_ntby_qty") or 0))
                for row in kis_series
                if row.get("date") and row["date"] <= cutoff
            )
            coverage_pct = (kis_sell_at_cutoff / unlocked_qty_at_cutoff * 100.0) if unlocked_qty_at_cutoff > 0 else 0.0
            kis_milestone_rows.append({
                "label": label,
                "cutoff_date": cutoff.isoformat(),
                "unlocked_overhang_qty": int(unlocked_qty_at_cutoff),
                "kis_cum_net_sell_qty": int(kis_sell_at_cutoff),
                "coverage_pct": round(coverage_pct, 2),
                "unmatched_qty": max(0, int(unlocked_qty_at_cutoff - kis_sell_at_cutoff)),
            })

    effective_exercised_to_date = exercised_to_date + kis_assumed_exercise_qty
    effective_remaining_total = max(0, total_lockup_qty - effective_exercised_to_date)
    effective_currently_unlocked_remaining = max(0, unlocked_to_date - effective_exercised_to_date)

    exercise_remaining = exercised_to_date
    lockup_rows = []
    upcoming_by_date = {}
    unlocked_by_date = {}
    for r in lockups_sorted:
        qty = max(0, int(r.get("quantity") or 0))
        consumed = min(qty, exercise_remaining)
        exercise_remaining -= consumed
        remaining_qty = max(0, qty - consumed)
        unlock_date = (r.get("lockup_end_date") or "")
        is_unlocked = unlock_date <= today
        row = {
            **r,
            "consumed_by_exercise": consumed,
            "remaining_qty": remaining_qty,
            "is_unlocked": is_unlocked,
            "available_now_qty": remaining_qty if is_unlocked else 0,
            "upcoming_qty": remaining_qty if not is_unlocked else 0,
        }
        lockup_rows.append(row)
        if unlock_date:
            unlocked_by_date.setdefault(unlock_date, 0)
            unlocked_by_date[unlock_date] += remaining_qty
            if not is_unlocked:
                upcoming_by_date.setdefault(unlock_date, 0)
                upcoming_by_date[unlock_date] += remaining_qty

    stock_name = ""
    if lockups_sorted:
        stock_name = lockups_sorted[0].get("stock_name") or ""
    elif exercises_sorted:
        stock_name = exercises_sorted[0].get("stock_name") or ""

    timeline = []
    cumulative = 0
    for r in exercises_sorted:
        qty = max(0, int(r.get("quantity") or 0))
        cumulative += qty
        timeline.append({
            **r,
            "remaining_after_event": max(0, total_lockup_qty - cumulative),
        })
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "summary": {
            "as_of_date": today,
            "ipo_overhang_total_qty": total_lockup_qty,
            "exercised_to_date_qty": exercised_to_date,
            "remaining_overhang_qty": remaining_total,
            "remaining_overhang_qty_effective": effective_remaining_total,
            "unlocked_to_date_qty": unlocked_to_date,
            "currently_unlocked_remaining_qty": currently_unlocked_remaining,
            "currently_unlocked_remaining_qty_effective": effective_currently_unlocked_remaining,
            "upcoming_overhang_qty": sum(upcoming_by_date.values()),
            "listing_date": listing_date.isoformat() if listing_date else "",
            "listing_age_days": listing_age_days if listing_age_days is not None else -1,
            "is_recent_ipo_under_6m": bool(is_recent_ipo_under_6m),
            "kis_institution_cum_net_sell_qty": int(kis_inst_cum_net_sell_qty),
            "kis_assumed_exercise_qty": int(kis_assumed_exercise_qty),
            "exercised_to_date_qty_effective": int(effective_exercised_to_date),
        },
        "lockups": lockup_rows,
        "exercise_events": timeline,
        "upcoming_by_unlock_date": [
            {"unlock_date": d, "qty": int(q)}
            for d, q in sorted(upcoming_by_date.items(), key=lambda x: x[0])
        ],
        "available_by_unlock_date": [
            {"unlock_date": d, "qty": int(q)}
            for d, q in sorted(unlocked_by_date.items(), key=lambda x: x[0])
        ],
        "kis_milestones": kis_milestone_rows,
    }


@app.get("/api/overhang/search")
async def api_overhang_search(name: str):
    q = (name or "").strip()
    if len(q) < 1:
        return []
    results = await search_stock_by_name(q)
    return [
        {
            "stock_name": r.get("name", ""),
            "stock_code": r.get("code", ""),
            "market": r.get("market", ""),
        }
        for r in (results or [])[:20]
    ]


@app.get("/api/overhang/{stock_code}")
async def api_overhang_status(stock_code: str):
    code = _normalize_stock_code_any(stock_code)
    if not _is_valid_stock_code_any(code):
        raise HTTPException(400, "stock_code는 영문/숫자 6자리여야 합니다")
    return await _build_overhang_status(code)


@app.post("/api/overhang/sync-dart")
async def api_overhang_sync_dart(req: OverhangDartSyncRequest):
    code = _normalize_stock_code_any(req.stock_code)
    if not _is_valid_stock_code_any(code):
        raise HTTPException(400, "stock_code는 영문/숫자 6자리여야 합니다")
    return await _sync_overhang_from_dart(code, (req.stock_name or "").strip())


@app.post("/api/overhang/lockups")
def api_overhang_add_lockup(req: OverhangLockupCreate):
    code = _normalize_stock_code_any(req.stock_code)
    name = (req.stock_name or "").strip()
    holder = (req.holder_name or "").strip()
    lockup_end = (req.lockup_end_date or "").strip()
    if not _is_valid_stock_code_any(code):
        raise HTTPException(400, "stock_code는 영문/숫자 6자리여야 합니다")
    if not name:
        raise HTTPException(400, "stock_name은 필수입니다")
    if not holder:
        raise HTTPException(400, "holder_name은 필수입니다")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", lockup_end):
        raise HTTPException(400, "lockup_end_date는 YYYY-MM-DD 형식이어야 합니다")
    if int(req.quantity or 0) <= 0:
        raise HTTPException(400, "quantity는 1 이상이어야 합니다")
    row_id = add_overhang_lockup(
        stock_code=code,
        stock_name=name,
        holder_name=holder,
        holder_type=(req.holder_type or "").strip(),
        lockup_end_date=lockup_end,
        quantity=int(req.quantity),
        source_note=(req.source_note or "").strip(),
    )
    return {"id": row_id}


@app.delete("/api/overhang/lockups/{lockup_id}")
def api_overhang_delete_lockup(lockup_id: int):
    delete_overhang_lockup(lockup_id)
    return {"ok": True}


@app.post("/api/overhang/exercises")
def api_overhang_add_exercise(req: OverhangExerciseCreate):
    code = _normalize_stock_code_any(req.stock_code)
    name = (req.stock_name or "").strip()
    ex_date = (req.exercise_date or "").strip()
    if not _is_valid_stock_code_any(code):
        raise HTTPException(400, "stock_code는 영문/숫자 6자리여야 합니다")
    if not name:
        raise HTTPException(400, "stock_name은 필수입니다")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", ex_date):
        raise HTTPException(400, "exercise_date는 YYYY-MM-DD 형식이어야 합니다")
    if int(req.quantity or 0) <= 0:
        raise HTTPException(400, "quantity는 1 이상이어야 합니다")
    row_id = add_overhang_exercise(
        stock_code=code,
        stock_name=name,
        exercise_date=ex_date,
        quantity=int(req.quantity),
        note=(req.note or "").strip(),
    )
    return {"id": row_id}


@app.delete("/api/overhang/exercises/{exercise_id}")
def api_overhang_delete_exercise(exercise_id: int):
    delete_overhang_exercise(exercise_id)
    return {"ok": True}


# --- Disclosure Compare API ---

@app.get("/api/disclosure-compare/watchlist")
def api_disclosure_compare_watchlist():
    return get_quarterly_perf_watchlist()


@app.get("/api/disclosure-compare/reports")
async def api_disclosure_compare_reports(stock_code: str):
    code = (stock_code or "").strip().zfill(6)
    if not re.match(r"^\d{6}$", code):
        raise HTTPException(400, "stock_code는 6자리 숫자여야 합니다")
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(500, "DART_API_KEY not configured")

    corp_code = await get_corp_code_by_stock(api_key, code)
    if not corp_code:
        raise HTTPException(404, "해당 종목의 DART corp_code를 찾지 못했습니다")

    reports = await fetch_periodic_reports(api_key, corp_code, limit=40)
    return {"stock_code": code, "corp_code": corp_code, "reports": reports}


@app.get("/api/disclosure-compare/compare")
async def api_disclosure_compare_compare(
    stock_code: str,
    left_bsns_year: str,
    left_reprt_code: str,
    right_bsns_year: str,
    right_reprt_code: str,
):
    code = (stock_code or "").strip().zfill(6)
    if not re.match(r"^\d{6}$", code):
        raise HTTPException(400, "stock_code는 6자리 숫자여야 합니다")
    if not re.match(r"^\d{4}$", str(left_bsns_year or "")) or not re.match(r"^\d{4}$", str(right_bsns_year or "")):
        raise HTTPException(400, "bsns_year는 4자리 숫자여야 합니다")
    if str(left_reprt_code) not in {"11011", "11012", "11013"} or str(right_reprt_code) not in {"11011", "11012", "11013"}:
        raise HTTPException(400, "reprt_code는 11011/11012/11013 중 하나여야 합니다")

    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(500, "DART_API_KEY not configured")

    corp_code = await get_corp_code_by_stock(api_key, code)
    if not corp_code:
        raise HTTPException(404, "해당 종목의 DART corp_code를 찾지 못했습니다")

    left_rows = await fetch_fnltt_rows(api_key, corp_code, str(left_bsns_year), str(left_reprt_code))
    right_rows = await fetch_fnltt_rows(api_key, corp_code, str(right_bsns_year), str(right_reprt_code))

    diff = compare_fnltt_rows(left_rows, right_rows)
    return {
        "stock_code": code,
        "corp_code": corp_code,
        "left": {
            "bsns_year": str(left_bsns_year),
            "reprt_code": str(left_reprt_code),
            "report_name": reprt_code_to_name(str(left_reprt_code)),
            "row_count": len(left_rows),
        },
        "right": {
            "bsns_year": str(right_bsns_year),
            "reprt_code": str(right_reprt_code),
            "report_name": reprt_code_to_name(str(right_reprt_code)),
            "row_count": len(right_rows),
        },
        **diff,
    }


@app.get("/api/disclosure-compare/text-compare")
async def api_disclosure_compare_text_compare(
    stock_code: str,
    left_rcept_no: str,
    right_rcept_no: str,
    unit: str = "paragraph",
):
    code = (stock_code or "").strip().zfill(6)
    if not re.match(r"^\d{6}$", code):
        raise HTTPException(400, "stock_code는 6자리 숫자여야 합니다")
    if not re.match(r"^\d{14}$", str(left_rcept_no or "")) or not re.match(r"^\d{14}$", str(right_rcept_no or "")):
        raise HTTPException(400, "rcept_no는 14자리 숫자여야 합니다")
    if unit not in {"paragraph", "sentence"}:
        raise HTTPException(400, "unit은 paragraph/sentence 중 하나여야 합니다")

    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(500, "DART_API_KEY not configured")

    try:
        left_text, right_text = await asyncio.gather(
            fetch_disclosure_document_text(api_key, str(left_rcept_no)),
            fetch_disclosure_document_text(api_key, str(right_rcept_no)),
        )
    except Exception as e:
        raise HTTPException(500, f"공시 원문 조회 실패: {str(e)}")

    diff = compare_document_text(left_text, right_text, unit=unit)
    return {
        "stock_code": code,
        "left_rcept_no": str(left_rcept_no),
        "right_rcept_no": str(right_rcept_no),
        **diff,
    }


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


@app.get("/usdc")
def usdc():
    return FileResponse(os.path.join(static_dir, "usdc.html"))

@app.get("/semiconductor-prices")
def semiconductor_prices():
    return FileResponse(os.path.join(static_dir, "semiconductor-prices.html"))

@app.get("/market")
def market():
    return FileResponse(os.path.join(static_dir, "market.html"))

@app.get("/deposit-fund")
def deposit_fund():
    return FileResponse(os.path.join(static_dir, "deposit-fund.html"))

@app.get("/youtube")
def youtube():
    return FileResponse(os.path.join(static_dir, "youtube.html"))

@app.get("/blog")
def blog():
    return FileResponse(os.path.join(static_dir, "blog.html"))

@app.get("/us-market")
def us_market():
    return FileResponse(os.path.join(static_dir, "us-market.html"))


@app.get("/trading-trend")
def trading_trend():
    return FileResponse(os.path.join(static_dir, "trading-trend.html"))


@app.get("/quarterly-performance")
def quarterly_performance():
    return FileResponse(os.path.join(static_dir, "quarterly-performance.html"))


@app.get("/stock-monitor")
def stock_monitor():
    return FileResponse(os.path.join(static_dir, "stock-monitor.html"))


@app.get("/disclosure-compare")
def disclosure_compare():
    return FileResponse(os.path.join(static_dir, "disclosure-compare.html"))


@app.get("/overhang")
def overhang():
    return FileResponse(os.path.join(static_dir, "overhang.html"))
