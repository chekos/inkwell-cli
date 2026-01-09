"""Feed URL and authentication validator."""

import httpx
from pydantic import HttpUrl, ValidationError

from inkwell.config.schema import AuthConfig
from inkwell.utils.errors import APIError, SecurityError
from inkwell.utils.errors import ValidationError as InkwellValidationError
from inkwell.utils.retry import AuthenticationError


class FeedValidator:
    """Validates feed URLs and authentication."""

    def __init__(self, timeout: int = 10) -> None:
        """Initialize the feed validator.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout

    async def validate_feed_url(self, url: str, auth: AuthConfig | None = None) -> bool:
        """Check if URL is valid and accessible.

        Args:
            url: Feed URL to validate
            auth: Optional authentication configuration

        Returns:
            True if URL is valid and accessible

        Raises:
            InvalidConfigError: If URL format is invalid
            NetworkError: If URL is not accessible
            AuthenticationError: If authentication is required but not provided/invalid
        """
        # Validate URL format
        try:
            HttpUrl(url)
        except ValidationError as e:
            raise InkwellValidationError(f"Invalid URL format: {url}") from e

        # Check if URL is accessible
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = self._build_auth_headers(auth)
                response = await client.head(url, headers=headers, follow_redirects=True)

                # Handle 405 Method Not Allowed (some servers don't support HEAD)
                if response.status_code == 405:
                    # Try GET instead
                    response = await client.get(url, headers=headers, follow_redirects=True)

                if response.status_code == 401:
                    raise SecurityError(
                        f"Authentication required for {url}. "
                        "Use --auth flag to provide credentials."
                    )

                response.raise_for_status()
                return True

        except httpx.TimeoutException as e:
            raise APIError(f"Timeout connecting to {url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(f"Authentication failed for {url}") from e
            elif e.response.status_code == 404:
                raise APIError(f"Feed not found: {url} (404)") from e
            else:
                raise APIError(f"HTTP error accessing {url}: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise APIError(f"Network error accessing {url}: {e}") from e

    async def validate_auth(self, url: str, auth: AuthConfig) -> bool:
        """Verify that authentication credentials work.

        Args:
            url: Feed URL to test
            auth: Authentication configuration to test

        Returns:
            True if authentication works

        Raises:
            AuthenticationError: If authentication fails
            NetworkError: If network error occurs
        """
        if auth.type == "none":
            # No auth to validate
            return True

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = self._build_auth_headers(auth)
                response = await client.head(url, headers=headers, follow_redirects=True)

                # Handle 405 Method Not Allowed
                if response.status_code == 405:
                    response = await client.get(url, headers=headers, follow_redirects=True)

                if response.status_code == 401:
                    raise SecurityError(f"Authentication failed for {url}. Check your credentials.")

                response.raise_for_status()
                return True

        except httpx.TimeoutException as e:
            raise APIError(f"Timeout connecting to {url}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(f"Invalid credentials for {url}") from e
            raise APIError(f"HTTP error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise APIError(f"Network error: {e}") from e

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
