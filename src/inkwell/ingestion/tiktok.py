"""Public TikTok page and caption ingestion.

The adapter deliberately returns only stable provenance. Caption CDN URLs are
used in memory and are never included in results, logs, or raised errors.
"""

from __future__ import annotations

import html as html_module
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from inkwell.transcription.models import TranscriptSegment
from inkwell.utils.errors import SecurityError, ValidationError

_TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com"}
_TIKTOK_CAPTION_HOST_SUFFIXES = (".tiktok.com", ".tiktokcdn.com", ".tiktokcdn-us.com")
_VIDEO_PATH = re.compile(r"^/@(?P<creator>[^/]+)/video/(?P<video_id>\d+)")
_CREATOR = re.compile(r"^[A-Za-z0-9._]+$")
_TIMING = re.compile(
    r"^(?P<start>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})(?:\s+.*)?$"
)
_TAG = re.compile(r"<[^>]+>")
_MAX_PAGE_BYTES = 5 * 1024 * 1024
_MAX_CAPTION_BYTES = 5 * 1024 * 1024
_MAX_CAPTION_REDIRECTS = 3
_MAX_PAGE_REDIRECTS = 5


class _UniversalDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("id") == "__UNIVERSAL_DATA_FOR_REHYDRATION__":
            self._capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture:
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self.parts.append(data)


@dataclass(frozen=True)
class TikTokSource:
    supplied_url: str
    canonical_url: str
    creator: str | None = None
    video_id: str | None = None
    caption: str | None = None
    duration_seconds: float | None = None
    transcript_text: str | None = None
    transcript_segments: tuple[TranscriptSegment, ...] = ()
    transcript_language: str | None = None
    transcript_auto_generated: bool | None = None

    @property
    def title(self) -> str:
        caption = (self.caption or "").strip()
        return caption[:100] if caption else f"TikTok {self.video_id or 'video'}"

    @property
    def podcast_name(self) -> str:
        return f"TikTok @{self.creator}" if self.creator else "TikTok"

    def provenance(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "platform": "tiktok",
            "supplied_url": _stable_tiktok_url(self.supplied_url),
            "canonical_url": self.canonical_url,
            "transcript_method": "embedded_webvtt" if self.transcript_text else "media_fallback",
        }
        optional = {
            "creator": self.creator,
            "video_id": self.video_id,
            "caption": self.caption,
            "duration_seconds": self.duration_seconds,
            "transcript_language": self.transcript_language,
            "transcript_auto_generated": self.transcript_auto_generated,
        }
        result.update({key: value for key, value in optional.items() if value is not None})
        return result


def is_tiktok_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.username is None
        and parsed.password is None
        and (parsed.hostname or "").lower() in _TIKTOK_HOSTS
    )


def _stable_tiktok_url(url: str) -> str:
    """Keep only stable public TikTok URL components for durable metadata."""
    parsed = urlparse(url)
    host = (parsed.hostname or "www.tiktok.com").lower()
    if host not in _TIKTOK_HOSTS:
        host = "www.tiktok.com"
    return urlunparse(("https", host, parsed.path or "/", "", "", ""))


