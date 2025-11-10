"""Tests for Dataview frontmatter generation."""

from datetime import datetime

import pytest

from inkwell.obsidian.dataview import (
    DataviewConfig,
    DataviewFrontmatter,
    create_frontmatter_dict,
    format_frontmatter_yaml,
)
from inkwell.obsidian.models import Entity, EntityType


class TestDataviewFrontmatter:
    """Test DataviewFrontmatter model."""

    def test_frontmatter_creation(self):
        """Test basic frontmatter creation."""
        frontmatter = DataviewFrontmatter(
            template="summary",
            podcast="Lex Fridman Podcast",
            episode="Cal Newport on Deep Work",
            created_date="2025-11-10",
            last_modified="2025-11-10",
            extracted_with="gemini",
        )

        assert frontmatter.template == "summary"
        assert frontmatter.podcast == "Lex Fridman Podcast"
        assert frontmatter.episode == "Cal Newport on Deep Work"
        assert frontmatter.extracted_with == "gemini"

    def test_frontmatter_with_optional_fields(self):
        """Test frontmatter with all optional fields."""
        frontmatter = DataviewFrontmatter(
            template="summary",
            podcast="Lex Fridman Podcast",
            episode="Cal Newport on Deep Work",
            episode_number=261,
            created_date="2025-11-10",
            episode_date="2023-05-15",
            last_modified="2025-11-10",
            url="https://example.com/episode",
            duration_minutes=180,
            host="Lex Fridman",
            guest="Cal Newport",
            people=["Cal Newport", "Andrew Huberman"],
            tags=["podcast/lex-fridman", "topic/ai"],
            topics=["ai", "productivity"],
            rating=5,
            status="completed",
            priority="high",
            extracted_with="gemini",
            cost_usd=0.0045,
            word_count=25000,
            has_wikilinks=True,
            has_interview=True,
        )

        assert frontmatter.episode_number == 261
        assert frontmatter.duration_minutes == 180
        assert frontmatter.host == "Lex Fridman"
        assert frontmatter.guest == "Cal Newport"
        assert len(frontmatter.people) == 2
        assert len(frontmatter.tags) == 2
        assert frontmatter.rating == 5
        assert frontmatter.status == "completed"
        assert frontmatter.has_wikilinks is True

    def test_rating_validation(self):
        """Test rating validation (1-5)."""
        # Valid ratings
        for rating in [1, 2, 3, 4, 5]:
            fm = DataviewFrontmatter(
                template="summary",
                podcast="Test",
                episode="Test",
                created_date="2025-11-10",
                last_modified="2025-11-10",
                extracted_with="gemini",
                rating=rating,
            )
            assert fm.rating == rating

        # Invalid ratings should fail validation
        with pytest.raises(Exception):  # Pydantic validation error
            DataviewFrontmatter(
                template="summary",
                podcast="Test",
                episode="Test",
                created_date="2025-11-10",
                last_modified="2025-11-10",
                extracted_with="gemini",
                rating=6,  # Invalid: > 5
            )

    def test_status_options(self):
        """Test valid status options."""
        statuses = ["inbox", "reading", "completed", "archived"]

        for status in statuses:
            fm = DataviewFrontmatter(
                template="summary",
                podcast="Test",
                episode="Test",
                created_date="2025-11-10",
                last_modified="2025-11-10",
                extracted_with="gemini",
                status=status,
            )
            assert fm.status == status

    def test_priority_options(self):
        """Test valid priority options."""
        priorities = ["low", "medium", "high"]

        for priority in priorities:
            fm = DataviewFrontmatter(
                template="summary",
                podcast="Test",
                episode="Test",
                created_date="2025-11-10",
                last_modified="2025-11-10",
                extracted_with="gemini",
                priority=priority,
            )
            assert fm.priority == priority


