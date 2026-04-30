"""URL metadata helpers."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

_AUDIO_EXTENSIONS = (
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
    ".ogg",
    ".flac",
    ".mp4",
    ".webm",
    ".mkv",
    ".m4v",
    ".mov",
)

_GENERIC_PATH_TITLES = {
    "audio",
    "embed",
    "episode",
    "feed",
    "feeds",
    "live",
    "playlist",
    "shorts",
    "videosxml",
    "watch",
}


def derive_readable_title_from_url(url: str) -> str | None:
    """Derive a readable episode title from a URL path.

    Returns None if the URL does not contain a useful title candidate.
    """
    parsed = urlparse(url)
    if not parsed.path:
        return None

    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        return None

    candidate = unquote(segments[-1]).strip()
    if not candidate:
        return None

    lower_candidate = candidate.lower()
    for extension in _AUDIO_EXTENSIONS:
        if lower_candidate.endswith(extension):
            candidate = candidate[: -len(extension)]
            break

    cleaned = candidate.replace("-", " ").replace("_", " ").replace("+", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
    if not cleaned:
        return None

    normalized = re.sub(r"[^a-z0-9]+", "", cleaned.lower())
    if normalized in _GENERIC_PATH_TITLES:
        return None

    return cleaned
