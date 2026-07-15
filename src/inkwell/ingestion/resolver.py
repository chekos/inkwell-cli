"""Conservative input classification for CLI ingestion.

This module owns only source classification and minimal path checks. The CLI
uses the resulting `ContentSource` to route saved feeds, URLs, local media,
local text, and stdin into the appropriate pipeline path. More expensive work
such as feed fetching, file reading, PDF parsing, article cleanup, local OCR,
transcription, and extraction stays outside the resolver. Dedicated video slide
routes remain separate follow-up ingestion work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from inkwell.config.manager import slugify_feed_name


class ContentSourceKind(str, Enum):
    """Kinds of raw input Inkwell can recognize before processing."""

    SAVED_FEED = "saved_feed"
    URL = "url"
    LOCAL_FILE = "local_file"
    STDIN = "stdin"
    DIRECT_MEDIA = "direct_media"
    YOUTUBE = "youtube"
    ARTICLE = "article"
    PDF = "pdf"
    IMAGE = "image"
    UNKNOWN_URL = "unknown_url"


@dataclass(frozen=True)
class ContentSource:
    """Classified user input.

    `value` is the normalized input to pass downstream when the source kind is
    already processable by the existing pipeline. For saved feeds, it remains
    the feed reference supplied by the user so `ConfigManager.get_feed()` can
    preserve its display-name and fuzzy matching behavior.
    """

    raw_input: str
    kind: ContentSourceKind
    value: str
    url: str | None = None
    path: Path | None = None
    feed_name: str | None = None
    is_existing_feed: bool = False

    @property
    def is_url(self) -> bool:
        """Return True for URL inputs currently accepted by the fetch pipeline."""
        return self.kind in {
            ContentSourceKind.URL,
            ContentSourceKind.DIRECT_MEDIA,
            ContentSourceKind.YOUTUBE,
            ContentSourceKind.ARTICLE,
        }


class InputResolver:
    """Classify raw CLI input into a conservative `ContentSource`.

    The resolver may receive known saved feeds to identify a feed reference, but
    callers can omit them to avoid reading feed config before direct URL work.
    """

    _MEDIA_EXTENSIONS = {
        ".aac",
        ".aif",
        ".aiff",
        ".avi",
        ".flac",
        ".m4a",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".oga",
        ".ogg",
        ".opus",
        ".wav",
        ".webm",
    }
    _YOUTUBE_HOSTS = {"youtu.be", "youtube.com", "www.youtube.com", "m.youtube.com"}
    _SUPPORTED_URL_SCHEMES = {"http", "https"}

    def __init__(self, saved_feeds: dict[str, Any] | None = None) -> None:
        """Initialize the resolver.

        Args:
            saved_feeds: Optional mapping of canonical feed names to feed configs.
                Values may expose a `display_name` attribute.
        """
        self._saved_feeds = saved_feeds or {}

    def resolve(self, raw_input: str) -> ContentSource:
        """Classify raw user input without performing I/O beyond path checks."""
        value = raw_input.strip()

        if value == "-":
            return ContentSource(
                raw_input=raw_input,
                kind=ContentSourceKind.STDIN,
                value=value,
            )

        feed_name = self._resolve_saved_feed_name(value)
        if feed_name is not None:
            return ContentSource(
                raw_input=raw_input,
                kind=ContentSourceKind.SAVED_FEED,
                value=value,
                feed_name=feed_name,
                is_existing_feed=True,
            )

        local_path = Path(value).expanduser()
        if local_path.is_file():
            return ContentSource(
                raw_input=raw_input,
                kind=ContentSourceKind.LOCAL_FILE,
                value=str(local_path),
                path=local_path,
            )

        normalized_url = self._normalize_scheme_less_url(value)
        parsed = urlparse(normalized_url)

        if parsed.scheme:
            if parsed.scheme not in self._SUPPORTED_URL_SCHEMES or not parsed.netloc:
                return ContentSource(
                    raw_input=raw_input,
                    kind=ContentSourceKind.UNKNOWN_URL,
                    value=normalized_url,
                    url=normalized_url,
                )

            kind = self._classify_supported_url(parsed.netloc, parsed.path)
            return ContentSource(
                raw_input=raw_input,
                kind=kind,
                value=normalized_url,
                url=normalized_url,
            )

        # Preserve existing fetch behavior: non-URL tokens are feed references.
        return ContentSource(
            raw_input=raw_input,
            kind=ContentSourceKind.SAVED_FEED,
            value=value,
            feed_name=value,
            is_existing_feed=False,
        )

    def _resolve_saved_feed_name(self, value: str) -> str | None:
        """Return canonical feed name when the input matches known feeds."""
        if value in self._saved_feeds:
            return value

        normalized = slugify_feed_name(value)
        if normalized in self._saved_feeds:
            return normalized

        for feed_name, feed_config in self._saved_feeds.items():
            display_name = getattr(feed_config, "display_name", None)
            if not display_name:
                continue
            if value.casefold() == display_name.casefold():
                return feed_name
            if normalized and normalized == slugify_feed_name(display_name):
                return feed_name

        return None

    def _normalize_scheme_less_url(self, value: str) -> str:
        """Mirror fetch's historic `example.com/path` URL normalization."""
        if urlparse(value).scheme:
            return value
        if "." in value and "/" in value:
            return f"https://{value}"
        return value

    def _classify_supported_url(self, host: str, path: str) -> ContentSourceKind:
        """Classify a normalized HTTP(S) URL."""
        normalized_host = host.lower()
        if normalized_host in self._YOUTUBE_HOSTS:
            return ContentSourceKind.YOUTUBE

        suffix = Path(path.lower()).suffix
        if suffix in self._MEDIA_EXTENSIONS:
            return ContentSourceKind.DIRECT_MEDIA

        return ContentSourceKind.URL
