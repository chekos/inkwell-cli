"""Custom exceptions for Inkwell."""


class InkwellError(Exception):
    """Base exception for all Inkwell errors."""

    pass


class ConfigError(InkwellError):
    """Configuration-related errors."""

    pass


class InvalidConfigError(ConfigError):
    """Invalid configuration data."""

    pass


class ConfigNotFoundError(ConfigError):
    """Configuration file not found."""

    pass


class EncryptionError(ConfigError):
    """Encryption/decryption errors."""

    pass


class FeedError(InkwellError):
    """Feed management errors."""

    pass


class FeedNotFoundError(FeedError):
    """Feed not found in configuration."""

    pass


class DuplicateFeedError(FeedError):
    """Feed already exists."""

    pass


class FeedParseError(FeedError):
    """RSS feed parsing errors."""

    pass


class AuthenticationError(FeedError):
    """Feed authentication failures."""

    pass


class NetworkError(InkwellError):
    """Network-related errors."""

    pass


class NetworkConnectionError(NetworkError):
    """Connection failures."""

    pass


class NetworkTimeoutError(NetworkError):
    """Request timeout."""

    pass
