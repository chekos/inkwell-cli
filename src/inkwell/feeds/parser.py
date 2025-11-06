"""RSS feed parser using feedparser."""


class RSSParser:
    """Parses RSS feeds and extracts episode information."""

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the RSS parser.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout
