from pathlib import Path

import httpx
import pytest

from inkwell.ingestion.tiktok import parse_webvtt, resolve_tiktok_source
from inkwell.utils.errors import SecurityError, ValidationError

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _client(page: str, captions: str, *, caption_status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.tiktok.com" and request.url.path.startswith("/t/"):
            return httpx.Response(
                302,
                headers={
                    "location": "https://www.tiktok.com/@amber.figlow/video/7673547653170351373"
                },
            )
        if request.url.host == "www.tiktok.com":
            return httpx.Response(200, text=page)
        return httpx.Response(caption_status, text=captions)

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_parse_webvtt_removes_syntax_multiline_and_duplicate_overlap() -> None:
    segments = parse_webvtt((FIXTURES / "tiktok_captions.vtt").read_text())
    assert [segment.text for segment in segments] == [
        "Hello from Inkwell",
        "with a multiline caption & safe text",
        "without duplicated speech",
    ]
    assert segments[0].start == 0
    assert segments[-1].duration == 2.5


def test_parse_webvtt_rejects_empty_or_malformed_payload() -> None:
    with pytest.raises(ValidationError, match="empty or malformed"):
        parse_webvtt("WEBVTT\n\nNOTE no cues")


def test_short_url_resolves_metadata_and_embedded_subtitle_without_leaking_url() -> None:
    page = (FIXTURES / "tiktok_video.html").read_text()
    captions = (FIXTURES / "tiktok_captions.vtt").read_text()
    with _client(page, captions) as client:
        result = resolve_tiktok_source("https://www.tiktok.com/t/ZTDLJ84Cq/", client=client)
    assert result.canonical_url == "https://www.tiktok.com/@amber.figlow/video/7673547653170351373"
    assert result.creator == "amber.figlow"
    assert result.video_id == "7673547653170351373"
    assert result.duration_seconds == 681
    assert result.transcript_language == "eng-US"
    assert result.transcript_auto_generated is True
    assert "[00:00] Hello from Inkwell" in (result.transcript_text or "")
    provenance = result.provenance()
    assert provenance["transcript_method"] == "embedded_webvtt"
    assert "v16-sign" not in repr(provenance)
    assert "x-expires" not in repr(provenance)


def test_provenance_strips_sensitive_supplied_url_components() -> None:
    from inkwell.ingestion.tiktok import TikTokSource

    source = TikTokSource(
        supplied_url="https://user:secret@www.tiktok.com/t/abc/?session=private#fragment",
        canonical_url="https://www.tiktok.com/@creator/video/123",
    )
    assert source.provenance()["supplied_url"] == "https://www.tiktok.com/t/abc/"
    assert "secret" not in repr(source.provenance())
    assert "session" not in repr(source.provenance())


def test_page_http_failure_returns_stable_media_fallback() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="blocked")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/t/abc/?session=private", client=client
        )
    assert result.transcript_text is None
    assert result.canonical_url == "https://www.tiktok.com/t/abc/"
    assert "session" not in repr(result.provenance())


def test_caption_redirect_to_untrusted_host_is_not_followed() -> None:
    page = (FIXTURES / "tiktok_video.html").read_text()
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        if request.url.host == "www.tiktok.com":
            return httpx.Response(200, text=page)
        return httpx.Response(302, headers={"location": "https://127.0.0.1/private.vtt"})

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@amber.figlow/video/7673547653170351373", client=client
        )
    assert result.transcript_text is None
    assert "127.0.0.1" not in requested_hosts


def test_page_redirect_to_untrusted_host_is_not_followed() -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SecurityError, match="redirect location was rejected"):
            resolve_tiktok_source("https://www.tiktok.com/t/abc/?session=private", client=client)

    assert requested_hosts == ["www.tiktok.com"]


@pytest.mark.parametrize("target", ["page", "caption"])
def test_streamed_oversized_response_uses_media_fallback(target: str, monkeypatch) -> None:
    import inkwell.ingestion.tiktok as adapter

    monkeypatch.setattr(adapter, "_MAX_PAGE_BYTES", 32)
    monkeypatch.setattr(adapter, "_MAX_CAPTION_BYTES", 32)
    page = (FIXTURES / "tiktok_video.html").read_text()
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        if request.url.host == "www.tiktok.com":
            body = ("x" * 64) if target == "page" else page
            return httpx.Response(200, content=body.encode())
        return httpx.Response(200, content=b"WEBVTT\n" + (b"x" * 64))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@amber.figlow/video/7673547653170351373", client=client
        )

    assert result.transcript_text is None
    assert result.provenance()["transcript_method"] == "media_fallback"
    assert requested_hosts[0] == "www.tiktok.com"


