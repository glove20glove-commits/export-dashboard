"""
블로그 모니터링 클라이언트
- RSS/Atom 피드 자동 탐지
- RSS 기반 글 수집
- RSS 없을 시 웹 스크래핑 폴백
"""

import re
import hashlib
from datetime import datetime
from urllib.parse import urljoin

import httpx
import feedparser
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BlogMonitor/1.0)"}


async def discover_feed(url: str) -> dict:
    """
    URL에서 RSS/Atom 피드를 자동 탐지.
    반환: {"feed_url": "...", "title": "...", "language": ""}
    """
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")

        # 이미 RSS/Atom 피드 URL인 경우
        if "xml" in ct or "rss" in ct or "atom" in ct:
            feed = feedparser.parse(resp.text)
            return {
                "feed_url": url,
                "title": feed.feed.get("title", url),
                "language": feed.feed.get("language", ""),
            }

        # HTML에서 RSS 링크 찾기
        soup = BeautifulSoup(resp.text, "html.parser")
        page_title = soup.title.string.strip() if soup.title and soup.title.string else url

        feed_link = soup.find("link", attrs={"type": re.compile(r"(rss|atom)")})
        if feed_link and feed_link.get("href"):
            href = feed_link["href"]
            if not href.startswith("http"):
                href = urljoin(url, href)
            return {"feed_url": href, "title": page_title, "language": ""}

        # 흔한 RSS 경로 시도
        common_paths = ["/feed", "/rss", "/feeds/posts/default", "/atom.xml",
                        "/rss.xml", "/feed.xml", "/index.xml"]
        for path in common_paths:
            try:
                test_url = urljoin(url.rstrip("/") + "/", path.lstrip("/"))
                r = await client.get(test_url, headers=_HEADERS)
                if r.status_code == 200:
                    txt = r.text[:500]
                    ctype = r.headers.get("content-type", "")
                    if "xml" in ctype or "<rss" in txt or "<feed" in txt:
                        feed = feedparser.parse(r.text)
                        return {
                            "feed_url": test_url,
                            "title": feed.feed.get("title", page_title),
                            "language": feed.feed.get("language", ""),
                        }
            except Exception:
                continue

        # RSS를 찾지 못한 경우 → 스크래핑 모드
        return {"feed_url": "", "title": page_title, "language": ""}


async def fetch_articles_rss(feed_url: str) -> list[dict]:
    """RSS 피드에서 글 목록을 가져옵니다."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(feed_url, headers=_HEADERS)
            resp.raise_for_status()
    except Exception:
        return []

    feed = feedparser.parse(resp.text)
    articles = []
    for entry in feed.entries[:50]:
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content = entry.summary or ""

        if content:
            soup = BeautifulSoup(content, "html.parser")
            content = soup.get_text(separator="\n", strip=True)

        published = ""
        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    published = datetime(*parsed[:6]).strftime("%Y-%m-%d")
                except Exception:
                    pass
                break

        guid = entry.get("id") or entry.get("link") or hashlib.md5(
            entry.get("title", "").encode()
        ).hexdigest()

        articles.append({
            "guid": guid,
            "url": entry.get("link", ""),
            "title": entry.get("title", "(제목 없음)"),
            "author": entry.get("author", ""),
            "published_at": published,
            "content": content[:8000],
        })
    return articles


async def fetch_articles_scrape(url: str) -> list[dict]:
    """RSS가 없는 경우 웹 스크래핑으로 글 목록을 가져옵니다."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)
        if not text or len(text) < 10 or href in seen:
            continue
        if not href.startswith("http"):
            href = urljoin(url, href)
        if any(skip in href.lower() for skip in [
            "#", "javascript:", "mailto:", "/tag/", "/category/", "/author/",
            "/page/", "login", "signup", "search",
        ]):
            continue
        seen.add(href)
        articles.append({
            "guid": hashlib.md5(href.encode()).hexdigest(),
            "url": href,
            "title": text[:200],
            "author": "",
            "published_at": "",
            "content": "",
        })
        if len(articles) >= 20:
            break
    return articles


async def fetch_article_content(url: str) -> str:
    """개별 글 URL에서 본문 텍스트를 가져옵니다."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        main = (soup.find("article") or soup.find("main") or
                soup.find("div", class_=re.compile(r"content|post|entry|article")))
        if main:
            return main.get_text(separator="\n", strip=True)[:6000]
        return soup.get_text(separator="\n", strip=True)[:4000]
    except Exception:
        return ""