def _is_safe_caption_url(url: str) -> bool:
    """Restrict embedded caption fetches to HTTPS TikTok-owned CDN hosts."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and any(host.endswith(suffix) for suffix in _TIKTOK_CAPTION_HOST_SUFFIXES)
    )


def _walk(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _find_item(data: Any) -> dict[str, Any]:
    for value in _walk(data):
        if isinstance(value, dict) and isinstance(value.get("itemStruct"), dict):
            return cast(dict[str, Any], value["itemStruct"])
    for value in _walk(data):
        if (
            isinstance(value, dict)
            and value.get("id")
            and ("subtitleInfos" in value or "captionInfos" in value or "video" in value)
        ):
            return value
    return {}


def _caption_tracks(item: dict[str, Any]) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    for value in _walk(item):
        if not isinstance(value, dict):
            continue
        for key in ("subtitleInfos", "captionInfos"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                tracks.extend(track for track in candidate if isinstance(track, dict))
    return tracks


def _track_url(track: dict[str, Any]) -> str | None:
    for key in ("Url", "url", "URL"):
        value = track.get(key)
        if isinstance(value, str) and _is_safe_caption_url(value):
            return value
    return None


def _bounded_response_text(response: httpx.Response, *, limit: int, label: str) -> str:
    """Read a streamed response without buffering more than the allowed bytes."""
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > limit:
                raise ValidationError(f"TikTok {label} exceeded the safe size limit")
        except ValueError:
            pass
    content = bytearray()
    for chunk in response.iter_bytes():
        if len(content) + len(chunk) > limit:
            raise ValidationError(f"TikTok {label} exceeded the safe size limit")
        content.extend(chunk)
    return bytes(content).decode(response.encoding or "utf-8", errors="replace")


def _fetch_page(http: httpx.Client, url: str) -> tuple[str, str]:
    """Fetch a bounded TikTok page while validating every redirect hop."""
    current_url = _stable_tiktok_url(url)
    for _ in range(_MAX_PAGE_REDIRECTS + 1):
        if not is_tiktok_url(current_url):
            raise ValidationError("TikTok page location was rejected")
        with http.stream("GET", current_url, follow_redirects=False) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValidationError("TikTok page redirect was invalid")
                next_url = urljoin(current_url, location)
                if not is_tiktok_url(next_url):
                    raise SecurityError("TikTok page redirect location was rejected")
                current_url = _stable_tiktok_url(next_url)
                continue
            response.raise_for_status()
            return current_url, _bounded_response_text(
                response, limit=_MAX_PAGE_BYTES, label="page"
            )
    raise ValidationError("TikTok page redirected too many times")


def _fetch_caption(http: httpx.Client, url: str) -> str:
    """Fetch a bounded caption while validating every redirect destination."""
    current_url = url
    for _ in range(_MAX_CAPTION_REDIRECTS + 1):
        if not _is_safe_caption_url(current_url):
            raise ValidationError("TikTok caption location was rejected")
        with http.stream("GET", current_url, follow_redirects=False) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValidationError("TikTok caption redirect was invalid")
                current_url = urljoin(current_url, location)
                continue
            response.raise_for_status()
            return _bounded_response_text(response, limit=_MAX_CAPTION_BYTES, label="caption track")
    raise ValidationError("TikTok caption track redirected too many times")


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _language(track: dict[str, Any]) -> str | None:
    for key in (
        "LanguageCodeName",
        "languageCodeName",
        "LanguageCode",
        "languageCode",
        "language",
    ):
        value = track.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    return total


def parse_webvtt(payload: str) -> list[TranscriptSegment]:
    """Parse WebVTT cues, removing syntax and rolling-caption duplication."""
    lines = payload.replace("\ufeff", "").replace("\r\n", "\n").split("\n")
    segments: list[TranscriptSegment] = []
    index = 0
    previous_words: list[str] = []
    while index < len(lines):
        timing_match = _TIMING.match(lines[index].strip())
        if not timing_match:
            index += 1
            continue
        start = _seconds(timing_match.group("start"))
        end = _seconds(timing_match.group("end"))
        index += 1
        cue_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            cue_lines.append(lines[index].strip())
            index += 1
        text = html_module.unescape(_TAG.sub("", " ".join(cue_lines)))
        words = re.sub(r"\s+", " ", text).strip().split()
        if not words:
            continue
        overlap = 0
        max_overlap = min(len(previous_words), len(words))
        for size in range(max_overlap, 0, -1):
            if previous_words[-size:] == words[:size]:
                overlap = size
                break
        new_words = words[overlap:]
        previous_words = words
        if not new_words:
            continue
        segments.append(
            TranscriptSegment(text=" ".join(new_words), start=start, duration=max(0.0, end - start))
        )
    if not segments:
        raise ValidationError(
            "TikTok captions were empty or malformed",
            suggestion="Inkwell will try the media transcription fallback when available.",
        )
    return segments


def _canonical_url(response_url: str, item: dict[str, Any]) -> tuple[str, str | None, str | None]:
    parsed = urlparse(response_url)
    match = _VIDEO_PATH.match(parsed.path)
    creator = match.group("creator") if match else None
    video_id = match.group("video_id") if match else None
    author = item.get("author")
    if isinstance(author, dict):
        remote_creator = author.get("uniqueId")
        if isinstance(remote_creator, str) and _CREATOR.fullmatch(remote_creator):
            creator = remote_creator
    remote_video_id = item.get("id")
    if isinstance(remote_video_id, (str, int)) and str(remote_video_id).isdigit():
        video_id = str(remote_video_id)
    if creator is not None and not _CREATOR.fullmatch(creator):
        creator = None
    if creator and video_id:
        return f"https://www.tiktok.com/@{creator}/video/{video_id}", creator, video_id
    return _stable_tiktok_url(response_url), creator, video_id


def _format_timestamp(seconds: float) -> str:
    rounded = max(0, int(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_transcript(segments: list[TranscriptSegment]) -> str:
    return "\n".join(f"[{_format_timestamp(segment.start)}] {segment.text}" for segment in segments)


def resolve_tiktok_source(url: str, *, client: httpx.Client | None = None) -> TikTokSource:
    """Resolve public TikTok metadata and use an embedded caption track if viable."""
    if not is_tiktok_url(url):
        raise ValidationError("Not a TikTok URL")
    owns_client = client is None
    http = client or httpx.Client(
        follow_redirects=False,
        timeout=20.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Inkwell/1.0)"},
    )
    try:
        try:
            resolved_url, page_text = _fetch_page(http, url)
        except (httpx.HTTPError, ValidationError):
            # yt-dlp can still recover some URLs that reject ordinary page requests.
            # Return only stable URL provenance and let the normal media/transcription
            # path produce the final actionable error if that fallback is also blocked.
            return TikTokSource(
                supplied_url=url,
                canonical_url=_stable_tiktok_url(url),
            )

        parser = _UniversalDataParser()
        parser.feed(page_text)
        try:
            data = json.loads("".join(parser.parts)) if parser.parts else {}
        except json.JSONDecodeError:
            data = {}
        item = _find_item(data)
        canonical_url, creator, video_id = _canonical_url(resolved_url, item)
        video_value = item.get("video")
        video: dict[str, Any] = video_value if isinstance(video_value, dict) else {}
        duration = video.get("duration") or item.get("duration")
        try:
            duration_seconds = float(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration_seconds = None

        for track in _caption_tracks(item):
            caption_url = _track_url(track)
            if caption_url is None:
                continue
            try:
                segments = parse_webvtt(_fetch_caption(http, caption_url))
            except (httpx.HTTPError, ValidationError, ValueError):
                continue
            language = _language(track)
            auto_value = track.get(
                "isAutoGenerated",
                track.get("autoGenerated", track.get("isAutoGen")),
            )
            auto_generated = _optional_bool(auto_value)
            if auto_generated is None and str(track.get("Source", "")).upper() == "ASR":
                auto_generated = True
            return TikTokSource(
                supplied_url=url,
                canonical_url=canonical_url,
                creator=creator,
                video_id=video_id,
                caption=item.get("desc") if isinstance(item.get("desc"), str) else None,
                duration_seconds=duration_seconds,
                transcript_text=_format_transcript(segments),
                transcript_segments=tuple(segments),
                transcript_language=language,
                transcript_auto_generated=auto_generated,
            )

        return TikTokSource(
            supplied_url=url,
            canonical_url=canonical_url,
            creator=creator,
            video_id=video_id,
            caption=item.get("desc") if isinstance(item.get("desc"), str) else None,
            duration_seconds=duration_seconds,
        )
    finally:
        if owns_client:
            http.close()
