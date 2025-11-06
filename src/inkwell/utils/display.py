"""Display utilities for terminal output."""

from urllib.parse import urlparse


def truncate_url(url: str, max_length: int = 50) -> str:
    """Truncate URL intelligently, preserving the domain.

    Args:
        url: URL to truncate
        max_length: Maximum length of output

    Returns:
        Truncated URL string

    Examples:
        >>> truncate_url("https://example.com/feed.rss", 30)
        'example.com/feed.rss'

        >>> truncate_url("https://very-long-domain.com/very/long/path/to/feed.rss", 30)
        'very-long-domain.com/...rss'
    """
    try:
        parsed = urlparse(url)

        # Start with domain (without scheme)
        domain = parsed.netloc
        path = parsed.path

        # If domain + path fits, use it (no scheme)
        simple_url = domain + path
        if len(simple_url) <= max_length:
            return simple_url

        # If domain is too long, truncate from middle
        if len(domain) > max_length - 3:
            mid = (max_length - 3) // 2
            return domain[:mid] + "..." + domain[-mid:]

        # Show domain + truncated path
        remaining = max_length - len(domain) - 3  # Space for "..."
        if remaining > 0:
            # Try to show file extension
            path_parts = path.rsplit("/", 1)
            if len(path_parts) == 2 and len(path_parts[1]) < remaining:
                return f"{domain}/...{path_parts[1]}"

        return domain + "/..."

    except Exception:
        # Fallback: simple truncation
        return url[: max_length - 3] + "..."
