"""File output manager for writing extraction results to disk.

Handles directory creation, atomic file writes, and metadata generation.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..extraction.models import ExtractionResult
from ..utils.errors import SecurityError
from ..utils.yaml_integrity import YAMLWithIntegrity
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
    - Schema versioning and migrations

    Example:
        >>> manager = OutputManager(output_dir=Path("./output"))
        >>> output = manager.write_episode(
        ...     episode_metadata,
        ...     extraction_results
        ... )
        >>> print(output.directory)
        ./output/podcast-name-2025-11-07-episode-title/
    """

    CURRENT_METADATA_SCHEMA_VERSION = 1

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
        # Pre-calculate episode directory path for backup tracking
        episode_dir = self._get_episode_directory_path(episode_metadata)
        backup_dir = None

        # Track backup directory if overwriting existing episode
        if overwrite and episode_dir.exists():
            backup_dir = episode_dir.with_suffix(".backup")

        try:
            # Create episode directory (handles backup internally)
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

            # Success - remove backup if it exists
            if backup_dir and backup_dir.exists():
                logger.debug(f"Removing backup after successful write: {backup_dir}")
                shutil.rmtree(backup_dir)

            return EpisodeOutput(
                metadata=episode_metadata,
                output_dir=episode_dir,
                files=output_files,
            )

        except Exception:
            # Restore backup on ANY failure during write operation
            if backup_dir and backup_dir.exists():
                logger.warning(f"Write failed, restoring backup from {backup_dir} to {episode_dir}")
                # Clean up partial episode directory if it exists
                if episode_dir.exists():
                    shutil.rmtree(episode_dir)
                # Restore backup to original location
                backup_dir.rename(episode_dir)
            raise

    def _get_episode_directory_path(self, episode_metadata: EpisodeMetadata) -> Path:
        """Get episode directory path without creating it.

        This is a helper to calculate the directory path before creating it,
        useful for backup tracking in write_episode().

        Structure: output_dir/podcast-slug/YYYY-MM-DD-episode-slug/

        Args:
            episode_metadata: Episode metadata

        Returns:
            Path to episode directory (may not exist yet)
        """
        # Sanitize each path component separately
        podcast_slug = self._sanitize_path_component(episode_metadata.podcast_slug)
        episode_slug = self._sanitize_path_component(episode_metadata.episode_slug)

        if not podcast_slug.strip() or not episode_slug.strip():
            raise ValueError("Episode directory path is empty after sanitization")

        return self.output_dir / podcast_slug / episode_slug

    def _sanitize_path_component(self, component: str) -> str:
        """Sanitize a single path component (no slashes allowed).

        Args:
            component: Path component to sanitize

        Returns:
            Sanitized path component
        """
        # Remove path traversal sequences and path separators
        sanitized = component.replace("..", "").replace("/", "-").replace("\\", "-")
        # Remove null bytes (path injection)
        sanitized = sanitized.replace("\0", "")
        return sanitized

    def _create_episode_directory(self, episode_metadata: EpisodeMetadata, overwrite: bool) -> Path:
        """Create episode directory with comprehensive security checks.

        This method implements defense-in-depth path traversal protection:
        1. Sanitizes directory names to remove traversal sequences
        2. Validates resolved paths stay within output directory
        3. Prevents symlink attacks
        4. Validates overwrite targets are episode directories
        5. Creates backups before overwrite with rollback support

        Structure: output_dir/podcast-slug/YYYY-MM-DD-episode-slug/

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
        # Step 1: Sanitize each path component
        podcast_slug = self._sanitize_path_component(episode_metadata.podcast_slug)
        episode_slug = self._sanitize_path_component(episode_metadata.episode_slug)

        # Step 2: Ensure not empty after sanitization
        if not podcast_slug.strip() or not episode_slug.strip():
            raise ValueError("Episode directory path is empty after sanitization")

        # Build the nested path: output_dir/podcast-slug/episode-slug
        podcast_dir = self.output_dir / podcast_slug
        episode_dir = podcast_dir / episode_slug

        # Step 3: Verify resolved path is within output_dir
        try:
            resolved_episode = episode_dir.resolve()
            resolved_output = self.output_dir.resolve()
            resolved_episode.relative_to(resolved_output)
        except ValueError:
            raise SecurityError(
                f"Invalid directory path: {podcast_slug}/{episode_slug}. "
                f"Resolved path {resolved_episode} is outside output directory."
            ) from None

        # Step 4: Check it's not a symlink (symlink attack)
        if episode_dir.exists() and episode_dir.is_symlink():
            raise SecurityError(
                f"Episode directory {episode_dir} is a symlink. "
                f"Refusing to use for security reasons."
            )

        # Step 5: Handle overwrite with validation
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
            backup_dir = episode_dir.with_suffix(".backup")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            episode_dir.rename(backup_dir)

            # Create new directory (parents=True ensures podcast dir exists)
            episode_dir.mkdir(parents=True)
        else:
            # Create both podcast and episode directories if needed
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
        temp_fd, temp_path = tempfile.mkstemp(dir=file_path.parent, prefix=".tmp_", suffix=".md")

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
        """Write metadata file with schema version and integrity checksum.

        Args:
            metadata_file: Path to metadata file
            episode_metadata: Episode metadata
        """
        # Convert to dict
        metadata_dict = episode_metadata.model_dump()

        # Ensure schema_version is set (should be set by model default, but be explicit)
        if "schema_version" not in metadata_dict or metadata_dict["schema_version"] is None:
            metadata_dict["schema_version"] = self.CURRENT_METADATA_SCHEMA_VERSION

        # Write with integrity checksum via atomic write (temp file + rename)
        YAMLWithIntegrity.write_yaml_with_checksum(metadata_file, metadata_dict)

    def list_episodes(self) -> list[Path]:
        """List all episode directories.

        Looks for episode directories in the nested structure:
        output_dir/podcast-slug/episode-slug/.metadata.yaml

        Returns:
            List of episode directory paths
        """
        episodes = []

        # Iterate through podcast directories
        for podcast_dir in self.output_dir.iterdir():
            if not podcast_dir.is_dir():
                continue

            # Look for episode directories inside each podcast directory
            for episode_dir in podcast_dir.iterdir():
                if episode_dir.is_dir() and (episode_dir / ".metadata.yaml").exists():
                    episodes.append(episode_dir)

        return sorted(episodes)

    def load_episode_metadata(self, episode_dir: Path) -> EpisodeMetadata:
        """Load episode metadata from directory with automatic migration.

        Handles schema versioning by automatically migrating old metadata
        to the current schema version.

        Args:
            episode_dir: Episode directory path

        Returns:
            EpisodeMetadata with current schema version

        Raises:
            FileNotFoundError: If metadata file doesn't exist
        """
        metadata_file = episode_dir / ".metadata.yaml"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        # Load with integrity verification
        data = YAMLWithIntegrity.read_yaml_with_verification(metadata_file)

        # Handle schema migrations
        schema_version = data.get("schema_version", 0)

        if schema_version == 0:
            # Migrate v0 (no version) -> v1
            data = self._migrate_metadata_v0_to_v1(data)
            logger.info(f"Migrated {metadata_file} from schema v0 to v1")
            schema_version = 1

        # Warn if metadata is from a newer version
        if schema_version > self.CURRENT_METADATA_SCHEMA_VERSION:
            logger.warning(
                f"Metadata schema version {schema_version} is newer than supported "
                f"version {self.CURRENT_METADATA_SCHEMA_VERSION}. "
                f"Some fields may be missing or incompatible."
            )

        return EpisodeMetadata(**data)

    def _migrate_metadata_v0_to_v1(self, data: dict) -> dict:
        """Migrate metadata from v0 (no version) to v1.

        This handles backward compatibility with metadata files created
        before schema versioning was implemented.

        Args:
            data: Metadata dictionary without schema_version

        Returns:
            Migrated metadata dictionary with schema_version = 1
        """
        # Add schema version
        data["schema_version"] = 1

        # v0 -> v1 had no field changes, just added versioning
        # Future migrations might need to:
        # - Add new fields with defaults
        # - Rename existing fields
        # - Transform field values

        return data

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
        total_files = sum(len(list(ep.glob("*.md"))) for ep in episodes)
        total_size = self.get_total_size()

        return {
            "total_episodes": len(episodes),
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
