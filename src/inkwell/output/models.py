"""Data models for output generation.

This module defines Pydantic models for:
- Episode metadata (tracking and costs)
- Output files (markdown content)
- Episode output (complete episode result)
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


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

    # Episode information
    podcast_name: str = Field(..., description="Name of the podcast")
    episode_title: str = Field(..., description="Episode title")
    episode_url: str = Field(..., description="Episode URL")
    published_date: Optional[datetime] = Field(
        None, description="When episode was published"
    )
    duration_seconds: Optional[float] = Field(
        None, description="Episode duration in seconds", ge=0
    )

    # Processing metadata
    processed_date: datetime = Field(
        default_factory=datetime.utcnow, description="When episode was processed"
    )
    transcription_source: str = Field(
        ..., description="Transcription source (youtube, gemini, cached)"
    )
    templates_applied: list[str] = Field(
        default_factory=list, description="Templates used for extraction"
    )

    # Cost tracking
    transcription_cost_usd: float = Field(
        0.0, description="Cost of transcription", ge=0
    )
    extraction_cost_usd: float = Field(0.0, description="Cost of extraction", ge=0)
    total_cost_usd: float = Field(0.0, description="Total processing cost", ge=0)

    # Custom metadata
    custom_fields: dict[str, Any] = Field(
        default_factory=dict, description="Custom user metadata"
    )

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
    frontmatter: dict[str, Any] = Field(
        default_factory=dict, description="YAML frontmatter"
    )

    # File metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When file was created"
    )
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

        frontmatter_yaml = yaml.dump(
            self.frontmatter, default_flow_style=False, sort_keys=False
        )
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
    files: list[OutputFile] = Field(
        default_factory=list, description="Generated output files"
    )

    # Stats
    total_files: int = Field(0, description="Number of files generated", ge=0)
    total_size_bytes: int = Field(0, description="Total size of all files", ge=0)

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When output was created"
    )

    def add_file(self, file: OutputFile) -> None:
        """Add output file and update stats."""
        file.update_size()
        self.files.append(file)
        self.total_files = len(self.files)
        self.total_size_bytes = sum(f.size_bytes for f in self.files)

    def get_file(self, template_name: str) -> Optional[OutputFile]:
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

    def get_file_by_name(self, filename: str) -> Optional[OutputFile]:
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
    def directory_name(self) -> str:
        """Get directory name for this episode.

        Format: podcast-name-YYYY-MM-DD-episode-title/

        Returns:
            Filesystem-safe directory name
        """
        import re

        # Slugify podcast name
        podcast_slug = re.sub(r"[^\w\s-]", "", self.metadata.podcast_name.lower())
        podcast_slug = re.sub(r"[-\s]+", "-", podcast_slug).strip("-")

        # Slugify episode title
        title_slug = re.sub(r"[^\w\s-]", "", self.metadata.episode_title.lower())
        title_slug = re.sub(r"[-\s]+", "-", title_slug).strip("-")

        # Truncate if too long
        if len(title_slug) > 50:
            title_slug = title_slug[:50].rstrip("-")

        return f"{podcast_slug}-{self.metadata.date_slug}-{title_slug}"

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
