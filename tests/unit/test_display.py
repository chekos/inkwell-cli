"""Tests for display utilities."""

from inkwell.utils.display import truncate_url


class TestTruncateURL:
    """Tests for URL truncation."""

    def test_short_url_unchanged(self) -> None:
        """Test that short URLs are not truncated."""
        url = "https://example.com/feed.rss"
        result = truncate_url(url, max_length=50)
        assert result == "example.com/feed.rss"

    def test_url_without_scheme(self) -> None:
        """Test URL without scheme."""
        url = "example.com/feed.rss"
        result = truncate_url(url, max_length=50)
        assert result == "example.com/feed.rss"

    def test_very_long_url(self) -> None:
        """Test very long URL shows domain and truncated path."""
        url = "https://very-long-domain-name.com/path/to/some/very/long/podcast/feed.rss"
        result = truncate_url(url, max_length=50)

        # Should preserve domain
        assert "very-long-domain-name.com" in result
        # Should indicate truncation
        assert "..." in result

    def test_long_domain_name(self) -> None:
        """Test URL with very long domain name."""
        url = "https://this-is-a-very-long-domain-name-that-exceeds-limit.com/feed.rss"
        result = truncate_url(url, max_length=30)

        # Should truncate domain from middle
        assert len(result) <= 30
        assert "..." in result

    def test_preserves_file_extension(self) -> None:
        """Test that file extensions are preserved when possible."""
        url = "https://example.com/very/long/path/to/file.rss"
        result = truncate_url(url, max_length=30)

        # Should show domain and extension
        assert "example.com" in result
        assert ".rss" in result or "..." in result

    def test_already_exact_length(self) -> None:
        """Test URL that is exactly max_length."""
        url = "https://example.com/feed.rss"  # 27 chars after scheme removal
        result = truncate_url(url, max_length=len("example.com/feed.rss"))
        assert result == "example.com/feed.rss"

    def test_unicode_in_url(self) -> None:
        """Test URL with unicode characters."""
        url = "https://example.com/café/feed.rss"
        result = truncate_url(url, max_length=50)
        assert "example.com" in result

    def test_url_with_query_params(self) -> None:
        """Test URL with query parameters."""
        url = "https://example.com/feed.rss?key=value&auth=token12345"
        result = truncate_url(url, max_length=40)

        # Should truncate but preserve domain
        assert "example.com" in result
        assert len(result) <= 40

    def test_url_with_port(self) -> None:
        """Test URL with port number."""
        url = "https://example.com:8080/feed.rss"
        result = truncate_url(url, max_length=50)
        assert "example.com:8080" in result

    def test_malformed_url_fallback(self) -> None:
        """Test that malformed URLs fall back to simple truncation."""
        url = "not-a-valid-url-but-very-long-string-that-needs-truncation"
        result = truncate_url(url, max_length=20)

        assert len(result) <= 20
        assert "..." in result

    def test_empty_url(self) -> None:
        """Test empty URL."""
        result = truncate_url("", max_length=50)
        assert result == ""

    def test_url_with_fragment(self) -> None:
        """Test URL with fragment identifier."""
        url = "https://example.com/feed.rss#section"
        result = truncate_url(url, max_length=50)
        assert "example.com" in result
