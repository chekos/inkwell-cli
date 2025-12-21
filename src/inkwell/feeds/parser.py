"""RSS feed parser using feedparser."""

from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from inkwell.config.schema import AuthConfig
from inkwell.feeds.models import Episode
from inkwell.utils.errors import APIError, SecurityError, ValidationError
from inkwell.utils.retry import AuthenticationError


class RSSParser:
    """Parses RSS feeds and extracts episode information."""

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the RSS parser.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout

    async def fetch_feed(
        self, url: str, auth: AuthConfig | None = None
    ) -> feedparser.FeedParserDict:
        """Fetch and parse RSS/Atom feed with authentication support.

        Args:
            url: Feed URL to fetch
            auth: Optional authentication configuration

        Returns:
            Parsed feed dictionary from feedparser

        Raises:
            NetworkError: If feed cannot be fetched
            AuthenticationError: If authentication fails
            FeedParseError: If feed parsing fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = self._build_auth_headers(auth)
                response = await client.get(url, headers=headers, follow_redirects=True)

                # Check for auth errors
                if response.status_code == 401:
                    raise SecurityError(f"Authentication failed for {url}. Check your credentials.")

                response.raise_for_status()

                # Parse feed
                feed = feedparser.parse(response.content)

                # Check for parsing errors
                if feed.bozo:  # feedparser error flag
                    # Log warning but continue if we got entries
                    if not feed.entries:
                        error_msg = getattr(feed, "bozo_exception", "Unknown parsing error")
                        raise ValidationError(f"Failed to parse feed from {url}: {error_msg}")

                if not feed.entries:
                    raise ValidationError(f"No episodes found in feed: {url}")

                return feed

        except httpx.TimeoutException as e:
            raise APIError(f"Timeout fetching feed from {url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(f"Authentication required for {url}") from e
            raise APIError(f"HTTP error fetching {url}: {e}") from e
        except httpx.RequestError as e:
            raise APIError(f"Network error fetching {url}: {e}") from e

    def _build_auth_headers(self, auth: AuthConfig | None = None) -> dict[str, str]:
        """Build HTTP headers for authentication.

        Args:
            auth: Authentication configuration

        Returns:
            Dictionary of HTTP headers
        """
        headers: dict[str, str] = {}

        if auth is None or auth.type == "none":
            return headers

        if auth.type == "basic":
            import base64

            if auth.username and auth.password:
                credentials = f"{auth.username}:{auth.password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

        elif auth.type == "bearer":
            if auth.token:
                headers["Authorization"] = f"Bearer {auth.token}"

        return headers

    def get_latest_episode(self, feed: feedparser.FeedParserDict, podcast_name: str) -> Episode:
        """Extract the latest episode from a feed.

        Args:
            feed: Parsed feed dictionary
            podcast_name: Name of the podcast

        Returns:
            Episode instance for the latest episode

        Raises:
            FeedParseError: If no episodes found
        """
        if not feed.entries:
            raise ValidationError("No episodes found in feed")

        # Entries are typically sorted newest first
        latest_entry = feed.entries[0]
        return self.extract_episode_metadata(latest_entry, podcast_name)

    def get_episode_by_title(
        self,
        feed: feedparser.FeedParserDict,
        title_keyword: str,
        podcast_name: str,
    ) -> Episode:
        """Find episode by title keyword (case-insensitive fuzzy match).

        Args:
            feed: Parsed feed dictionary
            title_keyword: Keyword to search for in episode titles
            podcast_name: Name of the podcast

        Returns:
            First matching Episode instance

        Raises:
            FeedParseError: If no matching episode found
        """
        title_keyword_lower = title_keyword.lower()

        for entry in feed.entries:
            entry_title = entry.get("title", "").lower()
            if title_keyword_lower in entry_title:
                return self.extract_episode_metadata(entry, podcast_name)

        raise ValidationError(f"No episode found matching '{title_keyword}' in feed")

    def extract_episode_metadata(self, entry: dict, podcast_name: str) -> Episode:
        """Extract Episode model from feedparser entry.

        Args:
            entry: Feedparser entry dictionary
            podcast_name: Name of the podcast

        Returns:
            Episode instance with extracted metadata

        Raises:
            FeedParseError: If required fields are missing
        """
        # Required fields
        title = entry.get("title")
        if not title:
            raise ValidationError("Episode missing required field: title")

        # Extract audio/video URL from enclosure
        enclosure_url = self._extract_enclosure_url(entry)
        if not enclosure_url:
            raise ValidationError(f"Episode '{title}' has no audio enclosure")

        # Extract published date
        published = self._extract_published_date(entry)

        # Extract description
        description = self._extract_description(entry)

        # Extract duration
        duration_seconds = self._extract_duration(entry)

        # Extract episode/season numbers
        episode_number = self._extract_episode_number(entry)
        season_number = self._extract_season_number(entry)

        # Extract GUID
        guid = entry.get("id") or entry.get("guid")

        return Episode(
            title=title,
            url=enclosure_url,  # type: ignore
            published=published,
            description=description,
            duration_seconds=duration_seconds,
            podcast_name=podcast_name,
            episode_number=episode_number,
            season_number=season_number,
            guid=guid,
        )

    def _extract_enclosure_url(self, entry: dict) -> str | None:
        """Extract audio/video URL from entry enclosures.

        Args:
            entry: Feedparser entry

        Returns:
            URL string or None if not found
        """
        # Check enclosures list
        enclosures = entry.get("enclosures", [])
        for enclosure in enclosures:
            if enclosure.get("type", "").startswith("audio/") or enclosure.get(
                "type", ""
            ).startswith("video/"):
                return enclosure.get("href") or enclosure.get("url")

        # Fallback: check links
        links = entry.get("links", [])
        for link in links:
            if link.get("rel") == "enclosure":
                return link.get("href")

        return None

    def _extract_published_date(self, entry: dict) -> datetime:
        """Extract published date from entry.

        Args:
            entry: Feedparser entry

        Returns:
            Datetime of publication
        """
        # Try published_parsed (feedparser's parsed date)
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            import time

            return datetime.fromtimestamp(time.mktime(entry.published_parsed))

        # Try parsing published string
        if "published" in entry:
            try:
                return parsedate_to_datetime(entry["published"])
            except (ValueError, TypeError):
                pass

        # Try updated field
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            import time
            from datetime import timezone

            return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)

        # Fallback to now
        from inkwell.utils.datetime import now_utc

        return now_utc()

    def _extract_description(self, entry: dict) -> str:
        """Extract description from entry.

        Args:
            entry: Feedparser entry

        Returns:
            Description text (may be empty)
        """
        # Try summary first
        if "summary" in entry:
            return entry["summary"]

        # Try description
        if "description" in entry:
            return entry["description"]

        # Try content
        if "content" in entry and entry["content"]:
            return entry["content"][0].get("value", "")

        return ""

    def _extract_duration(self, entry: dict) -> int | None:
        """Extract duration in seconds from entry.

        Args:
            entry: Feedparser entry

        Returns:
            Duration in seconds or None
        """
        # Check itunes:duration
        duration = entry.get("itunes_duration")
        if duration:
            try:
                # Can be "HH:MM:SS", "MM:SS", or just seconds
                if ":" in str(duration):
                    parts = str(duration).split(":")
                    if len(parts) == 3:  # HH:MM:SS
                        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:  # MM:SS
                        return int(parts[0]) * 60 + int(parts[1])
                else:
                    return int(duration)
            except (ValueError, TypeError):
                # Invalid duration format, return None to indicate unknown duration
                pass

        return None

    def _extract_episode_number(self, entry: dict) -> int | None:
        """Extract episode number from entry.

        Args:
            entry: Feedparser entry

        Returns:
            Episode number or None
        """
        # Check itunes:episode
        episode = entry.get("itunes_episode")
        if episode:
            try:
                return int(episode)
            except (ValueError, TypeError):
                pass

        return None

    def _extract_season_number(self, entry: dict) -> int | None:
        """Extract season number from entry.

        Args:
            entry: Feedparser entry

        Returns:
            Season number or None
        """
        # Check itunes:season
        season = entry.get("itunes_season")
        if season:
            try:
                return int(season)
            except (ValueError, TypeError):
                pass

        return None
