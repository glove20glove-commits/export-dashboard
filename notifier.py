import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=False)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
VISIT_CHAT_IDS = [x.strip() for x in os.getenv("TELEGRAM_VISIT_CHAT_ID", "").split(",") if x.strip()]

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://web-production-a69d3.up.railway.app")


async def send_telegram(message: str, use_group: bool = False):
    """Send a message to the configured Telegram chat(s)."""
    chats = (VISIT_CHAT_IDS or [CHAT_ID]) if use_group else [CHAT_ID]
    if not BOT_TOKEN or not any(chats):
        print("[notifier] TELEGRAM_BOT_TOKEN or chat ID not set")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        for chat in chats:
            await client.post(url, data={
                "chat_id": chat,
                "text": message,
                "parse_mode": "HTML",
            })


def notify_visit_update_sync(company_name: str, company_id: int, update_type: str, detail: str = ""):
    """Send a visit-related update notification to Telegram (sync)."""
    chats = VISIT_CHAT_IDS or [CHAT_ID]
    if not BOT_TOKEN or not any(chats):
        print("[notifier] TELEGRAM_BOT_TOKEN or chat ID not set")
        return
    link = f"{DASHBOARD_URL}/visit?company={company_id}"
    lines = [f"<b>탐방 업데이트</b>", "", f"<b>{company_name}</b> — {update_type}"]
    if detail:
        lines.append(detail)
    lines.append(f"\n<a href=\"{link}\">바로가기</a>")
    msg = "\n".join(lines)
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat in chats:
        try:
            resp = httpx.post(api_url, data={
                "chat_id": chat,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }, timeout=10)
            print(f"[notifier] visit update sent to {chat}: {resp.status_code}")
        except Exception as e:
            print(f"[notifier] visit update to {chat} failed: {e}")


async def notify_update(item_label: str, year: str, month: str, export_amt: int, import_amt: int, balance: int, export_rate: float):
    """Send a trade data update notification."""
    trend = "📈" if export_rate >= 0 else "📉"
    msg = (
        f"<b>무역통계 업데이트</b>\n\n"
        f"<b>{item_label}</b>\n"
        f"{year}년 {int(month)}월 데이터\n\n"
        f"수출: <b>{export_amt:,}</b> 천불 ({trend} {export_rate:+.1f}%)\n"
        f"수입: <b>{import_amt:,}</b> 천불\n"
        f"수지: <b>{balance:,}</b> 천불"
    )
    await send_telegram(msg)
