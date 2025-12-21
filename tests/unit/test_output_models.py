"""Unit tests for output models."""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from inkwell.output.models import (
    EpisodeMetadata,
    EpisodeOutput,
    OutputFile,
)
from inkwell.utils.datetime import now_utc


class TestEpisodeMetadata:
    """Tests for EpisodeMetadata model."""

    def test_create_minimal_metadata(self) -> None:
        """Test creating metadata with minimum required fields."""
        metadata = EpisodeMetadata(
            podcast_name="The Changelog",
            episode_title="Building Better Software",
            episode_url="https://example.com/ep123",
            transcription_source="youtube",
        )

        assert metadata.podcast_name == "The Changelog"
        assert metadata.episode_title == "Building Better Software"
        assert metadata.transcription_source == "youtube"
        assert metadata.total_cost_usd == 0.0
        assert len(metadata.templates_applied) == 0

    def test_create_full_metadata(self) -> None:
        """Test creating metadata with all fields."""
        pub_date = datetime(2025, 11, 7, 10, 30)

        metadata = EpisodeMetadata(
            podcast_name="The Changelog",
            episode_title="Building Better Software",
            episode_url="https://example.com/ep123",
            published_date=pub_date,
            duration_seconds=2700.0,  # 45 minutes
            transcription_source="gemini",
            templates_applied=["summary", "quotes"],
            transcription_cost_usd=0.05,
            extraction_cost_usd=0.20,
            total_cost_usd=0.25,
            custom_fields={"category": "tech"},
        )

        assert metadata.published_date == pub_date
        assert metadata.duration_seconds == 2700.0
        assert metadata.templates_applied == ["summary", "quotes"]
        assert metadata.total_cost_usd == 0.25
        assert metadata.custom_fields["category"] == "tech"

    def test_duration_formatted_hours(self) -> None:
        """Test formatting duration with hours."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
            duration_seconds=3661.0,  # 1:01:01
        )

        assert metadata.duration_formatted == "01:01:01"

    def test_duration_formatted_minutes(self) -> None:
        """Test formatting duration without hours."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
            duration_seconds=125.0,  # 2:05
        )

        assert metadata.duration_formatted == "02:05"

    def test_duration_formatted_none(self) -> None:
        """Test formatting duration when None."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        assert metadata.duration_formatted == "Unknown"

    def test_date_slug(self) -> None:
        """Test date slug generation."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
            published_date=datetime(2025, 11, 7),
        )

        assert metadata.date_slug == "2025-11-07"

    def test_date_slug_uses_processed_date(self) -> None:
        """Test date slug falls back to processed date."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        # Should use processed_date (today)
        assert metadata.date_slug.startswith("2025-")

    def test_add_template(self) -> None:
        """Test adding template to applied list."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        metadata.add_template("summary")
        metadata.add_template("quotes")

        assert metadata.templates_applied == ["summary", "quotes"]

    def test_add_template_no_duplicates(self) -> None:
        """Test that adding same template twice doesn't duplicate."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        metadata.add_template("summary")
        metadata.add_template("summary")  # Duplicate

        assert metadata.templates_applied == ["summary"]

    def test_add_cost(self) -> None:
        """Test adding extraction cost."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="gemini",
            transcription_cost_usd=0.05,
        )

        metadata.add_cost(0.10)
        metadata.add_cost(0.15)

        assert metadata.extraction_cost_usd == 0.25
        assert metadata.total_cost_usd == 0.30  # 0.05 + 0.25

    def test_negative_duration_rejected(self) -> None:
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError):
            EpisodeMetadata(
                podcast_name="Test",
                episode_title="Test",
                episode_url="https://example.com/test",
                transcription_source="youtube",
                duration_seconds=-100.0,
            )

    def test_negative_cost_rejected(self) -> None:
        """Test that negative costs are rejected."""
        with pytest.raises(ValidationError):
            EpisodeMetadata(
                podcast_name="Test",
                episode_title="Test",
                episode_url="https://example.com/test",
                transcription_source="youtube",
                total_cost_usd=-0.10,
            )


class TestOutputFile:
    """Tests for OutputFile model."""

    def test_create_output_file(self) -> None:
        """Test creating output file."""
        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="# Summary\n\nThis is a summary.",
        )

        assert file.filename == "summary.md"
        assert file.template_name == "summary"
        assert file.content.startswith("# Summary")
        assert file.has_frontmatter is False

    def test_file_with_frontmatter(self) -> None:
        """Test file with frontmatter."""
        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="# Summary\n\nContent here.",
            frontmatter={
                "date": "2025-11-07",
                "tags": ["tech", "podcast"],
            },
        )

        assert file.has_frontmatter is True
        assert "date" in file.frontmatter
        assert file.frontmatter["tags"] == ["tech", "podcast"]

    def test_full_content_without_frontmatter(self) -> None:
        """Test full content when no frontmatter."""
        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="# Summary\n\nContent.",
        )

        assert file.full_content == "# Summary\n\nContent."

    def test_full_content_with_frontmatter(self) -> None:
        """Test full content includes frontmatter."""
        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="# Summary\n\nContent.",
            frontmatter={"date": "2025-11-07"},
        )

        full = file.full_content
        assert full.startswith("---\n")
        assert "date: '2025-11-07'" in full or "date: 2025-11-07" in full
        assert "---\n\n# Summary" in full

    def test_update_size(self) -> None:
        """Test size calculation."""
        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="Test content",
        )

        file.update_size()

        assert file.size_bytes > 0
        assert file.size_bytes == len(b"Test content")

    def test_created_at_timestamp(self) -> None:
        """Test that created_at is set."""
        file = OutputFile(
            filename="test.md",
            template_name="test",
            content="test",
        )

        assert isinstance(file.created_at, datetime)
        assert file.created_at <= now_utc()


