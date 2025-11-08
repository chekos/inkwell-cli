"""Unit tests for output manager."""

from pathlib import Path

import pytest
import yaml

from inkwell.extraction.models import ExtractedContent, ExtractionResult
from inkwell.output.manager import OutputManager
from inkwell.output.models import EpisodeMetadata


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def episode_metadata() -> EpisodeMetadata:
    """Create sample episode metadata."""
    return EpisodeMetadata(
        podcast_name="Test Podcast",
        episode_title="Episode 1: Testing",
        episode_url="https://example.com/ep1",
        transcription_source="youtube",
    )


@pytest.fixture
def extraction_results() -> list[ExtractionResult]:
    """Create sample extraction results."""
    return [
        ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(
                template_name="summary",
                content="Episode summary",
            ),
            cost_usd=0.01,
            provider="gemini",
        ),
        ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="quotes",
            success=True,
            extracted_content=ExtractedContent(
                template_name="quotes",
                content={"quotes": [{"text": "Test quote", "speaker": "John"}]},
            ),
            cost_usd=0.05,
            provider="claude",
        ),
    ]


class TestOutputManagerInit:
    """Tests for OutputManager initialization."""

    def test_init_creates_output_dir(self, tmp_path: Path) -> None:
        """Test that output directory is created."""
        output_dir = tmp_path / "new_output"
        assert not output_dir.exists()

        manager = OutputManager(output_dir=output_dir)

        assert output_dir.exists()
        assert manager.output_dir == output_dir

    def test_init_with_existing_dir(self, temp_output_dir: Path) -> None:
        """Test initialization with existing directory."""
        manager = OutputManager(output_dir=temp_output_dir)
        assert manager.output_dir == temp_output_dir


class TestOutputManagerWriteEpisode:
    """Tests for writing episode output."""

    def test_write_episode_basic(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test basic episode writing."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, extraction_results)

        # Check directory created
        assert output.directory.exists()
        assert output.directory.parent == temp_output_dir

        # Check files created
        assert len(output.output_files) == 2
        assert (output.directory / "summary.md").exists()
        assert (output.directory / "quotes.md").exists()

        # Check metadata file
        assert output.metadata_file.exists()
        assert output.metadata_file.name == ".metadata.yaml"

    def test_write_episode_directory_name(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that directory name is correct."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, extraction_results)

        # Directory should match pattern: podcast-name-YYYY-MM-DD-episode-title
        dir_name = output.directory.name
        assert "test-podcast" in dir_name.lower()
        assert "episode-1" in dir_name.lower()
        assert len(dir_name.split("-")) >= 5  # Has date components

    def test_write_episode_markdown_content(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that markdown files have correct content."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, extraction_results)

        # Read summary file
        summary_file = output.directory / "summary.md"
        summary_content = summary_file.read_text()

        # Should have frontmatter
        assert summary_content.startswith("---\n")
        assert "template: summary" in summary_content

        # Should have content
        assert "Episode summary" in summary_content

    def test_write_episode_metadata_file(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that metadata file is correct."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, extraction_results)

        # Read metadata file
        with output.metadata_file.open("r") as f:
            metadata = yaml.safe_load(f)

        assert metadata["podcast_name"] == "Test Podcast"
        assert metadata["episode_title"] == "Episode 1: Testing"
        assert metadata["episode_url"] == "https://example.com/ep1"
        assert "templates_applied" in metadata
        assert "summary" in metadata["templates_applied"]
        assert "quotes" in metadata["templates_applied"]
        assert "total_cost_usd" in metadata

    def test_write_episode_calculates_cost(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that total cost is calculated."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, extraction_results)

        # Load metadata
        metadata = manager.load_episode_metadata(output.directory)

        # Should sum costs from all results
        assert metadata.total_cost_usd == 0.06  # 0.01 + 0.05

    def test_write_episode_overwrite_false_raises(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that overwrite=False raises error if directory exists."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write once
        manager.write_episode(episode_metadata, extraction_results)

        # Try to write again without overwrite
        with pytest.raises(FileExistsError) as exc_info:
            manager.write_episode(episode_metadata, extraction_results, overwrite=False)

        assert "already exists" in str(exc_info.value).lower()

    def test_write_episode_overwrite_true_replaces(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that overwrite=True replaces existing directory."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write once
        output1 = manager.write_episode(episode_metadata, extraction_results)
        file1 = output1.directory / "summary.md"
        original_content = file1.read_text()

        # Modify extraction results
        extraction_results[0].content.data["text"] = "Modified summary"

        # Write again with overwrite
        output2 = manager.write_episode(episode_metadata, extraction_results, overwrite=True)

        # Should be same directory
        assert output2.directory == output1.directory

        # Content should be updated
        new_content = file1.read_text()
        assert new_content != original_content
        assert "Modified summary" in new_content


class TestOutputManagerAtomicWrites:
    """Tests for atomic file writing."""

    def test_write_file_atomic_creates_file(self, temp_output_dir: Path) -> None:
        """Test that atomic write creates file."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"
        content = "Test content"

        manager._write_file_atomic(test_file, content)

        assert test_file.exists()
        assert test_file.read_text() == content

    def test_write_file_atomic_no_temp_files_left(self, temp_output_dir: Path) -> None:
        """Test that no temporary files are left after write."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"

        manager._write_file_atomic(test_file, "Content")

        # Check for temp files
        temp_files = list(temp_output_dir.glob(".tmp_*"))
        assert len(temp_files) == 0

    def test_write_file_atomic_replaces_existing(self, temp_output_dir: Path) -> None:
        """Test that atomic write replaces existing file."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"

        # Write original
        test_file.write_text("Original")

        # Atomic write new content
        manager._write_file_atomic(test_file, "Replaced")

        assert test_file.read_text() == "Replaced"


class TestOutputManagerListEpisodes:
    """Tests for listing episodes."""

    def test_list_episodes_empty(self, temp_output_dir: Path) -> None:
        """Test listing episodes when none exist."""
        manager = OutputManager(output_dir=temp_output_dir)

        episodes = manager.list_episodes()
        assert len(episodes) == 0

    def test_list_episodes_with_episodes(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test listing episodes after writing some."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write one episode
        manager.write_episode(episode_metadata, extraction_results)

        # Write another with different title
        episode_metadata.episode_title = "Episode 2"
        manager.write_episode(episode_metadata, extraction_results)

        episodes = manager.list_episodes()
        assert len(episodes) == 2

    def test_list_episodes_ignores_non_episodes(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that non-episode directories are ignored."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write real episode
        manager.write_episode(episode_metadata, extraction_results)

        # Create directory without metadata
        (temp_output_dir / "not-an-episode").mkdir()

        episodes = manager.list_episodes()
        assert len(episodes) == 1


class TestOutputManagerLoadMetadata:
    """Tests for loading episode metadata."""

    def test_load_episode_metadata(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test loading metadata from episode directory."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, extraction_results)

        # Load metadata
        loaded_metadata = manager.load_episode_metadata(output.directory)

        assert loaded_metadata.podcast_name == episode_metadata.podcast_name
        assert loaded_metadata.episode_title == episode_metadata.episode_title
        assert loaded_metadata.episode_url == episode_metadata.episode_url

    def test_load_metadata_missing_file_raises(self, temp_output_dir: Path) -> None:
        """Test that loading from directory without metadata raises error."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Create directory without metadata
        test_dir = temp_output_dir / "test-episode"
        test_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            manager.load_episode_metadata(test_dir)


class TestOutputManagerStatistics:
    """Tests for statistics."""

    def test_get_statistics_empty(self, temp_output_dir: Path) -> None:
        """Test statistics for empty output directory."""
        manager = OutputManager(output_dir=temp_output_dir)

        stats = manager.get_statistics()

        assert stats["total_episodes"] == 0
        assert stats["total_files"] == 0
        assert stats["total_size_mb"] >= 0

    def test_get_statistics_with_episodes(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test statistics with episodes."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write episode
        manager.write_episode(episode_metadata, extraction_results)

        stats = manager.get_statistics()

        assert stats["total_episodes"] == 1
        assert stats["total_files"] == 2  # summary.md, quotes.md
        assert stats["total_size_mb"] > 0

    def test_get_total_size(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test getting total size."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Empty directory
        assert manager.get_total_size() == 0

        # Write episode
        manager.write_episode(episode_metadata, extraction_results)

        # Should have size now
        total_size = manager.get_total_size()
        assert total_size > 0


class TestOutputManagerEdgeCases:
    """Tests for edge cases."""

    def test_write_episode_unicode_content(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
    ) -> None:
        """Test handling unicode in episode content."""
        results = [
            ExtractionResult(
                template_name="summary",
                content=ExtractedContent(
                    format="text",
                    data={"text": "Content with émojis 🎉 and symbols ™"},
                    raw="...",
                ),
                cost_usd=0.0,
                provider="cache",
            )
        ]

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, results)

        # Read file
        summary_file = output.directory / "summary.md"
        content = summary_file.read_text()

        assert "émojis 🎉" in content

    def test_write_episode_special_characters_in_title(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test handling special characters in episode title."""
        episode_metadata.episode_title = 'Episode: "Testing" & <More>'

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory (special chars cleaned)
        assert output.directory.exists()

    def test_write_episode_very_long_title(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test handling very long episode titles."""
        episode_metadata.episode_title = "x" * 300

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory with truncated name
        assert output.directory.exists()
        assert len(output.directory.name) < 300

    def test_write_episode_empty_results(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
    ) -> None:
        """Test writing episode with no extraction results."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, [])

        # Should still create directory and metadata
        assert output.directory.exists()
        assert output.metadata_file.exists()
        assert len(output.output_files) == 0
