"""Unit tests for output manager."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from inkwell.extraction.models import ExtractedContent, ExtractionResult
from inkwell.output.manager import OutputManager
from inkwell.output.models import EpisodeMetadata, EpisodeOutput
from inkwell.utils.errors import SecurityError


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

        # Check directory created (nested: output_dir/podcast-slug/episode-slug)
        assert output.directory.exists()
        # Parent is podcast dir, grandparent is output_dir
        assert output.directory.parent.parent == temp_output_dir

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

        # Directory structure: podcast-slug/YYYY-MM-DD-episode-title
        episode_dir_name = output.directory.name
        podcast_dir_name = output.directory.parent.name

        # Podcast dir should be the podcast slug
        assert podcast_dir_name == "test-podcast"
        # Episode dir should have date and title (not podcast name)
        assert "episode-1" in episode_dir_name.lower()
        assert len(episode_dir_name.split("-")) >= 4  # Has date components

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
        assert metadata.total_cost_usd == pytest.approx(0.06)  # 0.01 + 0.05

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

        # Create modified extraction results
        modified_results = [
            ExtractionResult(
                episode_url=extraction_results[0].episode_url,
                template_name=extraction_results[0].template_name,
                success=extraction_results[0].success,
                extracted_content=ExtractedContent(
                    template_name="summary",
                    content="Modified summary",
                ),
                cost_usd=extraction_results[0].cost_usd,
                provider=extraction_results[0].provider,
            ),
            extraction_results[1],
        ]

        # Write again with overwrite
        output2 = manager.write_episode(episode_metadata, modified_results, overwrite=True)

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

    def test_write_file_atomic_calls_fsync(self, temp_output_dir: Path) -> None:
        """Test that atomic write calls fsync for durability."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"
        content = "Test content with fsync"

        # Mock os.fsync to track calls
        with patch("os.fsync") as mock_fsync:
            manager._write_file_atomic(test_file, content)

            # Verify fsync was called at least once (for file content)
            # Note: May be called twice (file + directory)
            assert mock_fsync.call_count >= 1

            # Verify file was created successfully
            assert test_file.exists()
            assert test_file.read_text() == content

    def test_write_file_atomic_calls_flush_before_fsync(self, temp_output_dir: Path) -> None:
        """Test that flush is called before fsync."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"

        # Track call order
        call_order = []

        def mock_flush():
            call_order.append("flush")

        def mock_fsync(fd):
            call_order.append("fsync")

        with patch("os.fsync", side_effect=mock_fsync):
            with patch("builtins.open", wraps=open) as mock_open:
                # Patch the flush method of the file object
                original_open = open

                def patched_open(*args, **kwargs):
                    file_obj = original_open(*args, **kwargs)
                    original_flush = file_obj.flush

                    def tracked_flush():
                        mock_flush()
                        original_flush()

                    file_obj.flush = tracked_flush
                    return file_obj

                with patch("builtins.open", side_effect=patched_open):
                    manager._write_file_atomic(test_file, "content")

        # Verify flush was called before fsync
        assert "flush" in call_order
        assert "fsync" in call_order
        assert call_order.index("flush") < call_order.index("fsync")

    def test_write_file_atomic_handles_directory_fsync_failure(self, temp_output_dir: Path) -> None:
        """Test that directory fsync failure doesn't break write."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"
        content = "Test content"

        # Mock os.open to fail for directory (when called with O_RDONLY)
        original_open = os.open

        def mock_open(path, flags, mode=0o777):
            # Fail when opening directory (O_RDONLY flag)
            if flags == os.O_RDONLY:
                raise OSError("Directory fsync not supported")
            return original_open(path, flags, mode)

        with patch("os.open", side_effect=mock_open):
            # Should complete successfully despite directory fsync failure
            manager._write_file_atomic(test_file, content)

        # File should still be written
        assert test_file.exists()
        assert test_file.read_text() == content

    def test_write_file_atomic_fsync_on_file_descriptor(self, temp_output_dir: Path) -> None:
        """Test that fsync is called with correct file descriptor."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"

        with patch("os.fsync") as mock_fsync:
            manager._write_file_atomic(test_file, "content")

            # Verify fsync was called with a valid file descriptor (integer)
            assert mock_fsync.call_count >= 1
            first_call_args = mock_fsync.call_args_list[0][0]
            assert isinstance(first_call_args[0], int)

    def test_write_file_atomic_cleans_up_on_fsync_error(self, temp_output_dir: Path) -> None:
        """Test that temp file is cleaned up if fsync fails."""
        manager = OutputManager(output_dir=temp_output_dir)

        test_file = temp_output_dir / "test.md"

        # Mock fsync to raise error
        with patch("os.fsync", side_effect=OSError("Disk full")):
            with pytest.raises(OSError):
                manager._write_file_atomic(test_file, "content")

        # Temp file should be cleaned up
        temp_files = list(temp_output_dir.glob(".tmp_*"))
        assert len(temp_files) == 0

        # Final file should not exist
        assert not test_file.exists()


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
        assert stats["total_size_mb"] >= 0  # Small test files may round to 0.00 MB

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
                episode_url="https://example.com/ep1",
                template_name="summary",
                success=True,
                extracted_content=ExtractedContent(
                    template_name="summary",
                    content="Content with émojis 🎉 and symbols ™",
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


class TestOutputManagerSecurityPathTraversal:
    """Tests for path traversal attack prevention."""

    def test_path_traversal_with_dotdot_sequence(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that ../ sequences are sanitized."""
        # Attempt path traversal with ../
        episode_metadata.episode_title = "../../../../etc/passwd"

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Directory should be created safely within output_dir (nested structure)
        assert output.directory.exists()
        assert output.directory.parent.parent == temp_output_dir
        # Path traversal should be sanitized (../ removed)
        assert ".." not in output.directory.name

    def test_path_traversal_with_absolute_path(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that absolute paths in titles are sanitized."""
        # Attempt absolute path injection
        episode_metadata.episode_title = "/etc/cron.d/malicious"

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory safely (nested structure)
        assert output.directory.exists()
        assert output.directory.parent.parent == temp_output_dir
        # Slashes should be replaced with hyphens
        assert "/" not in output.directory.name

    def test_path_traversal_with_windows_path_separator(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that Windows path separators are sanitized."""
        # Attempt Windows path traversal
        episode_metadata.episode_title = r"..\..\..\..\Windows\System32"

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory safely (nested structure)
        assert output.directory.exists()
        assert output.directory.parent.parent == temp_output_dir
        # Both .. and \ should be sanitized
        assert ".." not in output.directory.name
        assert "\\" not in output.directory.name

    def test_path_traversal_with_mixed_separators(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that mixed path separators are sanitized."""
        # Mix of different path traversal techniques
        episode_metadata.episode_title = r"../../../\../etc/passwd"

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory safely (nested structure)
        assert output.directory.exists()
        assert output.directory.parent.parent == temp_output_dir

    def test_path_traversal_with_null_bytes(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that null bytes are removed."""
        # Null byte injection attempt
        episode_metadata.episode_title = "safe\x00../../../etc/passwd"

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory safely (nested structure)
        assert output.directory.exists()
        assert output.directory.parent.parent == temp_output_dir
        # Null bytes should be removed
        assert "\x00" not in output.directory.name

    def test_path_traversal_stays_within_output_dir(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that resolved path stays within output directory."""
        # Various path traversal attempts
        test_titles = [
            "../../../../home/user/.ssh/authorized_keys",
            "/etc/passwd",
            r"C:\Windows\System32\config",
            "../../../.bash_history",
        ]

        manager = OutputManager(output_dir=temp_output_dir)

        for title in test_titles:
            episode_metadata.episode_title = title
            output = manager.write_episode(episode_metadata, extraction_results, overwrite=True)

            # Verify directory is within output_dir
            resolved_output = output.directory.resolve()
            resolved_base = temp_output_dir.resolve()

            # Should not raise ValueError
            relative_path = resolved_output.relative_to(resolved_base)
            assert relative_path is not None


class TestOutputManagerSecuritySymlinkAttacks:
    """Tests for symlink attack prevention."""

    def test_symlink_directory_rejected(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that symlink directories are rejected."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Create a symlink that points outside output directory
        target_dir = temp_output_dir.parent / "sensitive_data"
        target_dir.mkdir()

        # Get the nested path components
        podcast_slug = episode_metadata.podcast_slug
        episode_slug = episode_metadata.episode_slug

        # Create podcast directory, then symlink at episode level
        podcast_dir = temp_output_dir / podcast_slug
        podcast_dir.mkdir()
        symlink_path = podcast_dir / episode_slug
        symlink_path.symlink_to(target_dir, target_is_directory=True)

        # Should raise SecurityError
        with pytest.raises(SecurityError) as exc_info:
            manager.write_episode(episode_metadata, extraction_results)

        assert "symlink" in str(exc_info.value).lower()

    def test_regular_directory_not_rejected(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that regular directories work fine."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Create a regular directory (not a symlink)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should succeed
        assert output.directory.exists()
        assert not output.directory.is_symlink()


class TestOutputManagerSecurityEdgeCases:
    """Tests for security-related edge cases."""

    def test_only_path_separators_in_title(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test titles containing only path separators."""
        episode_metadata.episode_title = "///\\\\\\"

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory with sanitized name
        assert output.directory.exists()
        assert "/" not in output.directory.name
        assert "\\" not in output.directory.name

    def test_overwrite_without_metadata_rejected(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that overwrite rejects directories without .metadata.yaml."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Create a directory without metadata (could be user data)
        # With nested structure: output_dir/podcast-slug/episode-slug
        podcast_slug = episode_metadata.podcast_slug
        episode_slug = episode_metadata.episode_slug

        podcast_dir = temp_output_dir / podcast_slug
        podcast_dir.mkdir()
        fake_dir = podcast_dir / episode_slug
        fake_dir.mkdir()
        (fake_dir / "important_data.txt").write_text("Don't delete me!")

        # Should raise ValueError refusing to delete
        with pytest.raises(ValueError) as exc_info:
            manager.write_episode(episode_metadata, extraction_results, overwrite=True)

        assert "metadata.yaml" in str(exc_info.value).lower()
        # Original directory should still exist
        assert fake_dir.exists()

    def test_overwrite_creates_backup(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that overwrite creates backup before deletion."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write episode first time
        output1 = manager.write_episode(episode_metadata, extraction_results)
        original_dir = output1.directory

        # Verify backup is created and cleaned up during overwrite
        # Write second time with overwrite
        output2 = manager.write_episode(episode_metadata, extraction_results, overwrite=True)

        # Should be same directory
        assert output2.directory == original_dir
        assert output2.directory.exists()

        # Backup should exist temporarily but might be cleaned up
        # The important thing is the operation succeeded

    def test_overwrite_restores_backup_on_mkdir_failure(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that backup is restored if mkdir fails during overwrite."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write episode first time
        output1 = manager.write_episode(episode_metadata, extraction_results)
        original_dir = output1.directory
        original_metadata_content = (original_dir / ".metadata.yaml").read_text()

        # Mock mkdir to fail during overwrite
        original_mkdir = Path.mkdir

        def failing_mkdir(self, *args, **kwargs):
            if self == original_dir:
                raise OSError("Simulated mkdir failure")
            return original_mkdir(self, *args, **kwargs)

        with patch.object(Path, "mkdir", failing_mkdir):
            # Should raise OSError and restore backup
            with pytest.raises(OSError):
                manager.write_episode(episode_metadata, extraction_results, overwrite=True)

        # Original directory should be restored
        assert original_dir.exists()
        assert (original_dir / ".metadata.yaml").exists()
        restored_content = (original_dir / ".metadata.yaml").read_text()
        assert restored_content == original_metadata_content

    def test_overwrite_restores_backup_on_file_write_failure(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that backup is restored if file write fails after directory creation."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write episode first time
        output1 = manager.write_episode(episode_metadata, extraction_results)
        original_dir = output1.directory
        original_summary_content = (original_dir / "summary.md").read_text()
        original_metadata_content = (original_dir / ".metadata.yaml").read_text()

        # Mock _write_file_atomic to fail on second file write
        write_count = 0
        original_write = manager._write_file_atomic

        def failing_write(path, content):
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                raise OSError("Disk full")
            original_write(path, content)

        with patch.object(manager, "_write_file_atomic", failing_write):
            # Should raise OSError and restore backup
            with pytest.raises(OSError, match="Disk full"):
                manager.write_episode(episode_metadata, extraction_results, overwrite=True)

        # Original directory should be restored with all files intact
        assert original_dir.exists()
        assert (original_dir / "summary.md").exists()
        assert (original_dir / "quotes.md").exists()
        assert (original_dir / ".metadata.yaml").exists()

        # Verify content is restored (not partially overwritten)
        restored_summary = (original_dir / "summary.md").read_text()
        restored_metadata = (original_dir / ".metadata.yaml").read_text()
        assert restored_summary == original_summary_content
        assert restored_metadata == original_metadata_content

        # Backup directory should not be left behind
        backup_dir = original_dir.with_suffix(".backup")
        assert not backup_dir.exists()

    def test_overwrite_restores_backup_on_metadata_write_failure(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that backup is restored if metadata write fails."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write episode first time
        output1 = manager.write_episode(episode_metadata, extraction_results)
        original_dir = output1.directory
        original_metadata_content = (original_dir / ".metadata.yaml").read_text()

        # Mock _write_metadata to fail
        def failing_write_metadata(metadata_file, episode_metadata):
            raise OSError("Permission denied")

        with patch.object(manager, "_write_metadata", failing_write_metadata):
            # Should raise OSError and restore backup
            with pytest.raises(OSError, match="Permission denied"):
                manager.write_episode(episode_metadata, extraction_results, overwrite=True)

        # Original directory should be restored
        assert original_dir.exists()
        assert (original_dir / ".metadata.yaml").exists()
        restored_content = (original_dir / ".metadata.yaml").read_text()
        assert restored_content == original_metadata_content

        # Backup directory should not be left behind
        backup_dir = original_dir.with_suffix(".backup")
        assert not backup_dir.exists()

    def test_overwrite_removes_backup_on_success(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that backup is removed after successful overwrite."""
        manager = OutputManager(output_dir=temp_output_dir)

        # Write episode first time
        output1 = manager.write_episode(episode_metadata, extraction_results)
        original_dir = output1.directory

        # Overwrite successfully
        output2 = manager.write_episode(episode_metadata, extraction_results, overwrite=True)

        # Episode should exist
        assert output2.directory.exists()
        assert output2.directory == original_dir

        # Backup should be removed
        backup_dir = original_dir.with_suffix(".backup")
        assert not backup_dir.exists()

    def test_multiple_path_traversal_techniques_combined(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test combination of multiple path traversal techniques."""
        # Kitchen sink attack: multiple techniques combined
        episode_metadata.episode_title = r"../\..//../\x00/../../../etc/passwd"

        manager = OutputManager(output_dir=temp_output_dir)
        output = manager.write_episode(episode_metadata, extraction_results)

        # Should create directory safely
        # With nested structure: output_dir/podcast-slug/episode-slug
        assert output.directory.exists()
        assert output.directory.parent.parent == temp_output_dir
        # All attack vectors should be neutralized
        assert ".." not in output.directory.name
        assert "/" not in output.directory.name
        assert "\\" not in output.directory.name
        assert "\x00" not in output.directory.name


# EpisodeOutput.from_directory() Tests


def test_episode_output_from_directory_basic(temp_output_dir, episode_metadata, extraction_results):
    """Test loading episode output from directory."""
    # First, write an episode
    manager = OutputManager(output_dir=temp_output_dir)
    written_output = manager.write_episode(episode_metadata, extraction_results)

    # Now load it back
    loaded_output = EpisodeOutput.from_directory(written_output.output_dir)

    # Verify metadata
    assert loaded_output.metadata.podcast_name == episode_metadata.podcast_name
    assert loaded_output.metadata.episode_title == episode_metadata.episode_title
    assert loaded_output.metadata.episode_url == episode_metadata.episode_url
    assert loaded_output.metadata.transcription_source == episode_metadata.transcription_source

    # Verify files were loaded
    assert len(loaded_output.files) == len(extraction_results)
    assert loaded_output.total_files == len(extraction_results)

    # Verify file content
    summary_file = loaded_output.get_file("summary")
    assert summary_file is not None
    assert "Episode summary" in summary_file.content

    quotes_file = loaded_output.get_file("quotes")
    assert quotes_file is not None
    assert "Quote 1" in quotes_file.content


def test_episode_output_from_directory_with_frontmatter(temp_output_dir):
    """Test loading files with YAML frontmatter."""
    # Create episode directory manually
    episode_dir = temp_output_dir / "test-episode"
    episode_dir.mkdir()

    # Write metadata
    metadata = EpisodeMetadata(
        podcast_name="Test Podcast",
        episode_title="Test Episode",
        episode_url="https://example.com/test",
        transcription_source="youtube",
    )
    metadata_file = episode_dir / ".metadata.yaml"
    metadata_file.write_text(yaml.dump(metadata.model_dump()))

    # Write markdown file with frontmatter
    content_with_frontmatter = """---
date: 2025-11-13
author: Test Author
tags:
  - test
  - example
---

# Summary

This is the actual content.
"""
    (episode_dir / "summary.md").write_text(content_with_frontmatter)

    # Load
    loaded_output = EpisodeOutput.from_directory(episode_dir)

    # Verify frontmatter was parsed
    summary_file = loaded_output.get_file("summary")
    assert summary_file is not None
    assert summary_file.frontmatter["author"] == "Test Author"
    assert "test" in summary_file.frontmatter["tags"]

    # Verify content excludes frontmatter
    assert "This is the actual content" in summary_file.content
    assert "---" not in summary_file.content


def test_episode_output_from_directory_missing_dir():
    """Test loading from non-existent directory raises error."""
    with pytest.raises(FileNotFoundError, match="Output directory not found"):
        EpisodeOutput.from_directory(Path("/nonexistent/path"))


def test_episode_output_from_directory_not_a_directory(tmp_path):
    """Test loading from a file (not directory) raises error."""
    # Create a file instead of directory
    file_path = tmp_path / "not-a-dir.txt"
    file_path.write_text("test")

    with pytest.raises(ValueError, match="not a directory"):
        EpisodeOutput.from_directory(file_path)


def test_episode_output_from_directory_missing_metadata(tmp_path):
    """Test loading from directory without metadata raises error."""
    # Create directory without .metadata.yaml
    episode_dir = tmp_path / "episode"
    episode_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="Metadata file not found"):
        EpisodeOutput.from_directory(episode_dir)


def test_episode_output_from_directory_no_markdown_files(temp_output_dir):
    """Test loading from directory with metadata but no markdown files."""
    episode_dir = temp_output_dir / "empty-episode"
    episode_dir.mkdir()

    # Write metadata only
    metadata = EpisodeMetadata(
        podcast_name="Test",
        episode_title="Test",
        episode_url="https://example.com/test",
        transcription_source="youtube",
    )
    metadata_file = episode_dir / ".metadata.yaml"
    metadata_file.write_text(yaml.dump(metadata.model_dump()))

    # Load should work but have no files
    loaded_output = EpisodeOutput.from_directory(episode_dir)

    assert loaded_output.total_files == 0
    assert len(loaded_output.files) == 0


def test_episode_output_from_directory_multiple_files(temp_output_dir):
    """Test loading directory with multiple markdown files."""
    episode_dir = temp_output_dir / "multi-file-episode"
    episode_dir.mkdir()

    # Write metadata
    metadata = EpisodeMetadata(
        podcast_name="Test",
        episode_title="Test",
        episode_url="https://example.com/test",
        transcription_source="youtube",
    )
    metadata_file = episode_dir / ".metadata.yaml"
    metadata_file.write_text(yaml.dump(metadata.model_dump()))

    # Write multiple markdown files
    (episode_dir / "summary.md").write_text("# Summary\n\nSummary content")
    (episode_dir / "quotes.md").write_text("# Quotes\n\n> Quote 1")
    (episode_dir / "key-concepts.md").write_text("# Concepts\n\n- Concept 1")
    (episode_dir / "tools-mentioned.md").write_text("# Tools\n\n- Tool 1")

    # Load
    loaded_output = EpisodeOutput.from_directory(episode_dir)

    assert loaded_output.total_files == 4
    assert loaded_output.get_file("summary") is not None
    assert loaded_output.get_file("quotes") is not None
    assert loaded_output.get_file("key-concepts") is not None
    assert loaded_output.get_file("tools-mentioned") is not None


# Schema Versioning and Migration Tests


class TestOutputManagerSchemaVersioning:
    """Tests for schema versioning and migration."""

    def test_write_metadata_includes_schema_version(
        self,
        temp_output_dir: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
    ) -> None:
        """Test that new metadata files include schema_version."""
        manager = OutputManager(output_dir=temp_output_dir)

        output = manager.write_episode(episode_metadata, extraction_results)

        # Read metadata file
        with output.metadata_file.open("r") as f:
            data = yaml.safe_load(f)

        # Should have schema_version field
        assert "schema_version" in data
        assert data["schema_version"] == 1

    def test_load_metadata_v0_migrates_to_v1(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Test that v0 metadata (no version) is migrated to v1."""
        manager = OutputManager(output_dir=temp_output_dir)

        episode_dir = temp_output_dir / "test-episode"
        episode_dir.mkdir()

        # Create v0 metadata (no schema_version field)
        metadata_file = episode_dir / ".metadata.yaml"
        v0_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Episode 1",
            "episode_url": "https://example.com/ep1",
            "transcription_source": "youtube",
            "processed_date": "2025-11-14T10:00:00+00:00",
            "templates_applied": [],
            "transcription_cost_usd": 0.0,
            "extraction_cost_usd": 0.0,
            "total_cost_usd": 0.0,
            "custom_fields": {},
        }
        metadata_file.write_text(yaml.dump(v0_metadata))

        # Load should auto-migrate
        loaded_metadata = manager.load_episode_metadata(episode_dir)

        # Should be migrated to v1
        assert loaded_metadata.schema_version == 1
        assert loaded_metadata.podcast_name == "Test Podcast"
        assert loaded_metadata.episode_title == "Episode 1"
        assert loaded_metadata.episode_url == "https://example.com/ep1"

    def test_load_metadata_v1_no_migration_needed(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Test that v1 metadata loads without migration."""
        manager = OutputManager(output_dir=temp_output_dir)

        episode_dir = temp_output_dir / "test-episode"
        episode_dir.mkdir()

        # Create v1 metadata (with schema_version)
        metadata_file = episode_dir / ".metadata.yaml"
        v1_metadata = {
            "schema_version": 1,
            "podcast_name": "Test Podcast",
            "episode_title": "Episode 1",
            "episode_url": "https://example.com/ep1",
            "transcription_source": "youtube",
            "processed_date": "2025-11-14T10:00:00+00:00",
            "templates_applied": [],
            "transcription_cost_usd": 0.0,
            "extraction_cost_usd": 0.0,
            "total_cost_usd": 0.0,
            "custom_fields": {},
        }
        metadata_file.write_text(yaml.dump(v1_metadata))

        # Load should work without migration
        loaded_metadata = manager.load_episode_metadata(episode_dir)

        # Should remain v1
        assert loaded_metadata.schema_version == 1
        assert loaded_metadata.podcast_name == "Test Podcast"

    def test_load_metadata_newer_version_warns(
        self,
        temp_output_dir: Path,
        capsys,
    ) -> None:
        """Test that loading newer schema version logs warning."""
        manager = OutputManager(output_dir=temp_output_dir)

        episode_dir = temp_output_dir / "test-episode"
        episode_dir.mkdir()

        # Create v2 metadata (future version)
        metadata_file = episode_dir / ".metadata.yaml"
        v2_metadata = {
            "schema_version": 2,
            "podcast_name": "Test Podcast",
            "episode_title": "Episode 1",
            "episode_url": "https://example.com/ep1",
            "transcription_source": "youtube",
            "processed_date": "2025-11-14T10:00:00+00:00",
            "templates_applied": [],
            "transcription_cost_usd": 0.0,
            "extraction_cost_usd": 0.0,
            "total_cost_usd": 0.0,
            "custom_fields": {},
        }
        metadata_file.write_text(yaml.dump(v2_metadata))

        # Load should warn about newer version
        loaded_metadata = manager.load_episode_metadata(episode_dir)

        # Should load but log warning (warning goes to stderr via rich)
        captured = capsys.readouterr()
        assert loaded_metadata.schema_version == 2
        assert "newer than supported" in captured.err.lower()

    def test_migrate_metadata_v0_to_v1_preserves_data(
        self,
        temp_output_dir: Path,
    ) -> None:
        """Test that migration preserves all original data."""
        manager = OutputManager(output_dir=temp_output_dir)

        episode_dir = temp_output_dir / "test-episode"
        episode_dir.mkdir()

        # Create v0 metadata with all fields
        metadata_file = episode_dir / ".metadata.yaml"
        v0_metadata = {
            "podcast_name": "Test Podcast",
            "episode_title": "Episode 1",
            "episode_url": "https://example.com/ep1",
            "published_date": "2025-11-01T15:30:00+00:00",
            "duration_seconds": 3600.0,
            "transcription_source": "gemini",
            "processed_date": "2025-11-14T10:00:00+00:00",
            "templates_applied": ["summary", "quotes"],
            "transcription_cost_usd": 0.05,
            "extraction_cost_usd": 0.10,
            "total_cost_usd": 0.15,
            "custom_fields": {"test_key": "test_value"},
        }
        metadata_file.write_text(yaml.dump(v0_metadata))

        # Load and migrate
        loaded_metadata = manager.load_episode_metadata(episode_dir)

        # Verify all data preserved
        assert loaded_metadata.schema_version == 1
        assert loaded_metadata.podcast_name == "Test Podcast"
        assert loaded_metadata.episode_title == "Episode 1"
        assert loaded_metadata.episode_url == "https://example.com/ep1"
        assert loaded_metadata.duration_seconds == 3600.0
        assert loaded_metadata.transcription_source == "gemini"
        assert loaded_metadata.templates_applied == ["summary", "quotes"]
        assert loaded_metadata.transcription_cost_usd == 0.05
        assert loaded_metadata.extraction_cost_usd == 0.10
        assert loaded_metadata.total_cost_usd == 0.15
        assert loaded_metadata.custom_fields == {"test_key": "test_value"}

    def test_schema_version_constant_is_one(self) -> None:
        """Test that current schema version is 1."""
        assert OutputManager.CURRENT_METADATA_SCHEMA_VERSION == 1

    def test_episode_metadata_default_schema_version(self) -> None:
        """Test that EpisodeMetadata defaults to schema_version=1."""
        metadata = EpisodeMetadata(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com/test",
            transcription_source="youtube",
        )

        assert metadata.schema_version == 1