class TestEpisodeOutput:
    """Tests for EpisodeOutput model."""

    def test_create_episode_output(self) -> None:
        """Test creating episode output."""
        metadata = EpisodeMetadata(
            podcast_name="The Changelog",
            episode_title="Building Better Software",
            episode_url="https://example.com/ep123",
            transcription_source="youtube",
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        assert output.metadata == metadata
        assert output.output_dir == Path("/tmp/output")
        assert output.total_files == 0
        assert output.total_size_bytes == 0

    def test_add_file(self) -> None:
        """Test adding files to output."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        file1 = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="Summary content",
        )

        file2 = OutputFile(
            filename="quotes.md",
            template_name="quotes",
            content="Quotes content",
        )

        output.add_file(file1)
        output.add_file(file2)

        assert output.total_files == 2
        assert output.total_size_bytes > 0
        assert len(output.files) == 2

    def test_get_file_by_template(self) -> None:
        """Test retrieving file by template name."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="Test",
        )

        output.add_file(file)

        found = output.get_file("summary")
        assert found is not None
        assert found.template_name == "summary"

        not_found = output.get_file("quotes")
        assert not_found is None

    def test_get_file_by_filename(self) -> None:
        """Test retrieving file by filename."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="Test",
        )

        output.add_file(file)

        found = output.get_file_by_name("summary.md")
        assert found is not None
        assert found.filename == "summary.md"

    def test_directory_name_formatting(self) -> None:
        """Test directory name formatting."""
        metadata = EpisodeMetadata(
            podcast_name="The Changelog",
            episode_title="Building Better Software",
            episode_url="https://example.com/test",
            transcription_source="youtube",
            published_date=datetime(2025, 11, 7),
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        dir_name = output.directory_name

        assert "the-changelog" in dir_name
        assert "2025-11-07" in dir_name
        assert "building-better-software" in dir_name
        assert " " not in dir_name  # No spaces

    def test_directory_name_special_chars(self) -> None:
        """Test directory name with special characters."""
        metadata = EpisodeMetadata(
            podcast_name="Tech & Stuff!",
            episode_title="Episode #123: The @Future",
            episode_url="https://example.com/test",
            transcription_source="youtube",
            published_date=datetime(2025, 11, 7),
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        dir_name = output.directory_name

        # Special characters removed
        assert "@" not in dir_name
        assert "#" not in dir_name
        assert "!" not in dir_name

    def test_directory_name_truncation(self) -> None:
        """Test long episode titles are truncated."""
        long_title = "This is a very long episode title " * 5

        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title=long_title,
            episode_url="https://example.com/test",
            transcription_source="youtube",
            published_date=datetime(2025, 11, 7),
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        dir_name = output.directory_name

        # Title part should be truncated
        parts = dir_name.split("-")
        title_part = "-".join(parts[4:])  # After podcast-YYYY-MM-DD-
        assert len(title_part) <= 50

    def test_size_formatted_bytes(self) -> None:
        """Test size formatting for bytes."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        output.total_size_bytes = 512
        assert output.size_formatted == "512 B"

    def test_size_formatted_kb(self) -> None:
        """Test size formatting for kilobytes."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        output.total_size_bytes = 5120
        assert "5.0 KB" in output.size_formatted

    def test_size_formatted_mb(self) -> None:
        """Test size formatting for megabytes."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        output.total_size_bytes = 5 * 1024 * 1024
        assert "5.0 MB" in output.size_formatted

    def test_get_summary(self) -> None:
        """Test summary generation."""
        metadata = EpisodeMetadata(
            podcast_name="The Changelog",
            episode_title="Building Better Software",
            episode_url="https://example.com/test",
            transcription_source="youtube",
            total_cost_usd=0.25,
        )

        output = EpisodeOutput(
            metadata=metadata,
            output_dir=Path("/tmp/output"),
        )

        file = OutputFile(
            filename="summary.md",
            template_name="summary",
            content="Test content here",
        )

        output.add_file(file)

        summary = output.get_summary()

        assert "1 files" in summary
        assert "cost: $0.250" in summary
