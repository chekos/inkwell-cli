"""Plugin type definitions.

This package contains base classes for specific plugin types:
- ExtractionPlugin: LLM-based content extraction (Claude, Gemini, etc.)
- TranscriptionPlugin: Audio to text conversion
- OutputPlugin: Output file generation (Markdown, HTML, etc.)

Example:
    >>> from inkwell.plugins.types import ExtractionPlugin, TranscriptionPlugin, OutputPlugin
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
    >>>
    >>> class MyOutput(OutputPlugin):
    ...     NAME = "my-output"
    ...     VERSION = "1.0.0"
    ...     DESCRIPTION = "Custom output format"
"""

from .extraction import ExtractionPlugin
from .output import OutputPlugin
from .transcription import TranscriptionPlugin, TranscriptionRequest

__all__ = [
    "ExtractionPlugin",
    "OutputPlugin",
    "TranscriptionPlugin",
    "TranscriptionRequest",
]
