"""URL metadata extraction for direct URL captures.

Extracts meaningful titles and creates short slugs from URLs,
supporting YouTube, audio files, and generic URLs.
"""

import hashlib
import logging
import re
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Default podcast name for direct URL captures
INBOX_PODCAST_NAME = "_inbox"


class URLMetadata(BaseModel):
    """Metadata extracted from a URL."""

    title: str | None = None
    video_id: str | None = None
    domain: str | None = None
    duration_seconds: float | None = None


def extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from URL.

    Handles various YouTube URL formats:
    - youtube.com/watch?v=ID
    - youtu.be/ID
    - youtube.com/embed/ID
    - youtube.com/v/ID

    Args:
        url: YouTube URL

    Returns:
        Video ID or None if not a YouTube URL
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")

    if host in ("youtube.com", "m.youtube.com"):
        # Standard watch URL
        if parsed.path == "/watch":
            query = parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]
        # Embed or v URL
        elif parsed.path.startswith(("/embed/", "/v/")):
            parts = parsed.path.split("/")
            if len(parts) >= 3:
                return parts[2].split("?")[0]
    elif host == "youtu.be":
        # Short URL
        return parsed.path.lstrip("/").split("?")[0]

    return None


def extract_url_slug(url: str) -> str:
    """Extract a short slug from any URL.

    For non-YouTube URLs, creates a short hash-based identifier.

    Args:
        url: Any URL

    Returns:
        Short, filesystem-safe slug (8-12 chars)
    """
    # Try YouTube first
    yt_id = extract_youtube_id(url)
    if yt_id:
        return yt_id

    # For other URLs, use a hash of the full URL
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    return url_hash


def extract_filename_from_url(url: str) -> str | None:
    """Extract filename from URL path.

    Args:
        url: URL to extract filename from

    Returns:
        Filename without extension, or None
    """
    parsed = urlparse(url)
    path = parsed.path

    # Get last path segment
    if "/" in path:
        filename = path.rsplit("/", 1)[-1]
        # Remove extension
        if "." in filename:
            filename = filename.rsplit(".", 1)[0]
        # Clean up
        filename = re.sub(r"[^\w\s-]", "", filename)
        filename = re.sub(r"[-\s]+", "-", filename).strip("-")
        if filename and len(filename) > 3:
            return filename

    return None


def create_fallback_title(url: str) -> str:
    """Create a fallback title from URL when no metadata is available.

    Args:
        url: Source URL

    Returns:
        Human-readable fallback title
    """
    # Try to get filename from URL
    filename = extract_filename_from_url(url)
    if filename:
        # Convert slug back to title case
        return filename.replace("-", " ").title()

    # Use domain + short ID
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").split(".")[0].title()
    short_id = extract_url_slug(url)[:8]

    return f"{domain} {short_id}"


async def extract_url_metadata(url: str) -> URLMetadata:
    """Extract metadata from URL without downloading.

    Uses yt-dlp to fetch metadata when available. Results are cached
    to avoid duplicate network calls when the same URL is processed
    for transcription later.

    Args:
        url: URL to extract metadata from

    Returns:
        URLMetadata with extracted information
    """
    from inkwell.audio.downloader import AudioDownloader, get_cached_info
    from inkwell.utils.errors import APIError

    # Pre-extract what we can from the URL itself
    video_id = extract_youtube_id(url) or extract_url_slug(url)
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    # Check cache first to avoid duplicate yt-dlp calls
    cached = get_cached_info(url)
    if cached:
        logger.debug(f"Using cached metadata for {url}")
        return URLMetadata(
            title=cached.get("title"),
            video_id=cached.get("id", video_id),
            domain=domain,
            duration_seconds=cached.get("duration"),
        )

    try:
        # Use yt-dlp to get full metadata (will be cached for later use)
        downloader = AudioDownloader()
        info = await downloader.get_info(url)

        title = info.get("title")
        duration = info.get("duration")

        # Prefer yt-dlp's video ID if available
        if info.get("id"):
            video_id = info["id"]

        return URLMetadata(
            title=title,
            video_id=video_id,
            domain=domain,
            duration_seconds=duration,
        )

    except APIError as e:
        # yt-dlp extraction failed (network error, unsupported URL, etc.)
        logger.debug(f"Could not extract metadata from {url}: {e}")
        return URLMetadata(
            title=None,
            video_id=video_id,
            domain=domain,
            duration_seconds=None,
        )


def get_episode_title_from_metadata(metadata: URLMetadata, url: str) -> str:
    """Get best episode title from metadata.

    Args:
        metadata: Extracted URL metadata
        url: Original URL (for fallback)

    Returns:
        Best available title
    """
    if metadata.title:
        return metadata.title

    return create_fallback_title(url)
