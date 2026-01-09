"""Extraction system for podcast content.

This package provides the core extraction functionality for Phase 3,
including template management, LLM provider abstraction, and content extraction.

Note: ExtractionEngine uses lazy import to avoid circular dependency with
inkwell.plugins.types.extraction (which imports BaseExtractor from this package).
"""

from .cache import ExtractionCache
from .models import (
    ExtractedContent,
    ExtractionResult,
    ExtractionTemplate,
    TemplateVariable,
)

__all__ = [
    "ExtractionTemplate",
    "TemplateVariable",
    "ExtractedContent",
    "ExtractionResult",
    "ExtractionCache",
    "ExtractionEngine",
]


def __getattr__(name: str):
    """Lazy import for ExtractionEngine to avoid circular imports.

    The circular import chain is:
    1. inkwell.plugins.__init__ → .types → .types.extraction
    2. .types.extraction imports BaseExtractor from inkwell.extraction.extractors.base
    3. inkwell.extraction.__init__ imports ExtractionEngine from .engine
    4. engine.py imports from ..plugins.types.extraction → CIRCULAR!

    By using lazy import, ExtractionEngine is only loaded when accessed.
    """
    if name == "ExtractionEngine":
        from .engine import ExtractionEngine

        return ExtractionEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
