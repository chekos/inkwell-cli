"""LLM provider implementations for extraction.

This package contains concrete implementations of BaseExtractor
for various LLM providers (Claude, Gemini, etc.).

Note:
    For new code, prefer using the plugin system:

    >>> from inkwell.plugins import ExtractionPlugin

    Or access extractors via ExtractionEngine's registry:

    >>> engine = ExtractionEngine()
    >>> extractor = engine.extraction_registry.get("claude")

    Direct imports from this package are maintained for backward compatibility
    but may be deprecated in future versions.
"""

from .base import BaseExtractor

# Lazy imports to avoid circular dependency with plugins.types.extraction
# ClaudeExtractor and GeminiExtractor inherit from ExtractionPlugin,
# which inherits from BaseExtractor (defined in this package)

__all__ = [
    "BaseExtractor",
    "ClaudeExtractor",
    "GeminiExtractor",
]


def __getattr__(name: str) -> type:
    """Lazy load extractors to avoid circular imports.

    Also emits deprecation warnings for direct extractor access.
    """
    import warnings

    if name == "ClaudeExtractor":
        from .claude import ClaudeExtractor

        warnings.warn(
            f"Direct import of {name} from inkwell.extraction.extractors is deprecated. "
            "Use ExtractionEngine.extraction_registry.get('claude') "
            "or import from inkwell.plugins.types.extraction instead. "
            "This will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return ClaudeExtractor

    if name == "GeminiExtractor":
        from .gemini import GeminiExtractor

        warnings.warn(
            f"Direct import of {name} from inkwell.extraction.extractors is deprecated. "
            "Use ExtractionEngine.extraction_registry.get('gemini') "
            "or import from inkwell.plugins.types.extraction instead. "
            "This will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return GeminiExtractor

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