def test_false_auto_generated_string_remains_false() -> None:
    page = (
        (FIXTURES / "tiktok_video.html")
        .read_text()
        .replace('"isAutoGenerated":true', '"isAutoGenerated":"false"')
    )
    captions = (FIXTURES / "tiktok_captions.vtt").read_text()
    with _client(page, captions) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@amber.figlow/video/7673547653170351373", client=client
        )
    assert result.transcript_auto_generated is False


def test_asr_caption_source_is_recorded_as_auto_generated() -> None:
    page = (
        (FIXTURES / "tiktok_video.html")
        .read_text()
        .replace('"isAutoGenerated":true', '"Source":"ASR"')
    )
    captions = (FIXTURES / "tiktok_captions.vtt").read_text()
    with _client(page, captions) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@amber.figlow/video/7673547653170351373", client=client
        )
    assert result.transcript_auto_generated is True


def test_untrusted_creator_metadata_cannot_corrupt_canonical_url() -> None:
    page = (
        (FIXTURES / "tiktok_video.html")
        .read_text()
        .replace('"uniqueId":"amber.figlow"', '"uniqueId":"creator?session=private"')
    )
    captions = (FIXTURES / "tiktok_captions.vtt").read_text()
    with _client(page, captions) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@safe.creator/video/7673547653170351373", client=client
        )

    assert result.creator == "safe.creator"
    assert result.canonical_url == (
        "https://www.tiktok.com/@safe.creator/video/7673547653170351373"
    )
    assert "session" not in repr(result.provenance())


def test_caption_infos_variant_is_supported() -> None:
    page = (FIXTURES / "tiktok_caption_infos.html").read_text()
    with _client(page, "WEBVTT\n\n00:00.000 --> 00:01.000\nHola") as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@fixture.creator/video/1234567890123456789", client=client
        )
    assert result.transcript_language == "es"
    assert result.transcript_text == "[00:00] Hola"


@pytest.mark.parametrize(("caption_status", "caption_body"), [(403, "expired"), (200, "WEBVTT")])
def test_rejected_or_malformed_caption_uses_media_fallback(
    caption_status: int, caption_body: str
) -> None:
    page = (FIXTURES / "tiktok_video.html").read_text()
    with _client(page, caption_body, caption_status=caption_status) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@amber.figlow/video/7673547653170351373", client=client
        )
    assert result.transcript_text is None
    assert result.provenance()["transcript_method"] == "media_fallback"
    assert "signature" not in repr(result.provenance())


def test_page_failure_still_allows_media_fallback_without_persisting_query() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="blocked")

    supplied = "https://www.tiktok.com/t/ZTDLJ84Cq/?utm_source=copy"
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        result = resolve_tiktok_source(supplied, client=client)

    assert result.transcript_text is None
    assert result.canonical_url == "https://www.tiktok.com/t/ZTDLJ84Cq/"
    assert result.provenance()["supplied_url"] == "https://www.tiktok.com/t/ZTDLJ84Cq/"


@pytest.mark.parametrize(
    "caption_url",
    [
        "http://v16-sign.tiktokcdn.com/caption.vtt",
        "https://127.0.0.1/caption.vtt",
        "https://user:password@v16-sign.tiktokcdn.com/caption.vtt",
        "https://attacker.example/caption.vtt",
    ],
)
def test_untrusted_caption_targets_are_not_requested(caption_url: str) -> None:
    page = (
        (FIXTURES / "tiktok_video.html")
        .read_text()
        .replace("https://v16-sign.tiktokcdn.com/caption.vtt?x-expires=secret", caption_url)
    )
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, text=page)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        result = resolve_tiktok_source(
            "https://www.tiktok.com/@amber.figlow/video/7673547653170351373", client=client
        )

    assert result.transcript_text is None
    assert requested == ["https://www.tiktok.com/@amber.figlow/video/7673547653170351373"]


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@www.tiktok.com/@creator/video/123",
        "ftp://www.tiktok.com/@creator/video/123",
        "https://www.tiktok.com.evil.example/@creator/video/123",
    ],
)
def test_rejects_credentialed_or_non_tiktok_urls(url: str) -> None:
    with pytest.raises(ValidationError, match="Not a TikTok URL"):
        resolve_tiktok_source(url)
