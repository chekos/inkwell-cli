"""Extraction-related error classes."""


class ExtractionError(Exception):
    """Base error for extraction failures."""

    pass


class ProviderError(ExtractionError):
    """Error from LLM provider (API error, rate limit, etc.)."""

    def __init__(self, message: str, provider: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ValidationError(ExtractionError):
    """Error validating LLM output against schema."""

    def __init__(self, message: str, schema: dict | None = None) -> None:
        super().__init__(message)
        self.schema = schema


class TemplateError(ExtractionError):
    """Error rendering or processing template."""

    pass
