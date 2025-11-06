"""Tests for feed models and Episode class."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from inkwell.feeds.models import Episode, slugify


class TestSlugify:
    """Tests for the slugify function."""

    def test_slugify_basic(self) -> None:
        """Test basic slugification."""
        assert slugify("Hello World") == "hello-world"

    def test_slugify_special_characters(self) -> None:
        """Test that special characters are removed."""
        assert slugify("Hello, World!") == "hello-world"
        assert slugify("Test: Episode #100") == "test-episode-100"

    def test_slugify_multiple_spaces(self) -> None:
        """Test that multiple spaces become single hyphen."""
        assert slugify("Hello    World") == "hello-world"

    def test_slugify_underscores(self) -> None:
        """Test that underscores are converted to hyphens."""
        assert slugify("hello_world_test") == "hello-world-test"

    def test_slugify_max_length(self) -> None:
        """Test that long strings are truncated."""
        long_text = "a" * 100
        result = slugify(long_text, max_length=20)
        assert len(result) <= 20

    def test_slugify_max_length_at_word_boundary(self) -> None:
        """Test that truncation happens at word boundaries."""
        text = "hello-world-this-is-a-very-long-title"
        result = slugify(text, max_length=20)
        # Should cut at a hyphen, not mid-word
        assert "-" not in result or result.endswith("-") is False

    def test_slugify_leading_trailing_hyphens(self) -> None:
        """Test that leading/trailing hyphens are removed."""
        assert slugify("-hello-world-") == "hello-world"

    def test_slugify_empty_string(self) -> None:
        """Test empty string handling."""
        assert slugify("") == ""

    def test_slugify_only_special_characters(self) -> None:
        """Test string with only special characters."""
        assert slugify("!!!@@@###") == ""


class TestEpisode:
    """Tests for Episode model."""

    def test_episode_creation(self) -> None:
        """Test creating an Episode instance."""
        episode = Episode(
            title="Test Episode",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime(2024, 11, 6, 10, 0, 0),
            description="Test description",
            podcast_name="Test Podcast",
        )

        assert episode.title == "Test Episode"
        assert str(episode.url) == "https://example.com/audio.mp3"
        assert episode.description == "Test description"
        assert episode.podcast_name == "Test Podcast"

    def test_episode_invalid_url_raises(self) -> None:
        """Test that invalid URL raises ValidationError."""
        with pytest.raises(ValidationError):
            Episode(
                title="Test",
                url="not-a-url",  # type: ignore
                published=datetime.now(),
                description="Test",
                podcast_name="Test",
            )

    def test_episode_slug_generation(self) -> None:
        """Test that slug is generated correctly."""
        episode = Episode(
            title="Episode 100: The Future of AI",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime(2024, 11, 6, 10, 0, 0),
            description="Test",
            podcast_name="Tech Talks",
        )

        slug = episode.slug
        assert "tech-talks" in slug
        assert "2024-11-06" in slug
        assert "episode-100" in slug or "future" in slug

    def test_episode_duration_formatted_with_hours(self) -> None:
        """Test duration formatting with hours."""
        episode = Episode(
            title="Test",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime.now(),
            description="Test",
            podcast_name="Test",
            duration_seconds=3665,  # 1:01:05
        )

        assert episode.duration_formatted == "1:01:05"

    def test_episode_duration_formatted_without_hours(self) -> None:
        """Test duration formatting without hours."""
        episode = Episode(
            title="Test",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime.now(),
            description="Test",
            podcast_name="Test",
            duration_seconds=305,  # 5:05
        )

        assert episode.duration_formatted == "5:05"

    def test_episode_duration_formatted_none(self) -> None:
        """Test duration formatting when duration is None."""
        episode = Episode(
            title="Test",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime.now(),
            description="Test",
            podcast_name="Test",
            duration_seconds=None,
        )

        assert episode.duration_formatted == "Unknown"

    def test_episode_optional_fields(self) -> None:
        """Test that optional fields can be None."""
        episode = Episode(
            title="Test",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime.now(),
            description="Test",
            podcast_name="Test",
        )

        assert episode.duration_seconds is None
        assert episode.episode_number is None
        assert episode.season_number is None
        assert episode.guid is None

    def test_episode_with_episode_number(self) -> None:
        """Test episode with episode and season numbers."""
        episode = Episode(
            title="Test",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime.now(),
            description="Test",
            podcast_name="Test",
            episode_number=42,
            season_number=2,
        )

        assert episode.episode_number == 42
        assert episode.season_number == 2

    def test_episode_with_guid(self) -> None:
        """Test episode with GUID."""
        episode = Episode(
            title="Test",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime.now(),
            description="Test",
            podcast_name="Test",
            guid="unique-episode-id-123",
        )

        assert episode.guid == "unique-episode-id-123"

    def test_episode_serialization(self) -> None:
        """Test that Episode can be serialized and deserialized."""
        original = Episode(
            title="Test Episode",
            url="https://example.com/audio.mp3",  # type: ignore
            published=datetime(2024, 11, 6),
            description="Description",
            podcast_name="Test Podcast",
            duration_seconds=1800,
            episode_number=10,
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = Episode(**data)

        assert restored.title == original.title
        assert restored.podcast_name == original.podcast_name
        assert restored.duration_seconds == original.duration_seconds
        assert restored.episode_number == original.episode_number
