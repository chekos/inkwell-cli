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
from .claude import ClaudeExtractor
from .gemini import GeminiExtractor

__all__ = [
    "BaseExtractor",
    "ClaudeExtractor",
    "GeminiExtractor",
]


def __getattr__(name: str) -> type:
    """Emit deprecation warnings for direct extractor access.

    This allows us to warn users while maintaining backward compatibility.
    """
    import warnings

    if name in ("ClaudeExtractor", "GeminiExtractor"):
        plugin_name = name.replace("Extractor", "").lower()
        warnings.warn(
            f"Direct import of {name} from inkwell.extraction.extractors is deprecated. "
            f"Use ExtractionEngine.extraction_registry.get('{plugin_name}') "
            "or import from inkwell.plugins.types.extraction instead. "
            "This will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Return the actual class
        if name == "ClaudeExtractor":
            return ClaudeExtractor
        else:
            return GeminiExtractor

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
