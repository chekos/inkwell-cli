"""Tests for RSS feed parser."""

from pathlib import Path

import feedparser
import pytest
import respx
from httpx import Response

from inkwell.config.schema import AuthConfig
from inkwell.feeds.parser import RSSParser
from inkwell.utils.errors import APIError, NotFoundError, SecurityError, ValidationError


@pytest.fixture
def valid_rss_feed() -> str:
    """Load valid RSS feed fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "valid_rss_feed.xml"
    return fixture_path.read_text()


@pytest.fixture
def atom_feed() -> str:
    """Load Atom feed fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "atom_feed.xml"
    return fixture_path.read_text()


@pytest.fixture
def malformed_feed() -> str:
    """Load malformed feed fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "malformed_feed.xml"
    return fixture_path.read_text()


class TestRSSParser:
    """Tests for RSSParser class."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_success(self, valid_rss_feed: str) -> None:
        """Test successful feed fetching."""
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(200, content=valid_rss_feed.encode())
        )

        parser = RSSParser()
        feed = await parser.fetch_feed("https://example.com/feed.rss")

        assert feed is not None
        assert len(feed.entries) == 3
        assert feed.feed.title == "Tech Talks Podcast"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_with_basic_auth(self, valid_rss_feed: str) -> None:
        """Test fetching feed with basic authentication."""
        route = respx.get("https://example.com/feed.rss").mock(
            return_value=Response(200, content=valid_rss_feed.encode())
        )

        parser = RSSParser()
        auth = AuthConfig(type="basic", username="user", password="pass")
        await parser.fetch_feed("https://example.com/feed.rss", auth=auth)

        # Check that Authorization header was sent
        request = route.calls[0].request
        assert "Authorization" in request.headers
        assert request.headers["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_with_bearer_auth(self, valid_rss_feed: str) -> None:
        """Test fetching feed with bearer token."""
        route = respx.get("https://example.com/feed.rss").mock(
            return_value=Response(200, content=valid_rss_feed.encode())
        )

        parser = RSSParser()
        auth = AuthConfig(type="bearer", token="secret-token")
        await parser.fetch_feed("https://example.com/feed.rss", auth=auth)

        # Check that Authorization header was sent
        request = route.calls[0].request
        assert "Authorization" in request.headers
        assert request.headers["Authorization"] == "Bearer secret-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_authentication_failure(self) -> None:
        """Test authentication failure (401)."""
        respx.get("https://example.com/feed.rss").mock(return_value=Response(401))

        parser = RSSParser()
        with pytest.raises(SecurityError, match="Authentication failed"):
            await parser.fetch_feed("https://example.com/feed.rss")

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_not_found(self) -> None:
        """Test feed not found (404)."""
        respx.get("https://example.com/feed.rss").mock(return_value=Response(404))

        parser = RSSParser()
        with pytest.raises(APIError, match="HTTP error"):
            await parser.fetch_feed("https://example.com/feed.rss")

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_timeout(self) -> None:
        """Test timeout handling."""
        import httpx as httpx_module

        respx.get("https://example.com/feed.rss").mock(
            side_effect=httpx_module.TimeoutException("Timeout")
        )

        parser = RSSParser(timeout=1)
        with pytest.raises(APIError, match="Timeout"):
            await parser.fetch_feed("https://example.com/feed.rss")

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_atom_format(self, atom_feed: str) -> None:
        """Test fetching Atom format feed."""
        respx.get("https://example.com/atom.xml").mock(
            return_value=Response(200, content=atom_feed.encode())
        )

        parser = RSSParser()
        feed = await parser.fetch_feed("https://example.com/atom.xml")

        assert feed is not None
        assert len(feed.entries) == 2
        assert feed.feed.title == "Developer Insights"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_feed_no_entries_raises(self) -> None:
        """Test that feed with no entries raises ValidationError."""
        empty_feed = '<?xml version="1.0"?><rss><channel></channel></rss>'
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(200, content=empty_feed.encode())
        )

        parser = RSSParser()
        with pytest.raises(ValidationError, match="No episodes found"):
            await parser.fetch_feed("https://example.com/feed.rss")

    def test_get_latest_episode(self, valid_rss_feed: str) -> None:
        """Test extracting latest episode from feed."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episode = parser.get_latest_episode(feed, "Tech Talks")

        assert episode.title == "Episode 100: The Future of AI"
        assert episode.podcast_name == "Tech Talks"
        assert episode.episode_number == 100
        assert episode.duration_seconds == 3600

    def test_get_episode_by_title(self, valid_rss_feed: str) -> None:
        """Test finding episode by title keyword."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episode = parser.get_episode_by_title(feed, "Scalable", "Tech Talks")

        assert episode.title == "Episode 99: Building Scalable Systems"
        assert episode.episode_number == 99

    def test_get_episode_by_title_not_found(self, valid_rss_feed: str) -> None:
        """Test that non-matching keyword raises ValidationError."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        with pytest.raises(ValidationError, match="No episode found matching"):
            parser.get_episode_by_title(feed, "nonexistent", "Tech Talks")

    def test_extract_episode_metadata(self, valid_rss_feed: str) -> None:
        """Test extracting episode metadata."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episode = parser.extract_episode_metadata(feed.entries[0], "Tech Talks")

        assert episode.title == "Episode 100: The Future of AI"
        assert str(episode.url) == "https://example.com/audio/ep100.mp3"
        assert episode.description != ""
        assert episode.duration_seconds == 3600
        assert episode.episode_number == 100

    def test_extract_episode_no_title_raises(self) -> None:
        """Test that episode without title raises ValidationError."""
        parser = RSSParser()
        entry = {}  # No title

        with pytest.raises(ValidationError, match="missing required field: title"):
            parser.extract_episode_metadata(entry, "Test")

    def test_extract_episode_no_enclosure_raises(self) -> None:
        """Test that episode without audio enclosure raises ValidationError."""
        parser = RSSParser()
        entry = {"title": "Test Episode"}  # No enclosure

        with pytest.raises(ValidationError, match="has no audio enclosure"):
            parser.extract_episode_metadata(entry, "Test")

    def test_extract_duration_hms_format(self) -> None:
        """Test duration extraction from HH:MM:SS format."""
        parser = RSSParser()
        entry = {"itunes_duration": "1:30:45"}

        duration = parser._extract_duration(entry)

        assert duration == 5445  # 1*3600 + 30*60 + 45

    def test_extract_duration_ms_format(self) -> None:
        """Test duration extraction from MM:SS format."""
        parser = RSSParser()
        entry = {"itunes_duration": "45:30"}

        duration = parser._extract_duration(entry)

        assert duration == 2730  # 45*60 + 30

    def test_extract_duration_seconds_format(self) -> None:
        """Test duration extraction from plain seconds."""
        parser = RSSParser()
        entry = {"itunes_duration": "3600"}

        duration = parser._extract_duration(entry)

        assert duration == 3600

    def test_extract_duration_missing(self) -> None:
        """Test duration extraction when field is missing."""
        parser = RSSParser()
        entry = {}

        duration = parser._extract_duration(entry)

        assert duration is None

    def test_extract_episode_number(self) -> None:
        """Test episode number extraction."""
        parser = RSSParser()
        entry = {"itunes_episode": "42"}

        episode_num = parser._extract_episode_number(entry)

        assert episode_num == 42

    def test_extract_season_number(self) -> None:
        """Test season number extraction."""
        parser = RSSParser()
        entry = {"itunes_season": "3"}

        season_num = parser._extract_season_number(entry)

        assert season_num == 3

    def test_extract_description_from_summary(self) -> None:
        """Test description extraction from summary field."""
        parser = RSSParser()
        entry = {"summary": "This is the summary"}

        description = parser._extract_description(entry)

        assert description == "This is the summary"

    def test_extract_description_from_content(self) -> None:
        """Test description extraction from content field."""
        parser = RSSParser()
        entry = {"content": [{"value": "This is the content"}]}

        description = parser._extract_description(entry)

        assert description == "This is the content"

    def test_extract_description_empty(self) -> None:
        """Test description extraction when no description available."""
        parser = RSSParser()
        entry = {}

        description = parser._extract_description(entry)

        assert description == ""

    def test_build_auth_headers_none(self) -> None:
        """Test auth header building with no authentication."""
        parser = RSSParser()

        headers = parser._build_auth_headers(None)

        assert headers == {}

    def test_build_auth_headers_basic(self) -> None:
        """Test basic authentication header building."""
        parser = RSSParser()
        auth = AuthConfig(type="basic", username="user", password="pass")

        headers = parser._build_auth_headers(auth)

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_build_auth_headers_bearer(self) -> None:
        """Test bearer token header building."""
        parser = RSSParser()
        auth = AuthConfig(type="bearer", token="secret-token")

        headers = parser._build_auth_headers(auth)

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer secret-token"


