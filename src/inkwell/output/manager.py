"""File output manager for writing extraction results to disk.

Handles directory creation, atomic file writes, and metadata generation.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ..extraction.models import ExtractionResult
from ..utils.errors import SecurityError
from .markdown import MarkdownGenerator
from .models import EpisodeMetadata, EpisodeOutput, OutputFile

logger = logging.getLogger(__name__)


class OutputManager:
    """Manage file output for extraction results.

    Handles:
    - Directory creation (episode-based structure)
    - Atomic file writes (write to temp, then move)
    - Metadata file generation
    - File conflict resolution

    Example:
        >>> manager = OutputManager(output_dir=Path("./output"))
        >>> output = manager.write_episode(
        ...     episode_metadata,
        ...     extraction_results
        ... )
        >>> print(output.directory)
        ./output/podcast-name-2025-11-07-episode-title/
    """

    def __init__(self, output_dir: Path, markdown_generator: MarkdownGenerator | None = None):
        """Initialize output manager.

        Args:
            output_dir: Base output directory
            markdown_generator: MarkdownGenerator instance (creates one if None)
        """
        self.output_dir = output_dir
        self.markdown_generator = markdown_generator or MarkdownGenerator()

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_episode(
        self,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
        overwrite: bool = False,
    ) -> EpisodeOutput:
        """Write extraction results for an episode to disk.

        Args:
            episode_metadata: Episode metadata
            extraction_results: List of extraction results
            overwrite: Whether to overwrite existing directory

        Returns:
            EpisodeOutput with directory and file information

        Raises:
            FileExistsError: If directory exists and overwrite=False
        """
        # Create episode directory
        episode_dir = self._create_episode_directory(episode_metadata, overwrite)

        # Write markdown files
        output_files = []
        total_cost = 0.0

        for result in extraction_results:
            # Generate markdown
            markdown_content = self.markdown_generator.generate(
                result,
                episode_metadata.model_dump(),
                include_frontmatter=True,
            )

            # Write file
            filename = f"{result.template_name}.md"
            file_path = episode_dir / filename

            self._write_file_atomic(file_path, markdown_content)

            output_files.append(
                OutputFile(
                    template_name=result.template_name,
                    filename=filename,
                    content=markdown_content,
                    size_bytes=len(markdown_content.encode("utf-8")),
                )
            )

            total_cost += result.cost_usd

        # Update metadata with cost
        episode_metadata.total_cost_usd = total_cost
        episode_metadata.templates_applied = [r.template_name for r in extraction_results]

        # Write metadata file
        metadata_file = episode_dir / ".metadata.yaml"
        self._write_metadata(metadata_file, episode_metadata)

        return EpisodeOutput(
            metadata=episode_metadata,
            output_dir=episode_dir,
            files=output_files,
        )

    def _create_episode_directory(
        self, episode_metadata: EpisodeMetadata, overwrite: bool
    ) -> Path:
        """Create episode directory with comprehensive security checks.

        This method implements defense-in-depth path traversal protection:
        1. Sanitizes directory names to remove traversal sequences
        2. Validates resolved paths stay within output directory
        3. Prevents symlink attacks
        4. Validates overwrite targets are episode directories
        5. Creates backups before overwrite with rollback support

        Args:
            episode_metadata: Episode metadata
            overwrite: Whether to overwrite existing directory

        Returns:
            Path to created directory

        Raises:
            FileExistsError: If directory exists and overwrite=False
            SecurityError: If path traversal or symlink attack detected
            ValueError: If directory name is invalid or empty after sanitization
        """
        # Get directory name from metadata
        dir_name = episode_metadata.directory_name

        # Step 1: Sanitize directory name
        # Remove path traversal sequences and path separators
        dir_name = dir_name.replace("..", "").replace("/", "-").replace("\\", "-")

        # Step 2: Remove null bytes (path injection)
        dir_name = dir_name.replace("\0", "")

        # Step 3: Ensure it's not empty after sanitization
        if not dir_name.strip():
            raise ValueError("Episode directory name is empty after sanitization")

        episode_dir = self.output_dir / dir_name

        # Step 4: Verify resolved path is within output_dir
        try:
            resolved_episode = episode_dir.resolve()
            resolved_output = self.output_dir.resolve()
            resolved_episode.relative_to(resolved_output)
        except ValueError:
            raise SecurityError(
                f"Invalid directory path: {dir_name}. "
                f"Resolved path {resolved_episode} is outside output directory."
            )

        # Step 5: Check it's not a symlink (symlink attack)
        if episode_dir.exists() and episode_dir.is_symlink():
            raise SecurityError(
                f"Episode directory {episode_dir} is a symlink. "
                f"Refusing to use for security reasons."
            )

        # Step 6: Handle overwrite with validation
        if episode_dir.exists():
            if not overwrite:
                raise FileExistsError(
                    f"Episode directory already exists: {episode_dir}\n"
                    f"Use --overwrite to replace existing directory."
                )

            # Validate it looks like an episode directory
            if not (episode_dir / ".metadata.yaml").exists():
                raise ValueError(
                    f"Directory {episode_dir} doesn't contain .metadata.yaml. "
                    f"Refusing to delete (may not be an episode directory)."
                )

            # Create backup before deletion
            backup_dir = episode_dir.with_suffix('.backup')
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            episode_dir.rename(backup_dir)

            try:
                episode_dir.mkdir(parents=True)
            except Exception:
                # Restore backup on failure
                if backup_dir.exists() and not episode_dir.exists():
                    backup_dir.rename(episode_dir)
                raise
        else:
            episode_dir.mkdir(parents=True, exist_ok=True)

        return episode_dir

    def _write_file_atomic(self, file_path: Path, content: str) -> None:
        """Write file atomically with guaranteed durability.

        Uses temp file + rename pattern with fsync to ensure data is on disk
        before rename completes. This protects against data loss from power
        failure or system crash.

        The implementation follows these steps:
        1. Write content to temporary file in same directory
        2. Flush Python buffers to OS (f.flush())
        3. Sync OS buffers to disk (os.fsync()) - ensures durability
        4. Atomically rename temp to final (POSIX guarantee)
        5. Sync directory to persist rename (best effort)

        Args:
            file_path: Target file path
            content: File content

        Raises:
            OSError: If write or sync fails
        """
        # Write to temporary file in same directory (ensures same filesystem)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent, prefix=".tmp_", suffix=".md"
        )

        try:
            # Write content to temp file
            with open(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)

                # Flush Python buffers to OS
                f.flush()

                # Sync OS buffers to disk (critical for durability)
                # This ensures data is actually written to disk, not just buffered
                # Without this, power loss could result in empty or corrupt files
                os.fsync(f.fileno())

            # Atomically rename temp to final
            # This is atomic at filesystem level (POSIX guarantee)
            Path(temp_path).replace(file_path)

            # Sync directory to persist the rename operation
            # Without this, the rename might not be durable across power loss
            # This is best effort - some filesystems don't support directory fsync
            try:
                dir_fd = os.open(file_path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, AttributeError) as e:
                # Directory fsync not supported on all platforms/filesystems
                # This is acceptable - the file content is already synced
                logger.debug(f"Directory fsync not supported: {e}")

        except Exception:
            # Clean up temp file on error
            Path(temp_path).unlink(missing_ok=True)
            raise

    def _write_metadata(self, metadata_file: Path, episode_metadata: EpisodeMetadata) -> None:
        """Write metadata file.

        Args:
            metadata_file: Path to metadata file
            episode_metadata: Episode metadata
        """
        # Convert to dict
        metadata_dict = episode_metadata.model_dump()

        # Write as YAML
        content = yaml.dump(metadata_dict, default_flow_style=False, sort_keys=False)

        self._write_file_atomic(metadata_file, content)

    def list_episodes(self) -> list[Path]:
        """List all episode directories.

        Returns:
            List of episode directory paths
        """
        # Find directories with .metadata.yaml
        episodes = []
        for item in self.output_dir.iterdir():
            if item.is_dir() and (item / ".metadata.yaml").exists():
                episodes.append(item)

        return sorted(episodes)

    def load_episode_metadata(self, episode_dir: Path) -> EpisodeMetadata:
        """Load episode metadata from directory.

        Args:
            episode_dir: Episode directory path

        Returns:
            EpisodeMetadata

        Raises:
            FileNotFoundError: If metadata file doesn't exist
        """
        metadata_file = episode_dir / ".metadata.yaml"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        with metadata_file.open("r") as f:
            data = yaml.safe_load(f)

        return EpisodeMetadata(**data)

    def get_total_size(self) -> int:
        """Get total size of output directory in bytes.

        Returns:
            Total size in bytes
        """
        total = 0
        for item in self.output_dir.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    def get_statistics(self) -> dict[str, Any]:
        """Get output directory statistics.

        Returns:
            Dict with statistics
        """
        episodes = self.list_episodes()
        total_files = sum(
            len(list(ep.glob("*.md"))) for ep in episodes
        )
        total_size = self.get_total_size()

        return {
            "total_episodes": len(episodes),
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
