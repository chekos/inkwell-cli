"""Data models for podcast episodes and feeds."""

import re
from datetime import datetime

from pydantic import BaseModel, HttpUrl


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a filesystem-safe slug.

    Args:
        text: The text to slugify
        max_length: Maximum length of the slug

    Returns:
        Filesystem-safe slug
    """
    # Convert to lowercase
    text = text.lower()
    # Remove non-alphanumeric characters (keep spaces and hyphens)
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace spaces with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Remove multiple consecutive hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rsplit("-", 1)[0]
    return text


class Episode(BaseModel):
    """Represents a single podcast episode."""

    title: str
    url: HttpUrl  # Direct audio/video URL
    published: datetime
    description: str
    duration_seconds: int | None = None
    podcast_name: str
    episode_number: int | None = None
    season_number: int | None = None
    guid: str | None = None  # Episode unique identifier

    @property
    def slug(self) -> str:
        """Generate filesystem-safe episode identifier.

        Format: podcast-name-YYYY-MM-DD-episode-title

        Returns:
            Slugified episode identifier
        """
        date_str = self.published.strftime("%Y-%m-%d")
        podcast_slug = slugify(self.podcast_name, max_length=30)
        title_slug = slugify(self.title, max_length=40)
        return f"{podcast_slug}-{date_str}-{title_slug}"

    @property
    def duration_formatted(self) -> str:
        """Get formatted duration string.

        Returns:
            Duration in HH:MM:SS or MM:SS format
        """
        if self.duration_seconds is None:
            return "Unknown"

        hours, remainder = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:d}:{seconds:02d}"
