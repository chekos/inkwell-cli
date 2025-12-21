"""Data models for output generation.

This module defines Pydantic models for:
- Episode metadata (tracking and costs)
- Output files (markdown content)
- Episode output (complete episode result)
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from inkwell.utils.datetime import now_utc


class EpisodeMetadata(BaseModel):
    """Metadata for a podcast episode.

    Stores information about the episode, processing details,
    and cost tracking.

    Example:
        >>> metadata = EpisodeMetadata(
        ...     podcast_name="The Changelog",
        ...     episode_title="Building Better Software",
        ...     episode_url="https://example.com/ep123",
        ...     transcription_source="youtube"
        ... )
    """

    # Schema versioning for forward/backward compatibility
    schema_version: int = Field(
        default=1, description="Metadata schema version for migration support"
    )

    # Episode information
    podcast_name: str = Field(..., description="Name of the podcast")
    episode_title: str = Field(..., description="Episode title")
    episode_url: str = Field(..., description="Episode URL")
    published_date: datetime | None = Field(None, description="When episode was published")
    duration_seconds: float | None = Field(None, description="Episode duration in seconds", ge=0)

    # Processing metadata
    processed_date: datetime = Field(
        default_factory=now_utc, description="When episode was processed"
    )
    transcription_source: str = Field(
        ..., description="Transcription source (youtube, gemini, cached)"
    )
    templates_applied: list[str] = Field(
        default_factory=list, description="Templates used for extraction"
    )

    # Cost tracking
    transcription_cost_usd: float = Field(0.0, description="Cost of transcription", ge=0)
    extraction_cost_usd: float = Field(0.0, description="Cost of extraction", ge=0)
    total_cost_usd: float = Field(0.0, description="Total processing cost", ge=0)

    # Custom metadata
    custom_fields: dict[str, Any] = Field(default_factory=dict, description="Custom user metadata")

    @property
    def duration_formatted(self) -> str:
        """Get formatted duration string (HH:MM:SS)."""
        if self.duration_seconds is None:
            return "Unknown"

        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    @property
    def date_slug(self) -> str:
        """Get date slug for directory name (YYYY-MM-DD)."""
        date = self.published_date or self.processed_date
        return date.strftime("%Y-%m-%d")

    @property
    def podcast_slug(self) -> str:
        """Get podcast name slug for directory structure."""
        import re

        slug = re.sub(r"[^\w\s-]", "", self.podcast_name.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        return slug

    @property
    def episode_slug(self) -> str:
        """Get episode slug (date + title) for directory name."""
        import re

        # Slugify episode title
        title_slug = re.sub(r"[^\w\s-]", "", self.episode_title.lower())
        title_slug = re.sub(r"[-\s]+", "-", title_slug).strip("-")

        # Truncate if too long
        if len(title_slug) > 50:
            title_slug = title_slug[:50].rstrip("-")

        return f"{self.date_slug}-{title_slug}"

    @property
    def directory_name(self) -> str:
        """Get full directory path for this episode.

        Format: podcast-slug/YYYY-MM-DD-episode-title

        Returns:
            Filesystem-safe nested directory path
        """
        return f"{self.podcast_slug}/{self.episode_slug}"

    def add_template(self, template_name: str) -> None:
        """Add template to applied templates list."""
        if template_name not in self.templates_applied:
            self.templates_applied.append(template_name)

    def add_cost(self, extraction_cost: float) -> None:
        """Add extraction cost to total."""
        self.extraction_cost_usd += extraction_cost
        self.total_cost_usd = self.transcription_cost_usd + self.extraction_cost_usd


class OutputFile(BaseModel):
    """Represents a single output markdown file.

    Each template produces one output file containing the
    extracted content formatted as markdown.

    Example:
        >>> file = OutputFile(
        ...     filename="summary.md",
        ...     template_name="summary",
        ...     content="# Summary\\n\\n...",
        ...     frontmatter={"date": "2025-11-07"}
        ... )
    """

    filename: str = Field(..., description="Output filename (e.g., 'summary.md')")
    template_name: str = Field(..., description="Template that generated this file")
    content: str = Field(..., description="Markdown content")
    frontmatter: dict[str, Any] = Field(default_factory=dict, description="YAML frontmatter")

    # File metadata
    created_at: datetime = Field(default_factory=now_utc, description="When file was created")
    size_bytes: int = Field(0, description="File size in bytes", ge=0)

    @property
    def has_frontmatter(self) -> bool:
        """Check if file has frontmatter."""
        return len(self.frontmatter) > 0

    @property
    def full_content(self) -> str:
        """Get full content with frontmatter if present.

        Returns:
            Markdown content with YAML frontmatter if applicable
        """
        if not self.has_frontmatter:
            return self.content

        # Format frontmatter as YAML
        import yaml

        frontmatter_yaml = yaml.dump(self.frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{frontmatter_yaml}---\n\n{self.content}"

    def update_size(self) -> None:
        """Update size_bytes based on current content."""
        self.size_bytes = len(self.full_content.encode("utf-8"))


class EpisodeOutput(BaseModel):
    """Complete output for an episode.

    Represents all output files generated for a podcast episode,
    including metadata and statistics.

    Example:
        >>> output = EpisodeOutput(
        ...     metadata=metadata,
        ...     output_dir=Path("~/podcasts/ep123"),
        ...     files=[summary_file, quotes_file]
        ... )
    """

    metadata: EpisodeMetadata = Field(..., description="Episode metadata")
    output_dir: Path = Field(..., description="Output directory path")
    files: list[OutputFile] = Field(default_factory=list, description="Generated output files")

    # Stats
    total_files: int = Field(0, description="Number of files generated", ge=0)
    total_size_bytes: int = Field(0, description="Total size of all files", ge=0)

    # Timestamps
    created_at: datetime = Field(default_factory=now_utc, description="When output was created")

    def add_file(self, file: OutputFile) -> None:
        """Add output file and update stats."""
        file.update_size()
        self.files.append(file)
        self.total_files = len(self.files)
        self.total_size_bytes = sum(f.size_bytes for f in self.files)

    def get_file(self, template_name: str) -> OutputFile | None:
        """Get output file by template name.

        Args:
            template_name: Name of template to find

        Returns:
            OutputFile if found, None otherwise
        """
        for file in self.files:
            if file.template_name == template_name:
                return file
        return None

    def get_file_by_name(self, filename: str) -> OutputFile | None:
        """Get output file by filename.

        Args:
            filename: Filename to find

        Returns:
            OutputFile if found, None otherwise
        """
        for file in self.files:
            if file.filename == filename:
                return file
        return None

    @property
    def directory(self) -> Path:
        """Get output directory path (backward compatibility alias).

        Returns:
            Output directory path
        """
        return self.output_dir

    @property
    def metadata_file(self) -> Path:
        """Get metadata file path (backward compatibility alias).

        Returns:
            Path to .metadata.yaml file
        """
        return self.output_dir / ".metadata.yaml"

    @property
    def output_files(self) -> list[OutputFile]:
        """Get output files list (backward compatibility alias).

        Returns:
            List of output files
        """
        return self.files

    @property
    def directory_name(self) -> str:
        """Get directory name for this episode.

        Format: podcast-name-YYYY-MM-DD-episode-title/

        Returns:
            Filesystem-safe directory name
        """
        # Delegate to metadata's directory_name property (DRY)
        return self.metadata.directory_name

    @property
    def size_formatted(self) -> str:
        """Get formatted total size string."""
        size = self.total_size_bytes

        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def get_summary(self) -> str:
        """Get human-readable summary of output.

        Returns:
            Summary string with file count, size, and cost
        """
        return (
            f"Generated {self.total_files} files ({self.size_formatted}) "
            f"in {self.directory_name}/ "
            f"(cost: ${self.metadata.total_cost_usd:.3f})"
        )

    @classmethod
    def from_directory(cls, output_dir: Path) -> "EpisodeOutput":
        """Load episode output from directory.

        Reads metadata and all markdown files from an episode output directory.

        Args:
            output_dir: Directory containing episode output files

        Returns:
            EpisodeOutput with loaded metadata and files

        Raises:
            FileNotFoundError: If directory or metadata file doesn't exist
            ValueError: If metadata file is invalid

        Example:
            >>> output = EpisodeOutput.from_directory(
            ...     Path("output/podcast-2025-11-13-episode-title")
            ... )
            >>> print(output.metadata.episode_title)
            >>> print(len(output.files))
        """
        import yaml

        # Check directory exists
        if not output_dir.exists():
            raise FileNotFoundError(f"Output directory not found: {output_dir}")

        if not output_dir.is_dir():
            raise ValueError(f"Path is not a directory: {output_dir}")

        # Load metadata
        metadata_file = output_dir / ".metadata.yaml"
        if not metadata_file.exists():
            raise FileNotFoundError(
                f"Metadata file not found: {metadata_file}. "
                f"Directory may not be an episode output directory."
            )

        with metadata_file.open("r") as f:
            metadata_dict = yaml.safe_load(f)

        metadata = EpisodeMetadata(**metadata_dict)

        # Load all markdown files
        files: list[OutputFile] = []
        for md_file in sorted(output_dir.glob("*.md")):
            # Read file content
            content = md_file.read_text(encoding="utf-8")

            # Parse frontmatter if present
            frontmatter: dict[str, Any] = {}
            file_content = content

            if content.startswith("---\n"):
                # Has frontmatter
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter_yaml = parts[1]
                    file_content = parts[2].lstrip()
                    frontmatter = yaml.safe_load(frontmatter_yaml) or {}

            # Determine template name from filename (remove .md)
            template_name = md_file.stem

            # Create OutputFile
            output_file = OutputFile(
                filename=md_file.name,
                template_name=template_name,
                content=file_content,
                frontmatter=frontmatter,
                created_at=datetime.fromtimestamp(md_file.stat().st_mtime),
                size_bytes=md_file.stat().st_size,
            )

            files.append(output_file)

        # Create EpisodeOutput
        episode_output = cls(
            metadata=metadata,
            output_dir=output_dir,
            files=files,
            total_files=len(files),
            total_size_bytes=sum(f.size_bytes for f in files),
        )

        return episode_output
