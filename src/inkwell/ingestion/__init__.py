"""Input classification primitives for Inkwell ingestion."""

from .resolver import ContentSource, ContentSourceKind, InputResolver
from .source_extractors import (
    extract_article_text_from_html,
    extract_article_text_from_url,
    extract_text_from_pdf,
)

__all__ = [
    "ContentSource",
    "ContentSourceKind",
    "InputResolver",
    "extract_article_text_from_html",
    "extract_article_text_from_url",
    "extract_text_from_pdf",
]
