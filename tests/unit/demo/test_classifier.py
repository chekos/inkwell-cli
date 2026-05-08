"""Tests for the demo URL classifier."""

import pytest

from inkwell.demo.classifier import (
    DemoUrlError,
    UrlKind,
    classify_demo_url,
)


class TestYouTubeAcceptance:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc12345xyz",
            "https://www.youtube.com/live/abc12345xyz",
            "https://www.youtube.com/embed/abc12345xyz",
        ],
    )
    def test_accepts_single_video_url_shapes(self, url: str) -> None:
        result = classify_demo_url(url)
        assert result.kind is UrlKind.YOUTUBE_VIDEO
        assert result.normalized_url == url


class TestYouTubeRejection:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/playlist?list=PLabc123",
            "https://www.youtube.com/watch?v=abc&list=PLabc123",
        ],
    )
    def test_rejects_playlist_urls(self, url: str) -> None:
        with pytest.raises(DemoUrlError) as excinfo:
            classify_demo_url(url)
        assert "playlist" in excinfo.value.user_message.lower()

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/",
            "https://www.youtube.com",
            "https://www.youtube.com/@somehandle",
            "https://www.youtube.com/c/SomeChannel",
            "https://www.youtube.com/channel/UCabc123",
            "https://www.youtube.com/user/SomeUser",
        ],
    )
    def test_rejects_non_video_youtube_urls(self, url: str) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url(url)

    def test_rejects_watch_without_video_id(self) -> None:
        with pytest.raises(DemoUrlError) as excinfo:
            classify_demo_url("https://www.youtube.com/watch")
        assert "video id" in excinfo.value.user_message.lower()

    def test_rejects_youtu_be_without_video_id(self) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url("https://youtu.be/")


class TestPublicRSSAcceptance:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/feed.rss",
            "https://feeds.simplecast.com/abc123",
            "http://example.com/podcast/feed.xml",
        ],
    )
    def test_accepts_public_rss_urls(self, url: str) -> None:
        result = classify_demo_url(url)
        assert result.kind is UrlKind.PUBLIC_RSS
        assert result.normalized_url == url


class TestSchemeAndHostRejections:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com/feed.rss",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "not-a-url",
            "",
        ],
    )
    def test_rejects_non_http_schemes(self, url: str) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/feed.rss",
            "http://127.0.0.1/feed.rss",
            "http://192.168.1.10/feed.rss",
            "http://10.0.0.5/feed.rss",
            "http://172.16.0.1/feed.rss",
            "http://[::1]/feed.rss",
            "http://service.local/feed.rss",
            "http://kubernetes.internal/feed.rss",
        ],
    )
    def test_rejects_private_or_local_addresses(self, url: str) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url(url)

    def test_strips_whitespace_before_classifying(self) -> None:
        result = classify_demo_url("   https://example.com/feed.rss  ")
        assert result.kind is UrlKind.PUBLIC_RSS
        assert result.normalized_url == "https://example.com/feed.rss"
