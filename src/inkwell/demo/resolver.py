"""Resolve a demo URL into a pipeline-ready source and reject overlong audio.

The classifier already validated that the pasted URL is structurally a
public RSS feed or a YouTube video URL. The resolver does the next layer
of work *before* the inkwell pipeline spends any LLM/transcription
budget:

- For YouTube videos: pull duration from ``yt-dlp`` metadata (no
  download) and reject anything over ``demo_config.max_duration_seconds``.
- For RSS feeds: fetch the feed via :func:`_fetch_feed_safely` (manual
  redirect loop that revalidates each hop with
  :func:`assert_demo_safe_url`), pick the latest episode via
  :class:`RSSParser`, and reject if the iTunes duration is missing or
  over the cap. The audio enclosure URL is also revalidated before
  handoff so a public feed can't list a localhost MP3.

Episodes longer than the cap are rejected here; metadata that lies
about duration (claims short, is actually long) is caught by the
service's post-transcription backstop in :mod:`inkwell.demo.service`.

The returned :class:`ResolvedDemoSource` is what
:func:`inkwell.demo.service.process_demo_job` feeds to
:class:`PipelineOrchestrator`.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any

import feedparser
import httpx
import pydantic
from yt_dlp import YoutubeDL  # type: ignore[import-untyped]
from yt_dlp.utils import DownloadError, ExtractorError  # type: ignore[import-untyped]

from inkwell.demo.classifier import (
    ClassifiedUrl,
    DemoUrlError,
    UrlKind,
    assert_demo_safe_url,
    assert_resolved_host_is_public,
)
from inkwell.demo.config import DemoConfig
from inkwell.feeds.parser import RSSParser
from inkwell.utils.errors import NotFoundError, ValidationError

_YTDLP_SOCKET_TIMEOUT_SECONDS = 30

_DEMO_RSS_PODCAST_FALLBACK = "Demo episode"

# RSS fetch hardening (codex P1 carry-over from m1):
# RSSParser.fetch_feed uses ``follow_redirects=True``, which would let a
# public URL 302 to localhost / RFC1918 and bypass the m1 SSRF guard.
# The demo path uses ``_fetch_feed_safely`` instead, which walks
# redirects manually and revalidates each ``Location`` target via
# ``assert_demo_safe_url``.
_RSS_FETCH_TIMEOUT_SECONDS = 30
_RSS_MAX_REDIRECT_HOPS = 5


@dataclass(frozen=True)
class ResolvedDemoSource:
    """A demo URL that has cleared duration validation and is ready to run.

    Attributes:
        kind: Kind of source that was resolved.
        pipeline_url: URL handed to :class:`PipelineOrchestrator`. For RSS
            this is the audio enclosure URL of the latest episode; for
            YouTube it is the original video URL (the transcription
            manager handles YouTube URLs directly).
        duration_seconds: Episode/video duration in seconds. Always a
            concrete int — episodes with unknown duration are rejected
            upstream.
        podcast_name: Display name used for output naming and the
            frontend payload.
        episode_title: Episode/video title used for output naming and the
            frontend payload.
    """

    kind: UrlKind
    pipeline_url: str
    duration_seconds: int
    podcast_name: str
    episode_title: str


async def resolve_demo_source(
    classified: ClassifiedUrl,
    *,
    demo_config: DemoConfig,
) -> ResolvedDemoSource:
    """Resolve a classified URL and reject anything over the duration cap.

    Args:
        classified: Output of :func:`classify_demo_url`.
        demo_config: Demo runtime configuration; ``max_duration_seconds``
            is the hard cap.

    Returns:
        A :class:`ResolvedDemoSource` ready to feed into the pipeline.

    Raises:
        DemoUrlError: If the URL can't be resolved, no episode is
            available, duration is unknown, or duration exceeds the cap.
            The ``user_message`` field is safe to surface verbatim.
    """
    if classified.kind is UrlKind.YOUTUBE_VIDEO:
        return await _resolve_youtube_video(classified.normalized_url, demo_config)
    if classified.kind is UrlKind.PUBLIC_RSS:
        return await _resolve_public_rss(classified.normalized_url, demo_config)
    # Defensive — UrlKind is closed; reachable only if a new variant is
    # added without updating this function.
    raise DemoUrlError(
        "We can't run that kind of URL in the demo.",
        reason=f"unknown_url_kind:{classified.kind!r}",
    )


async def _resolve_youtube_video(
    url: str,
    demo_config: DemoConfig,
) -> ResolvedDemoSource:
    info = await asyncio.to_thread(_fetch_youtube_video_info, url)
    duration_seconds = _coerce_duration(info)
    if duration_seconds is None:
        raise DemoUrlError(
            "We couldn't read this video's duration. Try another video.",
            reason="youtube_missing_duration",
        )
    _enforce_duration_cap(duration_seconds, demo_config)

    title = _coerce_str(info.get("title")) or "YouTube video"
    podcast_name = (
        _coerce_str(info.get("channel")) or _coerce_str(info.get("uploader")) or "YouTube"
    )

    return ResolvedDemoSource(
        kind=UrlKind.YOUTUBE_VIDEO,
        pipeline_url=url,
        duration_seconds=duration_seconds,
        podcast_name=podcast_name,
        episode_title=title,
    )


async def _resolve_public_rss(
    url: str,
    demo_config: DemoConfig,
) -> ResolvedDemoSource:
    feed = await _fetch_feed_safely(url)

    podcast_name = _coerce_str(getattr(feed.feed, "title", None)) or _DEMO_RSS_PODCAST_FALLBACK

    try:
        episode = RSSParser().get_latest_episode(feed, podcast_name)
    except (ValidationError, NotFoundError, pydantic.ValidationError) as exc:
        # ``pydantic.ValidationError`` covers feed entries that fail the
        # ``Episode`` model itself — e.g., an enclosure URL that fails
        # ``HttpUrl`` validation. Without it those land as 500s instead of
        # a user-safe DemoUrlError.
        raise DemoUrlError(
            "That feed doesn't have a usable latest episode.",
            reason=f"rss_no_latest_episode:{type(exc).__name__}",
        ) from exc

    if episode.duration_seconds is None:
        raise DemoUrlError(
            "The latest episode doesn't list a duration. Try a different feed.",
            reason="rss_missing_duration",
        )

    _enforce_duration_cap(episode.duration_seconds, demo_config)

    enclosure_url = str(episode.url)
    enclosure_host = httpx.URL(enclosure_url).host
    try:
        # Two layers, same as the redirect guard: assert_demo_safe_url
        # validates the host literal; assert_resolved_host_is_public
        # resolves it and rejects RFC1918 / loopback / link-local /
        # RFC6598 / etc. A feed on a public domain can still publish an
        # enclosure whose host *resolves* to private space (codex P1
        # follow-up), so both checks are needed here too.
        assert_demo_safe_url(enclosure_url)
        if enclosure_host:
            await asyncio.to_thread(assert_resolved_host_is_public, enclosure_host)
    except DemoUrlError as exc:
        # Feed listed an enclosure URL pointing at a private host.
        # Refuse the whole job — we can't trust this feed to hand us a
        # download target that's safe for the worker to dereference.
        raise DemoUrlError(
            "The latest episode's audio URL points at a private address.",
            reason=f"rss_unsafe_enclosure:{exc.reason}",
        ) from exc

    return ResolvedDemoSource(
        kind=UrlKind.PUBLIC_RSS,
        pipeline_url=enclosure_url,
        duration_seconds=episode.duration_seconds,
        podcast_name=episode.podcast_name,
        episode_title=episode.title,
    )


async def _fetch_feed_safely(url: str) -> feedparser.FeedParserDict:
    """Fetch RSS contents while revalidating every hop's host.

    This replaces :meth:`RSSParser.fetch_feed` for the demo path. The
    upstream method passes ``follow_redirects=True`` to ``httpx``, which
    would let a public URL 30x to localhost / RFC1918 and bypass the
    classifier's host policy. Here we set ``follow_redirects=False`` and
    walk up to :data:`_RSS_MAX_REDIRECT_HOPS` redirect hops manually.

    Every iteration revalidates the target before issuing the GET:

    - :func:`assert_demo_safe_url` (host-literal policy)
    - :func:`assert_resolved_host_is_public` (DNS resolution +
      ``not ip.is_global``)

    The initial URL is included on purpose. The classifier already ran
    these same checks at submission time, but classification and worker
    execution are decoupled in the demo (m1 = synchronous classify, m5 =
    Cloud Tasks delivery) — a DNS-rebinding attacker can submit a
    hostname that resolves public at classify time and flips to
    RFC1918/loopback before the worker fetches. Re-running the checks
    here closes that TOCTOU window for every hop, including hop 0.

    Args:
        url: Caller-supplied RSS URL. Already validated by
            :func:`classify_demo_url`, but we revalidate the chain.

    Returns:
        Parsed feed dictionary from :func:`feedparser.parse`.

    Raises:
        DemoUrlError: With a user-safe message and structured ``reason``
            when the fetch fails, the host is unsafe (initial or
            redirected), or the hop budget is exhausted.
    """
    current = url
    async with httpx.AsyncClient(
        timeout=_RSS_FETCH_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        for hop in range(_RSS_MAX_REDIRECT_HOPS + 1):
            await _assert_safe_to_fetch(current, is_redirect_hop=hop > 0)

            response = await _safe_get(client, current)

            if response.status_code == 401:
                raise DemoUrlError(
                    "That feed is private. The demo only supports public RSS feeds.",
                    reason="rss_authentication_required",
                )

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise DemoUrlError(
                        "We couldn't follow the RSS feed redirect.",
                        reason="rss_redirect_no_location",
                    )
                # Resolve the next target relative to the current URL and
                # let the next iteration's top-of-loop guard validate it.
                current = str(httpx.URL(current).join(location))
                continue

            if response.status_code >= 400:
                raise DemoUrlError(
                    "We couldn't read that RSS feed. Check the URL and try again.",
                    reason=f"rss_http_status:{response.status_code}",
                )

            feed = feedparser.parse(response.content)
            if not feed.entries:
                raise DemoUrlError(
                    "That feed doesn't have any episodes.",
                    reason="rss_no_entries",
                )
            return feed

    raise DemoUrlError(
        "Too many redirects while reading the RSS feed.",
        reason="rss_too_many_redirects",
    )


async def _assert_safe_to_fetch(url: str, *, is_redirect_hop: bool) -> None:
    """Run the host-literal + DNS checks before any GET.

    Wraps the underlying ``DemoUrlError`` so log filters can distinguish
    a redirect-driven rejection (``rss_redirect_to_unsafe_host:*``) from
    a TOCTOU-driven rejection on the initial URL
    (``rss_unsafe_host:*``).
    """
    host = httpx.URL(url).host
    try:
        assert_demo_safe_url(url)
        if host:
            await asyncio.to_thread(assert_resolved_host_is_public, host)
    except DemoUrlError as exc:
        if is_redirect_hop:
            raise DemoUrlError(
                "That feed redirects to a private address.",
                reason=f"rss_redirect_to_unsafe_host:{exc.reason}",
            ) from exc
        raise DemoUrlError(
            "That feed's host can't be safely fetched.",
            reason=f"rss_unsafe_host:{exc.reason}",
        ) from exc


async def _safe_get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """Single httpx GET with demo-friendly error mapping."""
    try:
        return await client.get(url)
    except httpx.TimeoutException as exc:
        raise DemoUrlError(
            "We couldn't reach that RSS feed in time.",
            reason="rss_fetch_timeout",
        ) from exc
    except httpx.RequestError as exc:
        raise DemoUrlError(
            "We couldn't read that RSS feed. Check the URL and try again.",
            reason=f"rss_fetch_network_error:{type(exc).__name__}",
        ) from exc


def _fetch_youtube_video_info(url: str) -> dict[str, Any]:
    """Pull a YouTube video's metadata via yt-dlp without downloading audio."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": _YTDLP_SOCKET_TIMEOUT_SECONDS,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
    except (DownloadError, ExtractorError, OSError) as exc:
        raise DemoUrlError(
            "We couldn't reach that video. It may be private, region-blocked, or removed.",
            reason=f"yt_dlp_extract_failed:{type(exc).__name__}",
        ) from exc

    if not isinstance(info, dict):
        raise DemoUrlError(
            "We couldn't read that video's metadata.",
            reason="yt_dlp_unexpected_payload",
        )
    return info


