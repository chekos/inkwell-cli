"""Resolve YouTube URLs of any shape to the channel's media-RSS feed URL.

Users can paste a video URL, channel URL, @handle, /c/ URL, /user/ URL, /live/
URL, /embed/ URL, /shorts/ URL, or a youtu.be short link — this module turns any
of them into `https://www.youtube.com/feeds/videos.xml?channel_id=UC…` that
inkwell's existing RSS pipeline understands.

URL shapes where the channel_id is derivable from the path (e.g. /channel/UCxxx)
are handled without network. Everything else is resolved via yt-dlp (already a
project dependency) with opts tuned to avoid enumerating the whole video list.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL  # type: ignore[import-untyped]
from yt_dlp.utils import DownloadError, ExtractorError  # type: ignore[import-untyped]

from inkwell.utils.errors import ValidationError

YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})

_CHANNEL_PATH_RE = re.compile(r"^/channel/(UC[A-Za-z0-9_-]+)/?")
_FEED_PATH = "/feeds/videos.xml"
_FEED_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

_MANUAL_ESCAPE_HATCH = (
    "If resolution keeps failing, you can still add the channel manually: "
    "inkwell add 'https://www.youtube.com/feeds/videos.xml?channel_id=UCxxx' --name X"
)


def _parse(url: str) -> tuple[str, str, dict[str, list[str]]] | None:
    """Split a URL into (host_lower, path, query_params).

    Returns None for URLs that are unusable (missing scheme/host).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname:
        return None
    return parsed.hostname.lower(), parsed.path, parse_qs(parsed.query)


def _is_youtube_host(host: str) -> bool:
    return host in YOUTUBE_HOSTS


def is_youtube_url(url: str) -> bool:
    """Lightweight host-only check: is this a YouTube URL?

    Does not touch the network, does not validate the URL path or query
    structure. Intended for callers that just want to gate UI on "did the
    user paste a YouTube link?" (e.g. the `--save-source` hint).
    """
    parts = _parse(url)
    return parts is not None and _is_youtube_host(parts[0])


def _is_already_resolved_feed_url(host: str, path: str, query: dict[str, list[str]]) -> bool:
    return path == _FEED_PATH and "channel_id" in query


def _is_playlist_url(path: str, query: dict[str, list[str]]) -> bool:
    return "list" in query or path.startswith("/playlist")


def _channel_id_from_path(path: str) -> str | None:
    match = _CHANNEL_PATH_RE.match(path)
    return match.group(1) if match else None


def _build_feed_url(channel_id: str) -> str:
    return _FEED_URL_TEMPLATE.format(channel_id=channel_id)


def _resolve_with_ytdlp(url: str) -> tuple[str, str | None]:
    """Synchronous yt-dlp call to get channel_id + channel name for a URL.

    Uses extract_flat + playlist_items: "0" so channel URLs don't enumerate
    every video — we only want the channel metadata.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlist_items": "0",
        "skip_download": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
    except (DownloadError, ExtractorError) as e:
        raise ValidationError(
            f"Couldn't resolve YouTube URL: {e}",
            suggestion=_MANUAL_ESCAPE_HATCH,
        ) from e

    channel_id = info.get("channel_id")
    if not channel_id:
        raise ValidationError(
            "Couldn't resolve YouTube URL: no channel_id returned "
            "(video may be private, region-blocked, or deleted)",
            suggestion=_MANUAL_ESCAPE_HATCH,
        )
    channel_name = info.get("channel") or info.get("uploader")
    return _build_feed_url(channel_id), channel_name


async def resolve_youtube_url(url: str) -> tuple[str, str | None] | None:
    """Resolve a YouTube URL to its channel's media-RSS feed URL.

    Returns:
        (feed_url, channel_name) for recognized YouTube URLs. channel_name is
        populated when yt-dlp was consulted; None for pure URL-shape resolution.
        None for non-YouTube URLs so callers fall through to the existing RSS
        flow.

    Raises:
        ValidationError for playlist URLs (out of scope) and for YouTube URLs
        that yt-dlp can't resolve.
    """
    parts = _parse(url)
    if parts is None:
        return None
    host, path, query = parts

    if not _is_youtube_host(host):
        return None

    if _is_playlist_url(path, query):
        raise ValidationError(
            "Playlist URLs aren't supported yet — try the channel URL instead",
            suggestion=(
                "Visit the playlist on YouTube and copy the channel's @handle "
                "or /channel/UC… URL from the creator."
            ),
        )

    if _is_already_resolved_feed_url(host, path, query):
        return url, None

    channel_id = _channel_id_from_path(path)
    if channel_id:
        return _build_feed_url(channel_id), None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _resolve_with_ytdlp, url)