class TestParseAndFetchEpisodes:
    """Tests for parse_and_fetch_episodes method."""

    def test_single_position(self, valid_rss_feed: str) -> None:
        """Test selecting episode by single position number."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "2", "Tech Talks")

        assert len(episodes) == 1
        assert episodes[0].title == "Episode 99: Building Scalable Systems"

    def test_position_one_gets_latest(self, valid_rss_feed: str) -> None:
        """Test that position 1 returns the first (latest) episode."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "1", "Tech Talks")

        assert len(episodes) == 1
        assert episodes[0].title == "Episode 100: The Future of AI"

    def test_range(self, valid_rss_feed: str) -> None:
        """Test selecting episodes by range."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "1-3", "Tech Talks")

        assert len(episodes) == 3
        assert episodes[0].title == "Episode 100: The Future of AI"
        assert episodes[1].title == "Episode 99: Building Scalable Systems"
        assert episodes[2].title == "Episode 98: Python Deep Dive"

    def test_range_reversed_auto_corrects(self, valid_rss_feed: str) -> None:
        """Test that reversed range (5-1) is auto-corrected."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "3-1", "Tech Talks")

        # Should get episodes 1, 2, 3 (auto-corrected)
        assert len(episodes) == 3

    def test_list(self, valid_rss_feed: str) -> None:
        """Test selecting episodes by comma-separated list."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "1,3", "Tech Talks")

        assert len(episodes) == 2
        assert episodes[0].title == "Episode 100: The Future of AI"
        assert episodes[1].title == "Episode 98: Python Deep Dive"

    def test_list_with_spaces(self, valid_rss_feed: str) -> None:
        """Test that spaces in list are handled correctly."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "1, 2, 3", "Tech Talks")

        assert len(episodes) == 3

    def test_keyword_fallback(self, valid_rss_feed: str) -> None:
        """Test that non-numeric input falls back to keyword search."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "Scalable", "Tech Talks")

        assert len(episodes) == 1
        assert "Scalable" in episodes[0].title

    def test_keyword_with_spaces(self, valid_rss_feed: str) -> None:
        """Test keyword search with multiple words."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "Future of AI", "Tech Talks")

        assert len(episodes) == 1
        assert "Future of AI" in episodes[0].title

    def test_position_out_of_bounds(self, valid_rss_feed: str) -> None:
        """Test that out-of-bounds position raises NotFoundError."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        with pytest.raises(NotFoundError) as exc_info:
            parser.parse_and_fetch_episodes(feed, "50", "Tech Talks")

        assert "1-3" in exc_info.value.suggestion

    def test_zero_position_invalid(self, valid_rss_feed: str) -> None:
        """Test that position 0 raises NotFoundError."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        with pytest.raises(NotFoundError):
            parser.parse_and_fetch_episodes(feed, "0", "Tech Talks")

    def test_range_partial_out_of_bounds(self, valid_rss_feed: str) -> None:
        """Test that range with some positions out of bounds raises error."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        with pytest.raises(NotFoundError):
            parser.parse_and_fetch_episodes(feed, "2-10", "Tech Talks")

    def test_list_with_invalid_position(self, valid_rss_feed: str) -> None:
        """Test that list with invalid position raises error."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        with pytest.raises(NotFoundError):
            parser.parse_and_fetch_episodes(feed, "1,50", "Tech Talks")

    def test_whitespace_stripped(self, valid_rss_feed: str) -> None:
        """Test that leading/trailing whitespace is stripped."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        episodes = parser.parse_and_fetch_episodes(feed, "  2  ", "Tech Talks")

        assert len(episodes) == 1

    def test_keyword_not_found(self, valid_rss_feed: str) -> None:
        """Test that non-matching keyword raises ValidationError."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()

        with pytest.raises(ValidationError, match="No episode found matching"):
            parser.parse_and_fetch_episodes(feed, "nonexistent keyword", "Tech Talks")


