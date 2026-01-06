"""Plugin type definitions.

This package contains base classes for specific plugin types:
- ExtractionPlugin: LLM-based content extraction (Claude, Gemini, etc.)
- TranscriptionPlugin: Audio to text conversion
- OutputPlugin (Phase 4): Output file generation

Example:
    >>> from inkwell.plugins.types import ExtractionPlugin, TranscriptionPlugin
    >>>
    >>> class MyExtractor(ExtractionPlugin):
    ...     NAME = "my-extractor"
    ...     VERSION = "1.0.0"
    ...     DESCRIPTION = "Custom extractor"
    >>>
    >>> class MyTranscriber(TranscriptionPlugin):
    ...     NAME = "my-transcriber"
    ...     VERSION = "1.0.0"
    ...     DESCRIPTION = "Custom transcriber"
"""

from .extraction import ExtractionPlugin
from .transcription import TranscriptionPlugin, TranscriptionRequest

__all__ = [
    "ExtractionPlugin",
    "TranscriptionPlugin",
    "TranscriptionRequest",
]
