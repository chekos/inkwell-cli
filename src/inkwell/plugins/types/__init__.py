"""Plugin type definitions.

This package contains base classes for specific plugin types:
- ExtractionPlugin: LLM-based content extraction (Claude, Gemini, etc.)
- TranscriptionPlugin (Phase 3): Audio to text conversion
- OutputPlugin (Phase 4): Output file generation

Example:
    >>> from inkwell.plugins.types import ExtractionPlugin
    >>>
    >>> class MyExtractor(ExtractionPlugin):
    ...     NAME = "my-extractor"
    ...     VERSION = "1.0.0"
    ...     DESCRIPTION = "Custom extractor"
"""

from .extraction import ExtractionPlugin

__all__ = [
    "ExtractionPlugin",
]
