"""Demo URL classifier and validator.

Accepts only the two URL shapes the public try-it demo supports:

- Public YouTube **video** URLs (watch / shorts / live / youtu.be).
- Public RSS feeds reachable over plain http(s).

Anything else — playlists, channel landing pages, /@handle URLs without a
specific video, private feeds, file://, ftp://, raw IP literals,
``localhost``, RFC1918/loopback/link-local hosts — is rejected before
anything reaches the inkwell pipeline.

This is intentionally a pure function: no network calls. Network
verification (HEAD on the RSS, ``yt-dlp`` metadata for YouTube duration)
happens later in the resolver layer where it can be cached and rate
limited.
"""

from __future__ import annotations

import enum
import ipaddress
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from inkwell.feeds.youtube_resolver import YOUTUBE_HOSTS

_ALLOWED_SCHEMES = frozenset({"http", "https"})


class UrlKind(str, enum.Enum):
    """Kind of source URL accepted by the demo."""

    YOUTUBE_VIDEO = "youtube_video"
    PUBLIC_RSS = "public_rss"


class DemoUrlError(ValueError):
    """Raised when a submitted URL is not eligible for the demo.

    The ``user_message`` field is safe to show in the response body; the
    underlying ``ValueError`` message is what we log internally.
    """

    def __init__(self, user_message: str, *, reason: str | None = None):
        super().__init__(reason or user_message)
        self.user_message = user_message
        self.reason = reason or user_message


@dataclass(frozen=True)
class ClassifiedUrl:
    """A URL that has passed demo eligibility checks."""

    kind: UrlKind
    normalized_url: str


def classify_demo_url(raw_url: str) -> ClassifiedUrl:
    """Validate a user-submitted URL and classify it for the demo pipeline.

    Args:
        raw_url: URL pasted by the user.

    Returns:
        :class:`ClassifiedUrl` describing what the URL points at.

    Raises:
        DemoUrlError: With a user-safe message when the URL is unsupported.
    """
    if not isinstance(raw_url, str):
        raise DemoUrlError("Paste a URL.", reason="non_string_input")

    url = raw_url.strip()
    if not url:
        raise DemoUrlError("Paste a URL.", reason="empty_input")

    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise DemoUrlError("That doesn't look like a URL.", reason="urlparse_failed") from exc

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise DemoUrlError(
            "Only http:// or https:// URLs are supported.",
            reason=f"scheme_not_allowed:{parsed.scheme}",
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise DemoUrlError("URL is missing a host.", reason="missing_host")

    _reject_private_or_local_host(host)

    if host in YOUTUBE_HOSTS:
        return _classify_youtube(parsed, url)

    return ClassifiedUrl(kind=UrlKind.PUBLIC_RSS, normalized_url=url)


def _classify_youtube(parsed, original_url: str) -> ClassifiedUrl:  # type: ignore[no-untyped-def]
    """Classify a YouTube URL or reject it as out-of-scope for the demo.

    The demo only accepts URLs that name a *single specific video*. We
    explicitly reject playlist URLs, channel landing pages, /@handle URLs
    without a video selected, and the YouTube homepage.
    """
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    query = parse_qs(parsed.query)

    if "list" in query or path == "/playlist" or path.startswith("/playlist/"):
        raise DemoUrlError(
            "Playlist URLs aren't supported in the demo — paste a single video URL.",
            reason="youtube_playlist",
        )

    # youtu.be/<video_id>
    if host == "youtu.be":
        video_id = path.lstrip("/").split("/", 1)[0]
        if not video_id:
            raise DemoUrlError(
                "youtu.be link is missing the video id.",
                reason="youtube_shortlink_no_video",
            )
        return ClassifiedUrl(kind=UrlKind.YOUTUBE_VIDEO, normalized_url=original_url)

    # Standard /watch?v=<video_id>
    if path == "/watch":
        video_ids = query.get("v", [])
        if not any(video_ids):
            raise DemoUrlError(
                "YouTube watch URL is missing the video id.",
                reason="youtube_watch_no_video",
            )
        return ClassifiedUrl(kind=UrlKind.YOUTUBE_VIDEO, normalized_url=original_url)

    # /shorts/<id>, /live/<id>, /embed/<id>, /v/<id>: all single-video shapes
    for prefix in ("/shorts/", "/live/", "/embed/", "/v/"):
        if path.startswith(prefix):
            tail = path[len(prefix) :].split("/", 1)[0]
            if not tail:
                raise DemoUrlError(
                    "YouTube URL is missing the video id.",
                    reason="youtube_path_no_video",
                )
            return ClassifiedUrl(kind=UrlKind.YOUTUBE_VIDEO, normalized_url=original_url)

    # Channel pages, @handles, homepage — out of scope for the demo.
    raise DemoUrlError(
        "Paste a YouTube video URL (watch, shorts, or youtu.be).",
        reason=f"youtube_non_video:{path or '/'}",
    )


def _reject_private_or_local_host(host: str) -> None:
    """Reject hostnames that point at private or local-only infrastructure.

    The demo backend will dereference the URL itself, so we have to refuse
    hosts that resolve into the internal network or the loopback range.
    """
    if host in {"localhost", "ip6-localhost", "ip6-loopback"}:
        raise DemoUrlError(
            "URL points at a local address.",
            reason=f"local_host:{host}",
        )

    # Hosts surrounded by [] (IPv6 literal in a URL) come back without
    # brackets after urlparse, so the parsing below is uniform.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if host.endswith(".local") or host.endswith(".internal"):
            raise DemoUrlError(
                "URL points at an internal address.",
                reason=f"internal_tld:{host}",
            ) from None
        return

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise DemoUrlError(
            "URL points at a private or reserved address.",
            reason=f"private_ip:{host}",
        )
