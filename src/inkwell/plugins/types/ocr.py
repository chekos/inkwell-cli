"""Plugin interface for local optical character recognition engines."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from inkwell.plugins.base import InkwellPlugin


@dataclass(frozen=True)
class OCRCapabilities:
    """Declared capabilities for an OCR engine."""

    local_only: bool = True
    orientation_detection: bool = False
    confidence_scores: bool = False
    image_formats: tuple[str, ...] = ()

    def display_parts(self) -> list[str]:
        """Return compact labels for ``inkwell plugins list``."""
        parts = ["local" if self.local_only else "remote"]
        if self.orientation_detection:
            parts.append("orientation")
        if self.confidence_scores:
            parts.append("confidence")
        if self.image_formats:
            parts.append(f"{len(self.image_formats)} formats")
        return parts


@dataclass(frozen=True)
class OCRRequest:
    """One in-memory image OCR request."""

    image: Any
    source_label: str
    page_number: int = 1
    language: str = "eng"
    auto_rotate: bool = True
    min_confidence: float = 30.0
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class OCRResult:
    """Normalized text and provenance returned by an OCR plugin."""

    text: str
    confidence: float
    page_number: int
    rotation_degrees: int
    orientation_confidence: float | None
    script: str | None
    engine: str
    engine_version: str


class OCRPlugin(InkwellPlugin):
    """Base class for local or installed OCR engines."""

    CAPABILITIES: ClassVar[OCRCapabilities] = OCRCapabilities()

    @classmethod
    def capability_info(cls) -> OCRCapabilities:
        """Return capabilities without instantiating the plugin."""
        return cls.CAPABILITIES

    def get_capabilities(self) -> OCRCapabilities:
        """Return this plugin's capabilities."""
        return self.capability_info()

    @abstractmethod
    def extract(self, request: OCRRequest) -> OCRResult:
        """Extract text and confidence data from an in-memory image."""