class TestParseAndFetchEpisodesAdversarial:
    """Adversarial and edge case tests for parse_and_fetch_episodes."""

    def test_empty_string_selector(self, valid_rss_feed: str) -> None:
        """Test that empty string is handled gracefully."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        # Empty string treated as keyword search - matches first episode
        # (empty string is substring of all titles)
        episodes = parser.parse_and_fetch_episodes(feed, "", "Tech Talks")
        assert len(episodes) == 1
        assert episodes[0].title == "Episode 100: The Future of AI"

    def test_large_range_rejected(self, valid_rss_feed: str) -> None:
        """Test that excessively large ranges are rejected."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        with pytest.raises(ValidationError, match="maximum is 100"):
            parser.parse_and_fetch_episodes(feed, "1-1000", "Tech Talks")

    def test_large_list_rejected(self, valid_rss_feed: str) -> None:
        """Test that excessively large lists are rejected."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        large_list = ",".join(str(i) for i in range(1, 102))  # 101 items
        with pytest.raises(ValidationError, match="maximum is 100"):
            parser.parse_and_fetch_episodes(feed, large_list, "Tech Talks")

    def test_negative_number_treated_as_keyword(self, valid_rss_feed: str) -> None:
        """Test that negative numbers fall through to keyword search."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        # "-5" doesn't match position/range/list patterns, so keyword search
        with pytest.raises(ValidationError, match="No episode found"):
            parser.parse_and_fetch_episodes(feed, "-5", "Tech Talks")

    def test_range_start_equals_end(self, valid_rss_feed: str) -> None:
        """Test range where start == end returns single episode."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        episodes = parser.parse_and_fetch_episodes(feed, "2-2", "Tech Talks")
        assert len(episodes) == 1

    def test_duplicates_in_list_processed(self, valid_rss_feed: str) -> None:
        """Test that duplicate positions are processed as-is."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        episodes = parser.parse_and_fetch_episodes(feed, "1,1,2", "Tech Talks")
        # Current behavior: duplicates processed as-is (3 episodes returned)
        assert len(episodes) == 3
