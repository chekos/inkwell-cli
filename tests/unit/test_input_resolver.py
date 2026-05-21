"""Tests for input classification primitives."""

from pathlib import Path
from types import SimpleNamespace

from inkwell.ingestion import ContentSourceKind, InputResolver


def test_resolves_stdin_marker() -> None:
    source = InputResolver().resolve("-")

    assert source.kind == ContentSourceKind.STDIN
    assert source.value == "-"
    assert source.url is None


def test_resolves_existing_local_file(tmp_path: Path) -> None:
    media_file = tmp_path / "episode.mp3"
    media_file.write_bytes(b"fake audio")

    source = InputResolver().resolve(str(media_file))

    assert source.kind == ContentSourceKind.LOCAL_FILE
    assert source.path == media_file
    assert source.value == str(media_file)


def test_resolves_youtube_url() -> None:
    source = InputResolver().resolve("https://www.youtube.com/watch?v=abc123")

    assert source.kind == ContentSourceKind.YOUTUBE
    assert source.is_url is True
    assert source.url == "https://www.youtube.com/watch?v=abc123"


def test_resolves_scheme_less_youtube_url() -> None:
    source = InputResolver().resolve("www.youtube.com/watch?v=abc123")

    assert source.kind == ContentSourceKind.YOUTUBE
    assert source.url == "https://www.youtube.com/watch?v=abc123"
    assert source.value == "https://www.youtube.com/watch?v=abc123"


def test_resolves_direct_media_url() -> None:
    source = InputResolver().resolve("https://example.com/podcast/episode.m4a?download=1")

    assert source.kind == ContentSourceKind.DIRECT_MEDIA
    assert source.is_url is True


def test_resolves_generic_http_url() -> None:
    source = InputResolver().resolve("https://example.com/articles/how-to-learn")

    assert source.kind == ContentSourceKind.URL
    assert source.is_url is True


def test_resolves_unknown_url_scheme() -> None:
    source = InputResolver().resolve("ftp://example.com/episode.mp3")

    assert source.kind == ContentSourceKind.UNKNOWN_URL
    assert source.is_url is False
    assert source.url == "ftp://example.com/episode.mp3"


def test_resolves_known_saved_feed_by_key() -> None:
    source = InputResolver(saved_feeds={"my-feed": object()}).resolve("my-feed")

    assert source.kind == ContentSourceKind.SAVED_FEED
    assert source.feed_name == "my-feed"
    assert source.is_existing_feed is True


def test_resolves_known_saved_feed_by_display_name() -> None:
    source = InputResolver(
        saved_feeds={"omw": SimpleNamespace(display_name="Oren Meets World")}
    ).resolve("oren meets world")

    assert source.kind == ContentSourceKind.SAVED_FEED
    assert source.feed_name == "omw"
    assert source.is_existing_feed is True


def test_unrecognized_token_stays_feed_reference() -> None:
    source = InputResolver().resolve("maybe-a-feed")

    assert source.kind == ContentSourceKind.SAVED_FEED
    assert source.feed_name == "maybe-a-feed"
    assert source.is_existing_feed is False
