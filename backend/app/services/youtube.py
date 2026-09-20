"""YouTube Data API v3 integration client.

Adheres to strict defensive design and minimal quota consumption rules:
- Strictly prohibits 'search.list' (100 units).
- Uses 'playlists.list' (1 unit), 'playlistItems.list' (1 unit), and batch 'videos.list' (1 unit for 50 videos).
- Never leaks API keys in exception messages or logs.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# ISO 8601 Duration Parser: PT#H#M#S
ISO8601_DURATION_REGEX = re.compile(
    r"^P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


def parse_iso8601_duration(duration_str: Optional[str]) -> Optional[int]:
    """Parse an ISO 8601 duration string (e.g., 'PT1H23M45S') into total seconds.

    Returns None if the string is empty or malformed.
    """
    if not duration_str:
        return None

    match = ISO8601_DURATION_REGEX.match(duration_str)
    if not match:
        return None

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def parse_rfc3339_datetime(dt_str: str) -> datetime:
    """Safely parse RFC 3339 datetime string from YouTube API into timezone-aware datetime."""
    try:
        # Handle 'Z' suffix
        cleaned = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return datetime.now(timezone.utc)


def extract_best_thumbnail(thumbnails: Dict[str, Any]) -> Optional[str]:
    """Extract the highest quality available thumbnail URL from YouTube snippet."""
    for quality in ("maxres", "standard", "high", "medium", "default"):
        thumb = thumbnails.get(quality)
        if thumb and isinstance(thumb, dict) and "url" in thumb:
            return thumb["url"]
    return None


@dataclass
class YouTubePlaylistData:
    id: str
    title: str
    description: str
    thumbnail_url: Optional[str]


@dataclass
class YouTubeVideoData:
    id: str
    title: str
    description: str
    published_at: datetime
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    view_count: Optional[int]
    is_members_only: bool = False


def derive_channel_playlist_id(channel_id: str, prefix: str) -> Optional[str]:
    """Derive special YouTube internal playlist IDs by substituting the 'UC' channel prefix.
    
    Examples:
    - UUMO + [suffix]: All membership-exclusive videos
    - UUMF + [suffix]: Membership-exclusive long-form videos
    - UULF + [suffix]: General public long-form videos
    - UU   + [suffix]: All uploaded videos
    """
    if not channel_id:
        return None
    cid = channel_id.strip()
    if cid.startswith("UC") and len(cid) >= 3:
        return f"{prefix}{cid[2:]}"
    return None


class YouTubeAPIError(Exception):
    """Base exception for YouTube API failures."""
    pass


class YouTubeQuotaExceededError(YouTubeAPIError):
    """Raised when YouTube API quota has been exceeded (403 quotaExceeded)."""
    pass


class YouTubeClient:
    """Lightweight and quota-optimized YouTube Data API v3 client."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, timeout: float = 15.0):
        if not api_key or api_key.startswith("your_"):
            raise ValueError("Invalid YouTube API key provided.")
        self._api_key = api_key
        self.timeout = timeout

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return params with masked API key for safe logging."""
        sanitized = dict(params)
        if "key" in sanitized:
            sanitized["key"] = "***REDACTED***"
        return sanitized

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GET request with error handling and quota monitoring."""
        request_params = dict(params)
        request_params["key"] = self._api_key

        url = f"{self.BASE_URL}/{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=request_params)

            if response.status_code == 200:
                return response.json()

            # Handle errors defensively
            error_data = {}
            try:
                error_data = response.json().get("error", {})
            except Exception:
                pass

            message = error_data.get("message", f"HTTP {response.status_code}")
            reasons = [e.get("reason") for e in error_data.get("errors", []) if isinstance(e, dict)]

            if "quotaExceeded" in reasons or response.status_code == 403:
                logger.error("YouTube API quota exceeded or forbidden: %s", message)
                raise YouTubeQuotaExceededError(f"YouTube API quota exceeded: {message}")

            logger.error("YouTube API error (%d): %s (reasons: %s)", response.status_code, message, reasons)
            raise YouTubeAPIError(f"YouTube API error: {message}")

        except httpx.RequestError as exc:
            logger.error("Network error while connecting to YouTube API: %s", exc)
            raise YouTubeAPIError(f"Network error communicating with YouTube API: {exc}") from exc

    def get_channel_playlists(self, channel_id: str, max_results: int = 50) -> List[YouTubePlaylistData]:
        """Fetch public playlists for a channel using 'playlists.list' (1 quota unit)."""
        playlists: List[YouTubePlaylistData] = []
        page_token: Optional[str] = None

        while True:
            params: Dict[str, Any] = {
                "part": "snippet,contentDetails",
                "channelId": channel_id,
                "maxResults": min(max_results, 50),
            }
            if page_token:
                params["pageToken"] = page_token

            data = self._request("playlists", params)
            items = data.get("items", [])
            for item in items:
                snippet = item.get("snippet", {})
                playlist_id = item.get("id")
                if not playlist_id:
                    continue
                playlists.append(
                    YouTubePlaylistData(
                        id=playlist_id,
                        title=snippet.get("title", ""),
                        description=snippet.get("description", ""),
                        thumbnail_url=extract_best_thumbnail(snippet.get("thumbnails", {})),
                    )
                )

            page_token = data.get("nextPageToken")
            if not page_token or len(playlists) >= max_results:
                break

        return playlists

    def get_playlist_items(self, playlist_id: str, max_results: int = 200) -> List[Dict[str, Any]]:
        """Fetch video references and ordering from a playlist using 'playlistItems.list' (1 unit per 50).

        Returns list of dict with 'video_id', 'position', 'title', 'description', 'published_at', 'thumbnail_url'.
        """
        items_result: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            params: Dict[str, Any] = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token

            data = self._request("playlistItems", params)
            items = data.get("items", [])
            for item in items:
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId")

                # Skip deleted or private videos
                if not video_id or snippet.get("title") in ("Private video", "Deleted video"):
                    continue

                position = snippet.get("position", len(items_result))
                items_result.append(
                    {
                        "video_id": video_id,
                        "position": position,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "published_at": parse_rfc3339_datetime(snippet.get("publishedAt", "")),
                        "thumbnail_url": extract_best_thumbnail(snippet.get("thumbnails", {})),
                    }
                )

            page_token = data.get("nextPageToken")
            if not page_token or len(items_result) >= max_results:
                break

        return items_result

    def get_videos_details(self, video_ids: List[str]) -> Dict[str, YouTubeVideoData]:
        """Batch fetch detailed video statistics & durations using 'videos.list' (1 quota unit per 50 IDs)."""
        if not video_ids:
            return {}

        results: Dict[str, YouTubeVideoData] = {}
        # Batch by 50 IDs max
        chunk_size = 50
        for i in range(0, len(video_ids), chunk_size):
            chunk = video_ids[i : i + chunk_size]
            params = {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(chunk),
                "maxResults": 50,
            }
            data = self._request("videos", params)
            for item in data.get("items", []):
                vid = item.get("id")
                if not vid:
                    continue
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                stats = item.get("statistics", {})

                duration_str = content_details.get("duration")
                duration_seconds = parse_iso8601_duration(duration_str)

                view_count = None
                if "viewCount" in stats:
                    try:
                        view_count = int(stats["viewCount"])
                    except (ValueError, TypeError):
                        view_count = 0

                results[vid] = YouTubeVideoData(
                    id=vid,
                    title=snippet.get("title", ""),
                    description=snippet.get("description", ""),
                    published_at=parse_rfc3339_datetime(snippet.get("publishedAt", "")),
                    thumbnail_url=extract_best_thumbnail(snippet.get("thumbnails", {})),
                    duration_seconds=duration_seconds,
                    view_count=view_count,
                )

        return results