class TestDataviewConfig:
    """Test DataviewConfig model."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = DataviewConfig()

        assert config.enabled is True
        assert config.include_episode_number is True
        assert config.include_duration is True
        assert config.include_word_count is True
        assert config.include_ratings is True
        assert config.include_status is True
        assert config.default_status == "inbox"
        assert config.default_priority == "medium"

    def test_config_customization(self):
        """Test custom configuration."""
        config = DataviewConfig(
            enabled=False,
            include_episode_number=False,
            include_duration=False,
            default_status="reading",
            default_priority="high",
        )

        assert config.enabled is False
        assert config.include_episode_number is False
        assert config.default_status == "reading"
        assert config.default_priority == "high"


class TestCreateFrontmatterDict:
    """Test create_frontmatter_dict function."""

    def test_basic_frontmatter_creation(self):
        """Test creating frontmatter from minimal metadata."""
        episode_metadata = {
            "podcast_name": "Lex Fridman Podcast",
            "episode_title": "Cal Newport on Deep Work",
        }

        # Mock extraction result
        class MockResult:
            provider = "gemini"
            cost_usd = 0.0045

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=MockResult(),
        )

        assert frontmatter["template"] == "summary"
        assert frontmatter["podcast"] == "Lex Fridman Podcast"
        assert frontmatter["episode"] == "Cal Newport on Deep Work"
        assert frontmatter["extracted_with"] == "gemini"
        assert frontmatter["cost_usd"] == 0.0045
        assert "created_date" in frontmatter
        assert "last_modified" in frontmatter

    def test_frontmatter_with_episode_number(self):
        """Test including episode number."""
        episode_metadata = {
            "podcast_name": "Lex Fridman Podcast",
            "episode_title": "Cal Newport on Deep Work",
            "episode_number": 261,
        }

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
        )

        assert frontmatter["episode_number"] == 261

    def test_frontmatter_with_dates(self):
        """Test date fields."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
            "episode_date": "2023-05-15",
        }

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
        )

        assert frontmatter["episode_date"] == "2023-05-15"
        assert "created_date" in frontmatter
        assert "last_modified" in frontmatter

    def test_frontmatter_with_urls(self):
        """Test URL fields."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
            "episode_url": "https://example.com/episode",
            "podcast_url": "https://example.com",
            "audio_url": "https://example.com/audio.mp3",
        }

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
        )

        assert frontmatter["url"] == "https://example.com/episode"
        assert frontmatter["podcast_url"] == "https://example.com"
        assert frontmatter["audio_url"] == "https://example.com/audio.mp3"

    def test_frontmatter_with_duration(self):
        """Test duration field."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
            "duration_minutes": 180,
        }

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
        )

        assert frontmatter["duration_minutes"] == 180

    def test_frontmatter_with_people(self):
        """Test host, guest, and people fields."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
            "host": "Lex Fridman",
            "guest": "Cal Newport",
        }

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
        )

        assert frontmatter["host"] == "Lex Fridman"
        assert frontmatter["guest"] == "Cal Newport"

    def test_frontmatter_with_entities(self):
        """Test extracting people from entities."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
        }

        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON, confidence=0.9),
            Entity(name="Andrew Huberman", type=EntityType.PERSON, confidence=0.85),
            Entity(name="Deep Work", type=EntityType.BOOK, confidence=0.9),
            Entity(name="Notion", type=EntityType.TOOL, confidence=0.8),
        ]

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
            entities=entities,
        )

        # Should extract only people
        assert "people" in frontmatter
        assert "Cal Newport" in frontmatter["people"]
        assert "Andrew Huberman" in frontmatter["people"]
        assert len(frontmatter["people"]) == 2

    def test_frontmatter_with_tags(self):
        """Test tag inclusion."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
        }

        tags = ["podcast/lex-fridman", "topic/ai", "topic/productivity", "theme/focus"]

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
            tags=tags,
        )

        assert frontmatter["tags"] == tags

        # Should extract topics from tags
        assert "topics" in frontmatter
        assert "ai" in frontmatter["topics"]
        assert "productivity" in frontmatter["topics"]

    def test_frontmatter_with_interview(self):
        """Test interview flag."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
        }

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
            interview_conducted=True,
        )

        assert frontmatter["has_interview"] is True

    def test_frontmatter_with_custom_config(self):
        """Test custom configuration."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
            "episode_number": 100,
            "duration_minutes": 120,
            "word_count": 25000,
        }

        config = DataviewConfig(
            include_episode_number=False,
            include_duration=False,
            include_word_count=False,
            include_status=False,
            include_ratings=False,
        )

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
            config=config,
        )

        # Fields should be excluded based on config
        assert "episode_number" not in frontmatter
        assert "duration_minutes" not in frontmatter
        assert "word_count" not in frontmatter
        assert "status" not in frontmatter
        assert "rating" not in frontmatter

    def test_frontmatter_default_status_and_priority(self):
        """Test default status and priority."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
        }

        config = DataviewConfig(
            default_status="reading",
            default_priority="high",
        )

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
            config=config,
        )

        assert frontmatter["status"] == "reading"
        assert frontmatter["priority"] == "high"

    def test_wikilinks_flag(self):
        """Test has_wikilinks flag."""
        episode_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
        }

        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON, confidence=0.9),
        ]

        frontmatter = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
            entities=entities,
        )

        assert frontmatter["has_wikilinks"] is True

        # Without entities
        frontmatter2 = create_frontmatter_dict(
            template_name="summary",
            episode_metadata=episode_metadata,
            extraction_result=None,
            entities=None,
        )

        assert frontmatter2["has_wikilinks"] is False


