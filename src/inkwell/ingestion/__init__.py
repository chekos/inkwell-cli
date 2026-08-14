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
from .tiktok import TikTokSource, is_tiktok_url, parse_webvtt, resolve_tiktok_source

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
    "TikTokSource",
    "is_tiktok_url",
    "parse_webvtt",
    "resolve_tiktok_source",
    "extract_text_from_pdf",
]
