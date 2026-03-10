import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=False)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

API_KEY = os.getenv("YOUTUBE_API_KEY", "")
BASE_URL = "https://www.googleapis.com/youtube/v3"


async def resolve_channel(identifier: str) -> dict | None:
    """Resolve a channel ID, handle, or custom URL to channel info.
    Returns {"channel_id": ..., "channel_name": ..., "channel_url": ...} or None.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # Try as channel ID first
        if identifier.startswith("UC"):
            resp = await client.get(f"{BASE_URL}/channels", params={
                "key": API_KEY, "part": "snippet", "id": identifier,
            })
            data = resp.json()
            if data.get("items"):
                item = data["items"][0]
                return {
                    "channel_id": item["id"],
                    "channel_name": item["snippet"]["title"],
                    "channel_url": f"https://www.youtube.com/channel/{item['id']}",
                }

        # Try as handle (@username) or custom URL
        handle = identifier.lstrip("@")
        for search_type in ["forHandle", "forUsername"]:
            resp = await client.get(f"{BASE_URL}/channels", params={
                "key": API_KEY, "part": "snippet", search_type: handle,
            })
            data = resp.json()
            if data.get("items"):
                item = data["items"][0]
                return {
                    "channel_id": item["id"],
                    "channel_name": item["snippet"]["title"],
                    "channel_url": f"https://www.youtube.com/channel/{item['id']}",
                }

        # Fallback: search
        resp = await client.get(f"{BASE_URL}/search", params={
            "key": API_KEY, "part": "snippet", "q": identifier,
            "type": "channel", "maxResults": 1,
        })
        data = resp.json()
        if data.get("items"):
            item = data["items"][0]
            cid = item["snippet"]["channelId"]
            return {
                "channel_id": cid,
                "channel_name": item["snippet"]["channelTitle"],
                "channel_url": f"https://www.youtube.com/channel/{cid}",
            }
    return None


async def fetch_latest_videos(channel_id: str, max_results: int = 10) -> list[dict]:
    """Fetch latest videos from a channel using the search API."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/search", params={
            "key": API_KEY,
            "channelId": channel_id,
            "part": "snippet",
            "order": "date",
            "type": "video",
            "maxResults": max_results,
        })
        data = resp.json()
        if "error" in data:
            raise Exception(data["error"].get("message", "YouTube API error"))

        videos = []
        for item in data.get("items", []):
            vid = item["id"].get("videoId")
            if not vid:
                continue
            snip = item["snippet"]
            videos.append({
                "video_id": vid,
                "title": snip.get("title", ""),
                "description": snip.get("description", ""),
                "thumbnail_url": snip.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "published_at": snip.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
            })
        return videos
