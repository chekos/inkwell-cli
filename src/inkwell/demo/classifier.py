"""Demo URL classifier and validator.

Accepts only the two URL shapes the public try-it demo supports:

- Public YouTube **video** URLs (watch / shorts / live / youtu.be).
- Public RSS feeds reachable over plain http(s).

Anything else — playlists, channel landing pages, /@handle URLs without a
specific video, private feeds, file://, ftp://, raw IP literals,
``localhost``, RFC1918/loopback/link-local hosts, and non-canonical IPv4
encodings that libc resolvers normalize back to those ranges (decimal
``2130706433``, hex ``0x7f000001``, octal ``0177.0.0.1``, short-form
``127.1``) — is rejected before anything reaches the inkwell pipeline.

URL-shape and host-literal validation is pure; the only network call
the classifier makes is a ``socket.getaddrinfo`` lookup against the
parsed host so a public-looking name whose A/AAAA records resolve to
loopback / RFC1918 / link-local space (DNS rebinding,
attacker-controlled DNS, internal split-horizon resolvers) is rejected
at submission time. Heavier verification (HEAD on the RSS, ``yt-dlp``
metadata for YouTube duration) still happens later in the resolver
layer where it can be cached and rate limited.

**Redirect note for the resolver/fetcher (m2):** ``classify_demo_url``
only validates the URL the user pasted. Any HTTP fetch in the demo path
must either disable redirects (``follow_redirects=False``) and call
:func:`assert_demo_safe_url` on every ``Location`` hop, or use a custom
``httpx`` event hook that does the same. Otherwise a public URL can
302 to ``localhost`` / RFC1918 and bypass this guard.
"""

from __future__ import annotations

import enum
import ipaddress
import socket
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
    assert_resolved_host_is_public(host)

    if host in YOUTUBE_HOSTS:
        return _classify_youtube(parsed, url)

    return ClassifiedUrl(kind=UrlKind.PUBLIC_RSS, normalized_url=url)


def assert_resolved_host_is_public(host: str) -> None:
    """Resolve ``host`` and reject if any address is private or reserved.

    :func:`_reject_private_or_local_host` only inspects the host literal
    in the URL string. This adds the next layer: a public-looking
    hostname can still resolve to loopback / RFC1918 / link-local space
    via DNS rebinding, attacker-controlled DNS, or an internal
    split-horizon resolver. Both checks together close the SSRF surface
    for the URL the user pasted.

    No-op for IP literals — those are already covered by
    :func:`_reject_private_or_local_host`, and ``getaddrinfo`` on a
    literal would just echo it back.

    Args:
        host: Lowercased hostname extracted from the URL.

    Raises:
        DemoUrlError: When the host can't be resolved or any resolved
            address falls in a disallowed range. ``reason`` is
            ``dns_resolution_failed:<errtype>`` or
            ``resolved_private_ip:<host>-><ip>`` for logging.
    """
    try:
        ipaddress.ip_address(host)
        return
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, 0, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DemoUrlError(
            "We couldn't resolve that host.",
            reason=f"dns_resolution_failed:{type(exc).__name__}",
        ) from exc

    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _ip_is_disallowed(ip):
            raise DemoUrlError(
                "URL resolves to a private address.",
                reason=f"resolved_private_ip:{host}->{ip}",
            )


def assert_demo_safe_url(url: str) -> None:
    """Re-validate a URL's scheme and host against the demo policy.

    Use this from the resolver/fetcher (m2) on every redirect hop so a
    public URL can't 302 to ``localhost``/RFC1918 and bypass
    :func:`classify_demo_url`. The recommended pattern with ``httpx`` is
    ``follow_redirects=False`` plus a manual loop that calls this on
    each ``Location`` header.

    Note: this is a *string-only* check. The async redirect path in
    :mod:`inkwell.demo.resolver` calls
    :func:`_assert_resolved_host_is_public` alongside it (via
    ``asyncio.to_thread``) to add the DNS layer without blocking the
    event loop.

    Args:
        url: Absolute URL string to validate.

    Raises:
        DemoUrlError: With a user-safe message when the URL is
            unsupported. The ``reason`` field carries the structured
            error code for logging.
    """
    if not isinstance(url, str):
        raise DemoUrlError("Paste a URL.", reason="non_string_input")

    text = url.strip()
    if not text:
        raise DemoUrlError("Paste a URL.", reason="empty_input")

    try:
        parsed = urlparse(text)
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
    Both canonical IP literals (``127.0.0.1``, ``::1``, RFC1918) and the
    non-canonical IPv4 encodings that libc accepts (decimal ``2130706433``,
    hex ``0x7f000001``, octal ``0177.0.0.1``, short-form ``127.1``) are
    blocked — those legacy encodings are not legitimate hostnames in the
    public web and are a known SSRF bypass vector.
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
        _reject_legacy_ipv4_encoding(host)
        if host.endswith(".local") or host.endswith(".internal"):
            raise DemoUrlError(
                "URL points at an internal address.",
                reason=f"internal_tld:{host}",
            ) from None
        return

    if _ip_is_disallowed(ip):
        raise DemoUrlError(
            "URL points at a private or reserved address.",
            reason=f"private_ip:{host}",
        )


def _reject_legacy_ipv4_encoding(host: str) -> None:
    """Reject non-canonical IPv4 encodings that libc resolvers accept.

    ``ipaddress.ip_address`` only parses canonical dotted-quad IPv4. libc
    (via ``inet_aton`` / ``getaddrinfo``) additionally accepts decimal
    integer (``2130706433``), hex (``0x7f000001``), octal (``0177.0.0.1``),
    and short-form (``127.1``) representations. Real RSS / podcast hosts
    don't use those, and they're a documented SSRF bypass for filters
    that only check canonical forms — so we reject any host that
    ``inet_aton`` parses but ``ipaddress.ip_address`` doesn't.

    For defense-in-depth we also re-check the resolved canonical address
    against the private-network policy, so ``2130706433`` (== 127.0.0.1)
    surfaces a "loopback" reason rather than just a generic refusal.
    """
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return

    try:
        ip = ipaddress.ip_address(packed)
    except ValueError:
        # inet_aton accepted but ipaddress can't reverse-engineer it —
        # be conservative and refuse outright.
        raise DemoUrlError(
            "URL points at a non-canonical IP address.",
            reason=f"legacy_ipv4_encoding:{host}",
        ) from None

    if _ip_is_disallowed(ip):
        raise DemoUrlError(
            "URL points at a private or reserved address.",
            reason=f"legacy_ipv4_private:{host}->{ip}",
        )

    # Public IP, but the legacy encoding itself is the smell — refuse.
    raise DemoUrlError(
        "URL points at a non-canonical IP address.",
        reason=f"legacy_ipv4_encoding:{host}->{ip}",
    )


def _ip_is_disallowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )
