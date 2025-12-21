"""Tests for configuration schema models."""

from pathlib import Path

import pytest
from pydantic import HttpUrl, ValidationError

from inkwell.config.schema import (
    AuthConfig,
    ExtractionConfig,
    FeedConfig,
    Feeds,
    GlobalConfig,
    InterviewConfig,
    TranscriptionConfig,
)


class TestAuthConfig:
    """Tests for AuthConfig model."""

    def test_auth_config_default_is_none(self) -> None:
        """Test that default auth type is 'none'."""
        auth = AuthConfig()
        assert auth.type == "none"
        assert auth.username is None
        assert auth.password is None
        assert auth.token is None

    def test_auth_config_basic_auth(self) -> None:
        """Test basic authentication configuration."""
        auth = AuthConfig(
            type="basic",
            username="user",
            password="pass",
        )
        assert auth.type == "basic"
        assert auth.username == "user"
        assert auth.password == "pass"
        assert auth.token is None

    def test_auth_config_bearer_auth(self) -> None:
        """Test bearer token authentication configuration."""
        auth = AuthConfig(
            type="bearer",
            token="secret-token",
        )
        assert auth.type == "bearer"
        assert auth.token == "secret-token"
        assert auth.username is None
        assert auth.password is None

    def test_auth_config_invalid_type_raises(self) -> None:
        """Test that invalid auth type raises ValidationError."""
        with pytest.raises(ValidationError):
            AuthConfig(type="invalid")  # type: ignore


class TestFeedConfig:
    """Tests for FeedConfig model."""

    def test_feed_config_minimal(self) -> None:
        """Test FeedConfig with minimal required fields."""
        feed = FeedConfig(url="https://example.com/feed.rss")  # type: ignore
        assert isinstance(feed.url, HttpUrl)
        assert feed.auth.type == "none"
        assert feed.category is None
        assert feed.custom_templates == []

    def test_feed_config_with_all_fields(self, sample_feed_config_dict: dict) -> None:
        """Test FeedConfig with all fields populated."""
        feed = FeedConfig(**sample_feed_config_dict)
        assert str(feed.url) == "https://example.com/feed.rss"
        assert feed.category == "tech"
        assert feed.custom_templates == ["architecture-patterns"]

    def test_feed_config_invalid_url_raises(self) -> None:
        """Test that invalid URL raises ValidationError."""
        with pytest.raises(ValidationError):
            FeedConfig(url="not-a-url")  # type: ignore

    def test_feed_config_with_auth(self) -> None:
        """Test FeedConfig with authentication."""
        feed = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="pass"),
        )
        assert feed.auth.type == "basic"
        assert feed.auth.username == "user"


class TestGlobalConfig:
    """Tests for GlobalConfig model."""

    def test_global_config_defaults(self) -> None:
        """Test GlobalConfig with default values."""
        config = GlobalConfig()
        assert config.version == "1"
        # Default output dir should be expanded (validator auto-expands ~)
        assert config.default_output_dir == Path("~/podcasts").expanduser()
        assert config.log_level == "INFO"
        assert "summary" in config.default_templates
        assert "quotes" in config.default_templates
        assert "key-concepts" in config.default_templates
        assert "tech" in config.template_categories
        assert "interview" in config.template_categories

        # New nested config structure
        assert config.transcription.model_name == "gemini-2.5-flash"
        assert config.transcription.youtube_check is True
        assert config.transcription.cost_threshold_usd == 1.0
        assert config.interview.model == "claude-sonnet-4-5"
        assert config.extraction.default_provider == "gemini"

    def test_global_config_from_dict(self, sample_config_dict: dict) -> None:
        """Test GlobalConfig created from dictionary."""
        config = GlobalConfig(**sample_config_dict)
        assert config.version == "1"
        assert config.log_level == "INFO"
        assert config.youtube_check is True

    def test_global_config_custom_output_dir(self) -> None:
        """Test GlobalConfig with custom output directory."""
        config = GlobalConfig(default_output_dir=Path("/custom/path"))
        assert config.default_output_dir == Path("/custom/path")

    def test_global_config_invalid_log_level_raises(self) -> None:
        """Test that invalid log level raises ValidationError."""
        with pytest.raises(ValidationError):
            GlobalConfig(log_level="INVALID")  # type: ignore

    def test_global_config_template_categories(self) -> None:
        """Test template categories structure."""
        config = GlobalConfig()
        assert isinstance(config.template_categories, dict)
        assert isinstance(config.template_categories["tech"], list)
        assert "tools-mentioned" in config.template_categories["tech"]
        assert "books-mentioned" in config.template_categories["interview"]

    def test_global_config_backward_compatibility(self) -> None:
        """Test that deprecated fields still work via migration."""
        config = GlobalConfig(
            transcription_model="gemini-1.5-flash",
            interview_model="claude-opus-4",
            youtube_check=False,
        )
        # Deprecated fields should migrate to new structure
        assert config.transcription.model_name == "gemini-1.5-flash"
        assert config.interview.model == "claude-opus-4"
        assert config.transcription.youtube_check is False

    def test_migration_respects_explicit_new_config(self) -> None:
        """When user explicitly sets new config, don't override with deprecated.

        This test validates that users can migrate from old to new config
        without the deprecated field silently overriding their explicit choices.
        """
        config = GlobalConfig(
            transcription_model="gemini-1.5-flash",  # Old/deprecated
            transcription=TranscriptionConfig(model_name="gemini-2.5-flash"),  # Explicit new
        )

        # User's explicit choice should win
        assert config.transcription.model_name == "gemini-2.5-flash"

    def test_migration_respects_explicit_interview_config(self) -> None:
        """When user explicitly sets interview.model, don't override with deprecated."""
        config = GlobalConfig(
            interview_model="claude-opus-4",  # Old/deprecated
            interview=InterviewConfig(model="claude-sonnet-4-5"),  # Explicit new
        )

        # User's explicit choice should win
        assert config.interview.model == "claude-sonnet-4-5"

    def test_migration_respects_explicit_youtube_check(self) -> None:
        """When user explicitly sets youtube_check in new config, respect it."""
        config = GlobalConfig(
            youtube_check=False,  # Deprecated
            transcription=TranscriptionConfig(youtube_check=True),  # Explicit new
        )

        # User's explicit choice should win
        assert config.transcription.youtube_check is True

    def test_migration_applies_when_new_not_provided(self) -> None:
        """When new config not provided, apply deprecated value."""
        config = GlobalConfig(
            transcription_model="gemini-1.5-flash",
            # transcription NOT provided - will use default_factory
        )

        # Should migrate since transcription was not explicitly set
        assert config.transcription.model_name == "gemini-1.5-flash"

    def test_migration_interview_applies_when_new_not_provided(self) -> None:
        """When interview config not provided, apply deprecated value."""
        config = GlobalConfig(
            interview_model="claude-opus-4",
            # interview NOT provided - will use default_factory
        )

        # Should migrate since interview was not explicitly set
        assert config.interview.model == "claude-opus-4"

    def test_migration_youtube_check_applies_when_new_not_provided(self) -> None:
        """When transcription config not provided, apply deprecated youtube_check."""
        config = GlobalConfig(
            youtube_check=False,
            # transcription NOT provided - will use default_factory
        )

        # Should migrate since transcription was not explicitly set
        assert config.transcription.youtube_check is False

    def test_migration_blocked_when_explicit_empty_config(self) -> None:
        """Even if user passes empty config object, respect it (don't migrate).

        This validates that passing TranscriptionConfig() explicitly signals
        intent to use new structure, even if all fields are at defaults.
        """
        config = GlobalConfig(
            transcription_model="gemini-1.5-flash",
            transcription=TranscriptionConfig(),  # Explicit, even if default values
        )

        # Should NOT migrate because user explicitly provided transcription config
        # This is the new intended behavior - explicit config wins, even if empty
        assert config.transcription.model_name == "gemini-2.5-flash"  # Default, not migrated

    def test_global_config_new_fields_only(self) -> None:
        """Using only new nested structure works correctly.

        This test validates the preferred approach where users only use
        the new nested config structure without any deprecated fields.
        """
        config = GlobalConfig(transcription=TranscriptionConfig(model_name="gemini-2.5-flash"))

        assert config.transcription.model_name == "gemini-2.5-flash"
        # Deprecated field should not be set
        assert config.transcription_model is None

    def test_default_output_dir_expands_tilde(self) -> None:
        """Tilde paths should expand to user home directory."""
        config = GlobalConfig(default_output_dir=Path("~/test-podcasts"))

        # Should expand ~ to actual home directory
        assert not str(config.default_output_dir).startswith("~")
        assert config.default_output_dir.is_absolute()

        # Should contain user's home directory
        home = Path.home()
        assert str(config.default_output_dir).startswith(str(home))

    def test_absolute_path_unchanged(self) -> None:
        """Absolute paths should not be modified."""
        config = GlobalConfig(default_output_dir=Path("/absolute/path"))

        assert config.default_output_dir == Path("/absolute/path")

    def test_relative_path_unchanged(self) -> None:
        """Relative paths should not be modified."""
        config = GlobalConfig(default_output_dir=Path("relative/path"))

        # Relative paths stay relative (only ~ expands)
        assert config.default_output_dir == Path("relative/path")


class TestFeeds:
    """Tests for Feeds model."""

    def test_feeds_empty_default(self) -> None:
        """Test that Feeds defaults to empty dictionary."""
        feeds = Feeds()
        assert feeds.feeds == {}

    def test_feeds_with_feed(self) -> None:
        """Test Feeds with a single feed."""
        feed_config = FeedConfig(url="https://example.com/feed.rss")  # type: ignore
        feeds = Feeds(feeds={"my-podcast": feed_config})
        assert "my-podcast" in feeds.feeds
        assert isinstance(feeds.feeds["my-podcast"], FeedConfig)

    def test_feeds_multiple_feeds(self) -> None:
        """Test Feeds with multiple feeds."""
        feeds = Feeds(
            feeds={
                "podcast1": FeedConfig(url="https://example.com/feed1.rss"),  # type: ignore
                "podcast2": FeedConfig(url="https://example.com/feed2.rss"),  # type: ignore
            }
        )
        assert len(feeds.feeds) == 2
        assert "podcast1" in feeds.feeds
        assert "podcast2" in feeds.feeds

    def test_feeds_serialization(self) -> None:
        """Test that Feeds can be serialized and deserialized."""
        original = Feeds(
            feeds={"test": FeedConfig(url="https://example.com/feed.rss")}  # type: ignore
        )
        # Serialize to dict
        data = original.model_dump()
        # Deserialize back
        restored = Feeds(**data)
        assert "test" in restored.feeds
        assert str(restored.feeds["test"].url) == "https://example.com/feed.rss"


