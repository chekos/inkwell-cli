"""Custom exceptions for Inkwell.

Simplified to 5 core error types per todo #035.
Each error includes rich context via details dict and user-friendly suggestions.
"""


class InkwellError(Exception):
    """Base exception for all Inkwell errors.

    Attributes:
        message: Human-readable error message
        details: Additional context as a dictionary
        suggestion: Optional suggestion for the user
    """

    def __init__(
        self,
        message: str,
        details: dict | None = None,
        suggestion: str | None = None,
    ):
        """Initialize error with message, details, and optional suggestion.

        Args:
            message: Error message describing what went wrong
            details: Additional context (e.g., {"file": path, "line": 42})
            suggestion: User-friendly suggestion for resolving the error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion

    def __str__(self) -> str:
        """Format error with suggestion if available."""
        base = self.message
        if self.suggestion:
            base += f"\n\nSuggestion: {self.suggestion}"
        return base


class ConfigError(InkwellError):
    """Configuration and setup errors.

    Covers:
    - Invalid config files
    - Missing configuration
    - Encryption/decryption issues
    - Config validation failures
    """

    pass


class APIError(InkwellError):
    """External API failures.

    Covers:
    - LLM provider errors (Claude, Gemini)
    - YouTube API failures
    - Network errors (connection, timeout)
    - Rate limiting
    - Server errors (5xx)

    Includes provider name and status code for debugging.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        **kwargs,
    ):
        """Initialize API error with provider context.

        Args:
            message: Error description
            provider: API provider name (e.g., "gemini", "claude", "youtube")
            status_code: HTTP status code if applicable
            **kwargs: Additional arguments (details, suggestion)
        """
        super().__init__(message, **kwargs)
        self.provider = provider
        self.status_code = status_code


class ValidationError(InkwellError):
    """Input validation failures.

    Covers:
    - Invalid URLs
    - Malformed data
    - Schema validation errors
    - Invalid request parameters
    """

    pass


class NotFoundError(InkwellError):
    """Resource not found errors.

    Covers:
    - Feed not found
    - File not found
    - Template not found
    - Episode not found

    Includes resource type and identifier for context.
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        **kwargs,
    ):
        """Initialize NotFoundError with resource context.

        Args:
            resource_type: Type of resource (e.g., "Feed", "Template", "File")
            resource_id: Resource identifier (name, path, ID)
            **kwargs: Additional arguments (details, suggestion)
        """
        message = f"{resource_type} not found: {resource_id}"
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id


class SecurityError(InkwellError):
    """Security-related errors.

    Covers:
    - Path traversal attempts
    - Permission denied
    - Authentication failures
    - Invalid credentials
    """

    pass
