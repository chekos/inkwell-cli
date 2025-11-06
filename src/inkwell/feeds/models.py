"""Data models for podcast episodes and feeds."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class Episode(BaseModel):
    """Represents a single podcast episode."""

    title: str
    url: HttpUrl  # Direct audio/video URL
    published: datetime
    description: str
    duration_seconds: Optional[int] = None
    podcast_name: str
    episode_number: Optional[int] = None
    season_number: Optional[int] = None

    @property
    def slug(self) -> str:
        """Generate filesystem-safe episode identifier."""
        # TODO: Implement slugification
        date_str = self.published.strftime("%Y-%m-%d")
        return f"{self.podcast_name}-{date_str}-{self.title}"
