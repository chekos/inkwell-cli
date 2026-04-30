"""Resolve YouTube URLs of any shape to the channel's media-RSS feed URL.

Users can paste a video URL, channel URL, @handle, /c/ URL, /user/ URL, /live/
URL, /embed/ URL, /shorts/ URL, or a youtu.be short link — this module turns any
of them into `https://www.youtube.com/feeds/videos.xml?channel_id=UC…` that
inkwell's existing RSS pipeline understands.

URL shapes where the channel_id is derivable from the path (e.g. /channel/UCxxx)
are handled without network. Everything else is resolved via yt-dlp (already a
project dependency) with opts tuned to avoid enumerating the whole video list.
"""

import asyncio
import re
from typing import NamedTuple
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL  # type: ignore[import-untyped]
from yt_dlp.utils import DownloadError, ExtractorError  # type: ignore[import-untyped]

from inkwell.utils.errors import ValidationError


class ResolvedFeed(NamedTuple):
    """Channel RSS feed URL plus optional channel name.

    `channel_name` is populated when yt-dlp was consulted (watch, @handle,
    youtu.be, etc.) and is None for pure URL-shape resolution (`/channel/UC…`
    or already-resolved `feeds/videos.xml?channel_id=…` inputs).
    """

    feed_url: str
    channel_name: str | None = None
    episode_title: str | None = None


YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})

_CHANNEL_PATH_RE = re.compile(r"^/channel/(UC[A-Za-z0-9_-]+)/?")
_FEED_PATH = "/feeds/videos.xml"
_FEED_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# Covers slow/unresponsive yt-dlp HTTP calls so `inkwell add` doesn't hang forever.
_YTDLP_SOCKET_TIMEOUT_SECONDS = 30

_MANUAL_ESCAPE_HATCH = (
    "If resolution keeps failing, you can still add the channel manually: "
    "inkwell add 'https://www.youtube.com/feeds/videos.xml?channel_id=UCxxx' --feed-name X"
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
    user paste a YouTube link?" (e.g. the `--save-feed` hint).
    """
    parts = _parse(url)
    return parts is not None and _is_youtube_host(parts[0])


def is_youtube_playlist_url(url: str) -> bool:
    """Lightweight check for YouTube playlist URLs (no network).

    Lets callers reject playlists fail-fast before kicking off the pipeline.
    Non-YouTube URLs return False (callers should gate on `is_youtube_url`
    first if the distinction matters).
    """
    parts = _parse(url)
    if parts is None:
        return False
    host, path, query = parts
    return _is_youtube_host(host) and _is_playlist_url(path, query)


def channel_id_from_feed_url(url: str) -> str | None:
    """Return channel_id from a normalized YouTube media-RSS URL, if present."""
    parts = _parse(url)
    if parts is None:
        return None
    host, path, query = parts
    if not _is_youtube_host(host) or path != _FEED_PATH:
        return None
    channel_ids = query.get("channel_id", [])
    return next((channel_id for channel_id in channel_ids if channel_id), None)


def _is_already_resolved_feed_url(host: str, path: str, query: dict[str, list[str]]) -> bool:
    # Require a non-empty channel_id value; `?channel_id=` alone would slip
    # through otherwise and reach yt-dlp with an RSS XML URL.
    channel_ids = query.get("channel_id", [])
    return path == _FEED_PATH and any(cid for cid in channel_ids)


def _is_playlist_url(path: str, query: dict[str, list[str]]) -> bool:
    # Require a segment boundary on /playlist so /playlists (the listing page)
    # isn't false-positived as a single-playlist URL.
    return "list" in query or path == "/playlist" or path.startswith("/playlist/")


def _channel_id_from_path(path: str) -> str | None:
    match = _CHANNEL_PATH_RE.match(path)
    return match.group(1) if match else None


def _resolve_with_ytdlp(url: str) -> ResolvedFeed:
    """Synchronous yt-dlp call to get the channel's media-RSS feed URL + name.

    Uses extract_flat + playlist_items: "0" so channel URLs don't enumerate
    every video — we only want the channel metadata.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlist_items": "0",
        "skip_download": True,
        "socket_timeout": _YTDLP_SOCKET_TIMEOUT_SECONDS,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
    except (DownloadError, ExtractorError, OSError) as e:
        # OSError covers transient network failures (ssl.SSLError,
        # urllib.error.URLError) that yt-dlp re-raises without wrapping.
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
    episode_title = info.get("title") if isinstance(info.get("title"), str) else None
    return ResolvedFeed(
        feed_url=_FEED_URL_TEMPLATE.format(channel_id=channel_id),
        channel_name=channel_name,
        episode_title=episode_title,
    )


async def resolve_youtube_url(url: str) -> ResolvedFeed | None:
    """Resolve a YouTube URL to its channel's media-RSS feed URL (+ name).

    Returns:
        `ResolvedFeed(feed_url, channel_name)` for recognized YouTube URLs.
        `channel_name` is populated when yt-dlp was consulted, None otherwise.
        `None` for non-YouTube URLs so callers fall through to the existing
        RSS flow.

    Raises:
        ValidationError for playlist URLs (out of scope), for YouTube URLs
        that yt-dlp can't resolve, and for the YouTube homepage.
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
        return ResolvedFeed(feed_url=url, channel_name=None)

    channel_id = _channel_id_from_path(path)
    if channel_id:
        return ResolvedFeed(
            feed_url=_FEED_URL_TEMPLATE.format(channel_id=channel_id),
            channel_name=None,
        )

    # Reject the root/homepage before handing off to yt-dlp so users get a
    # specific error instead of yt-dlp's opaque "video may be private" message.
    if path in ("", "/"):
        raise ValidationError(
            "Paste a channel or video URL, not the YouTube homepage",
            suggestion=(
                "Examples: https://www.youtube.com/@somehandle, "
                "https://www.youtube.com/channel/UCxxx, "
                "https://www.youtube.com/watch?v=VIDEOID"
            ),
        )

    return await asyncio.to_thread(_resolve_with_ytdlp, url)
