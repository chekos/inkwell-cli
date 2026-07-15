"""Typed source-text results and deterministic provenance metadata."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ExtractionMethod = Literal["selectable_text", "ocr", "hybrid"]
PageExtractionMethod = Literal["selectable_text", "ocr", "empty"]


@dataclass(frozen=True)
class SourcePageProvenance:
    """How one document page contributed to the extracted text."""

    page_number: int
    extraction_method: PageExtractionMethod
    character_count: int
    confidence: float | None = None
    rotation_degrees: int = 0
    orientation_confidence: float | None = None
    render_dpi: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a stable JSON/YAML-ready representation."""
        return {
            "page_number": self.page_number,
            "extraction_method": self.extraction_method,
            "character_count": self.character_count,
            "confidence": self.confidence,
            "rotation_degrees": self.rotation_degrees,
            "orientation_confidence": self.orientation_confidence,
            "render_dpi": self.render_dpi,
        }


@dataclass(frozen=True)
class SourceTextResult:
    """Locally extracted source text plus inspectable provenance."""

    text: str
    source_kind: str
    media_type: str
    source_path: Path
    method: ExtractionMethod
    pages: tuple[SourcePageProvenance, ...]
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None
    ocr_language: str | None = None
    warnings: tuple[str, ...] = ()

    def provenance(self) -> dict[str, Any]:
        """Build deterministic metadata without machine-specific absolute paths."""
        source_size, source_sha256 = _hash_source_file(self.source_path)
        normalized_text = self.text.strip()
        metadata: dict[str, Any] = {
            "schema_version": 1,
            "local_only": True,
            "source": {
                "filename": self.source_path.name,
                "media_type": self.media_type,
                "size_bytes": source_size,
                "sha256": source_sha256,
            },
            "method": self.method,
            "page_count": len(self.pages),
            "text_characters": len(normalized_text),
            "text_sha256": hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
            "pages": [page.as_dict() for page in self.pages],
            "warnings": list(self.warnings),
        }
        if self.ocr_engine is not None:
            metadata["ocr"] = {
                "engine": self.ocr_engine,
                "engine_version": self.ocr_engine_version,
                "language": self.ocr_language,
            }
        return metadata


def _hash_source_file(path: Path) -> tuple[int, str]:
    """Hash a local source without retaining private document bytes in memory."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()
