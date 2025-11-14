"""Extraction system for podcast content.

This package provides the core extraction functionality for Phase 3,
including template management, LLM provider abstraction, and content extraction.
"""

from .cache import ExtractionCache
from .engine import ExtractionEngine
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