class TestFormatFrontmatterYaml:
    """Test format_frontmatter_yaml function."""

    def test_format_basic_frontmatter(self):
        """Test formatting frontmatter as YAML."""
        frontmatter = {
            "template": "summary",
            "podcast": "Lex Fridman Podcast",
            "episode": "Test Episode",
            "created_date": "2025-11-10",
            "rating": 5,
        }

        yaml_str = format_frontmatter_yaml(frontmatter)

        # Should have YAML delimiters
        assert yaml_str.startswith("---\n")
        assert yaml_str.endswith("---")

        # Should contain all fields
        assert "template: summary" in yaml_str
        assert "podcast: Lex Fridman Podcast" in yaml_str
        assert "episode: Test Episode" in yaml_str
        assert "created_date" in yaml_str
        assert "rating: 5" in yaml_str

    def test_format_with_lists(self):
        """Test formatting with list fields."""
        frontmatter = {
            "template": "summary",
            "podcast": "Test",
            "episode": "Test",
            "tags": ["podcast", "ai", "productivity"],
            "people": ["Cal Newport", "Andrew Huberman"],
        }

        yaml_str = format_frontmatter_yaml(frontmatter)

        assert "tags:" in yaml_str
        assert "- podcast" in yaml_str
        assert "- ai" in yaml_str
        assert "people:" in yaml_str
        assert "- Cal Newport" in yaml_str

    def test_format_preserves_order(self):
        """Test that field order is preserved."""
        frontmatter = {
            "template": "summary",
            "podcast": "Test",
            "episode": "Test",
            "created_date": "2025-11-10",
        }

        yaml_str = format_frontmatter_yaml(frontmatter)

        # Fields should appear in order
        template_pos = yaml_str.find("template:")
        podcast_pos = yaml_str.find("podcast:")
        episode_pos = yaml_str.find("episode:")
        date_pos = yaml_str.find("created_date:")

        assert template_pos < podcast_pos < episode_pos < date_pos

    def test_format_with_unicode(self):
        """Test formatting with Unicode characters."""
        frontmatter = {
            "template": "summary",
            "podcast": "Podcast français",
            "episode": "Episode with émojis 🎙️",
            "guest": "José García",
        }

        yaml_str = format_frontmatter_yaml(frontmatter)

        # Should handle Unicode properly
        assert "français" in yaml_str
        assert "émojis" in yaml_str
        assert "José García" in yaml_str