def _coerce_duration(info: dict[str, Any]) -> int | None:
    """Normalize yt-dlp's duration field into integer seconds.

    yt-dlp returns ``duration`` as a numeric (int or float) when known.
    Some extractors only set ``duration_string`` (``"H:MM:SS"``); we
    parse that as a fallback. Returns ``None`` if neither is usable.

    Float values are rounded up via :func:`math.ceil` so a video that
    is fractionally over the cap (``1800.9`` against a 1800s cap) is
    rejected at the resolver — truncation would let it through and
    defer rejection to a post-transcription backstop, after the
    pipeline has already spent budget.
    """
    raw = info.get("duration")
    if isinstance(raw, (int, float)) and raw > 0:
        return math.ceil(raw)

    duration_string = info.get("duration_string")
    if isinstance(duration_string, str) and duration_string.strip():
        seconds = _parse_duration_string(duration_string)
        if seconds is not None and seconds > 0:
            return seconds

    return None


def _parse_duration_string(value: str) -> int | None:
    """Parse ``H:MM:SS`` / ``M:SS`` / ``SSSS`` into seconds, else None."""
    text = value.strip()
    if not text:
        return None
    if ":" in text:
        try:
            parts = [int(part) for part in text.split(":")]
        except ValueError:
            return None
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return hours * 3600 + minutes * 60 + seconds
        if len(parts) == 2:
            minutes, seconds = parts
            return minutes * 60 + seconds
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _enforce_duration_cap(duration_seconds: int, demo_config: DemoConfig) -> None:
    if duration_seconds > demo_config.max_duration_seconds:
        cap_minutes = demo_config.max_duration_seconds // 60
        raise DemoUrlError(
            f"Episodes over {cap_minutes} minutes aren't supported in the demo.",
            reason=(f"duration_over_cap:{duration_seconds}>{demo_config.max_duration_seconds}"),
        )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


__all__ = [
    "ResolvedDemoSource",
    "resolve_demo_source",
]
