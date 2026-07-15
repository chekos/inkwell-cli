"""Input classification primitives for Inkwell ingestion."""

from .models import SourcePageProvenance, SourceTextResult
from .ocr import OCRManager
from .resolver import ContentSource, ContentSourceKind, InputResolver
from .source_extractors import (
    OCRMode,
    extract_article_text_from_html,
    extract_article_text_from_url,
    extract_source_text_from_image,
    extract_source_text_from_pdf,
    extract_text_from_pdf,
)

__all__ = [
    "ContentSource",
    "ContentSourceKind",
    "InputResolver",
    "OCRManager",
    "OCRMode",
    "SourcePageProvenance",
    "SourceTextResult",
    "extract_article_text_from_html",
    "extract_article_text_from_url",
    "extract_source_text_from_image",
    "extract_source_text_from_pdf",
    "extract_text_from_pdf",
]