class TestTranscriptionConfigValidation:
    """Tests for TranscriptionConfig input validation."""

    def test_cost_threshold_valid_values(self) -> None:
        """Test that valid cost threshold values are accepted."""
        # Minimum value
        config = TranscriptionConfig(cost_threshold_usd=0.0)
        assert config.cost_threshold_usd == 0.0

        # Mid-range value
        config = TranscriptionConfig(cost_threshold_usd=100.0)
        assert config.cost_threshold_usd == 100.0

        # Maximum value
        config = TranscriptionConfig(cost_threshold_usd=1000.0)
        assert config.cost_threshold_usd == 1000.0

    def test_cost_threshold_rejects_negative(self) -> None:
        """Test that negative cost threshold is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionConfig(cost_threshold_usd=-1.0)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_cost_threshold_rejects_excessive(self) -> None:
        """Test that excessive cost threshold is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionConfig(cost_threshold_usd=9999.0)
        assert "less than or equal to 1000" in str(exc_info.value)

    def test_model_name_valid_format(self) -> None:
        """Test that valid Gemini model names are accepted."""
        config = TranscriptionConfig(model_name="gemini-2.5-flash")
        assert config.model_name == "gemini-2.5-flash"

        config = TranscriptionConfig(model_name="gemini-1.5-pro")
        assert config.model_name == "gemini-1.5-pro"

    def test_model_name_rejects_invalid_prefix(self) -> None:
        """Test that model names not starting with 'gemini-' are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionConfig(model_name="gpt-4")
        assert 'Model name must start with "gemini-"' in str(exc_info.value)

    def test_model_name_rejects_empty(self) -> None:
        """Test that empty model name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionConfig(model_name="")
        assert "at least 1 character" in str(exc_info.value)

    def test_model_name_rejects_too_long(self) -> None:
        """Test that excessively long model names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionConfig(model_name="gemini-" + "x" * 200)
        assert "at most 100 characters" in str(exc_info.value)

    def test_api_key_validates_length(self) -> None:
        """Test that API key length constraints are enforced."""
        # Valid length
        config = TranscriptionConfig(api_key="x" * 50)
        assert len(config.api_key) == 50  # type: ignore

        # Too short
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionConfig(api_key="short")
        assert "at least 20 characters" in str(exc_info.value)

        # Too long
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionConfig(api_key="x" * 600)
        assert "at most 500 characters" in str(exc_info.value)


class TestExtractionConfigValidation:
    """Tests for ExtractionConfig input validation."""

    def test_api_keys_validate_length(self) -> None:
        """Test that API key length constraints are enforced."""
        # Valid Claude API key
        config = ExtractionConfig(claude_api_key="x" * 50)
        assert len(config.claude_api_key) == 50  # type: ignore

        # Valid Gemini API key
        config = ExtractionConfig(gemini_api_key="x" * 50)
        assert len(config.gemini_api_key) == 50  # type: ignore

    def test_claude_api_key_rejects_too_short(self) -> None:
        """Test that short Claude API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionConfig(claude_api_key="short")
        assert "at least 20 characters" in str(exc_info.value)

    def test_claude_api_key_rejects_too_long(self) -> None:
        """Test that excessively long Claude API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionConfig(claude_api_key="x" * 600)
        assert "at most 500 characters" in str(exc_info.value)

    def test_gemini_api_key_rejects_too_short(self) -> None:
        """Test that short Gemini API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionConfig(gemini_api_key="short")
        assert "at least 20 characters" in str(exc_info.value)

    def test_gemini_api_key_rejects_too_long(self) -> None:
        """Test that excessively long Gemini API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionConfig(gemini_api_key="x" * 600)
        assert "at most 500 characters" in str(exc_info.value)


class TestInterviewConfigValidation:
    """Tests for InterviewConfig input validation."""

    def test_question_count_valid_values(self) -> None:
        """Test that valid question counts are accepted."""
        # Minimum
        config = InterviewConfig(question_count=1)
        assert config.question_count == 1

        # Mid-range
        config = InterviewConfig(question_count=10)
        assert config.question_count == 10

        # Maximum
        config = InterviewConfig(question_count=100)
        assert config.question_count == 100

    def test_question_count_rejects_zero(self) -> None:
        """Test that zero question count is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(question_count=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_question_count_rejects_negative(self) -> None:
        """Test that negative question count is rejected (DoS prevention)."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(question_count=-1)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_question_count_rejects_excessive(self) -> None:
        """Test that excessive question count is rejected (DoS prevention)."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(question_count=999)
        assert "less than or equal to 100" in str(exc_info.value)

    def test_max_depth_valid_values(self) -> None:
        """Test that valid max depth values are accepted."""
        config = InterviewConfig(max_depth=1)
        assert config.max_depth == 1

        config = InterviewConfig(max_depth=5)
        assert config.max_depth == 5

        config = InterviewConfig(max_depth=10)
        assert config.max_depth == 10

    def test_max_depth_rejects_zero(self) -> None:
        """Test that zero max depth is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(max_depth=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_max_depth_rejects_excessive(self) -> None:
        """Test that excessive max depth is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(max_depth=999)
        assert "less than or equal to 10" in str(exc_info.value)

    def test_session_timeout_valid_values(self) -> None:
        """Test that valid session timeout values are accepted."""
        # Minimum (1 minute)
        config = InterviewConfig(session_timeout_minutes=1)
        assert config.session_timeout_minutes == 1

        # Mid-range (1 hour)
        config = InterviewConfig(session_timeout_minutes=60)
        assert config.session_timeout_minutes == 60

        # Maximum (24 hours)
        config = InterviewConfig(session_timeout_minutes=1440)
        assert config.session_timeout_minutes == 1440

    def test_session_timeout_rejects_zero(self) -> None:
        """Test that zero session timeout is rejected (DoS prevention)."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(session_timeout_minutes=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_session_timeout_rejects_negative(self) -> None:
        """Test that negative session timeout is rejected (DoS prevention)."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(session_timeout_minutes=-1)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_session_timeout_rejects_excessive(self) -> None:
        """Test that excessive session timeout is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(session_timeout_minutes=9999)
        assert "less than or equal to 1440" in str(exc_info.value)

    def test_max_cost_valid_values(self) -> None:
        """Test that valid max cost values are accepted."""
        # Free tier
        config = InterviewConfig(max_cost_per_interview=0.0)
        assert config.max_cost_per_interview == 0.0

        # Default
        config = InterviewConfig(max_cost_per_interview=0.50)
        assert config.max_cost_per_interview == 0.50

        # Maximum
        config = InterviewConfig(max_cost_per_interview=100.0)
        assert config.max_cost_per_interview == 100.0

    def test_max_cost_rejects_negative(self) -> None:
        """Test that negative max cost is rejected (security bypass prevention)."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(max_cost_per_interview=-1.0)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_max_cost_rejects_excessive(self) -> None:
        """Test that excessive max cost is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(max_cost_per_interview=999.0)
        assert "less than or equal to 100" in str(exc_info.value)

    def test_temperature_valid_values(self) -> None:
        """Test that valid temperature values are accepted."""
        # Minimum
        config = InterviewConfig(temperature=0.0)
        assert config.temperature == 0.0

        # Mid-range
        config = InterviewConfig(temperature=1.0)
        assert config.temperature == 1.0

        # Maximum
        config = InterviewConfig(temperature=2.0)
        assert config.temperature == 2.0

    def test_temperature_rejects_negative(self) -> None:
        """Test that negative temperature is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(temperature=-0.1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_temperature_rejects_excessive(self) -> None:
        """Test that excessive temperature is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(temperature=3.0)
        assert "less than or equal to 2" in str(exc_info.value)

    def test_guidelines_validates_length(self) -> None:
        """Test that guidelines length constraint is enforced."""
        # Valid length
        config = InterviewConfig(guidelines="x" * 1000)
        assert len(config.guidelines) == 1000

        # Maximum length
        config = InterviewConfig(guidelines="x" * 10000)
        assert len(config.guidelines) == 10000

    def test_guidelines_rejects_too_long(self) -> None:
        """Test that excessively long guidelines are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(guidelines="x" * 20000)
        assert "at most 10000 characters" in str(exc_info.value)

    def test_model_validates_length(self) -> None:
        """Test that model name length constraint is enforced."""
        # Valid model name
        config = InterviewConfig(model="claude-sonnet-4-5")
        assert config.model == "claude-sonnet-4-5"

        # Too short
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(model="")
        assert "at least 1 character" in str(exc_info.value)

        # Too long
        with pytest.raises(ValidationError) as exc_info:
            InterviewConfig(model="x" * 200)
        assert "at most 100 characters" in str(exc_info.value)
