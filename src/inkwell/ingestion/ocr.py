"""Local OCR plugin management and the built-in Tesseract implementation."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
from collections import OrderedDict
from typing import Any, ClassVar

from inkwell.plugins.base import PluginValidationError
from inkwell.plugins.discovery import discover_plugins
from inkwell.plugins.types.ocr import (
    OCRCapabilities,
    OCRPlugin,
    OCRRequest,
    OCRResult,
)
from inkwell.utils.errors import ValidationError

OCR_INSTALL_SUGGESTION = (
    "Install the optional Python dependencies with "
    "`uv tool install 'inkwell-cli[ocr]'` (installed CLI) or "
    "`uv sync --extra ocr` (source checkout). Also install Tesseract with "
    "`brew install tesseract` on macOS or `sudo apt install tesseract-ocr` on Ubuntu."
)
OCR_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z0-9_+.-]+$")


class OCREmptyResultError(ValidationError):
    """Raised when an OCR page contains no readable text."""


class OCRLowConfidenceError(ValidationError):
    """Raised when OCR output is too uncertain to enter durable notes."""

    def __init__(self, confidence: float, page_number: int) -> None:
        self.confidence = confidence
        self.page_number = page_number
        super().__init__(
            f"OCR confidence is too low on page {page_number}: {confidence:.1f}%",
            suggestion=(
                "Use a clearer or higher-resolution scan, correct the page orientation, "
                "or choose installed language data with --ocr-language."
            ),
        )


class TesseractOCRPlugin(OCRPlugin):
    """Offline OCR using the local Tesseract executable."""

    NAME: ClassVar[str] = "tesseract"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Local image OCR through Tesseract"
    CAPABILITIES: ClassVar[OCRCapabilities] = OCRCapabilities(
        local_only=True,
        orientation_detection=True,
        confidence_scores=True,
        image_formats=("bmp", "gif", "jpeg", "png", "pnm", "tiff", "webp"),
    )

    def validate(self) -> None:
        """Verify optional Python packages and the local binary are available."""
        errors: list[str] = []
        if importlib.util.find_spec("PIL") is None:
            errors.append("Pillow is not installed")
        if importlib.util.find_spec("pytesseract") is None:
            errors.append("pytesseract is not installed")
        if shutil.which("tesseract") is None:
            errors.append("the tesseract executable is not on PATH")
        if errors:
            raise PluginValidationError(self.NAME, errors)

    def extract(self, request: OCRRequest) -> OCRResult:
        """Run orientation-aware Tesseract OCR without network access."""
        if not OCR_LANGUAGE_PATTERN.fullmatch(request.language):
            raise ValidationError(
                f"Invalid OCR language value: {request.language}",
                suggestion="Use Tesseract language codes such as eng, spa, or eng+spa.",
            )

        import pytesseract
        from PIL import ImageOps

        normalized_image = ImageOps.exif_transpose(request.image)
        image = normalized_image.convert("RGB")
        if normalized_image is not request.image:
            normalized_image.close()
        rotation_degrees = 0
        orientation_confidence: float | None = None
        script: str | None = None

        if request.auto_rotate:
            try:
                osd = pytesseract.image_to_osd(
                    image,
                    output_type=pytesseract.Output.DICT,
                    timeout=min(request.timeout_seconds, 30.0),
                )
                rotation_degrees = int(osd.get("rotate", 0) or 0) % 360
                orientation_confidence = _optional_float(osd.get("orientation_conf"))
                raw_script = osd.get("script")
                script = str(raw_script) if raw_script else None
                if rotation_degrees:
                    rotated_image = image.rotate(
                        -rotation_degrees,
                        expand=True,
                        fillcolor="white",
                    )
                    image.close()
                    image = rotated_image
            except (pytesseract.TesseractError, RuntimeError, TypeError, ValueError):
                # OSD commonly lacks enough characters on short images. OCR still
                # proceeds using EXIF-normalized orientation.
                rotation_degrees = 0
                orientation_confidence = None
                script = None

        try:
            try:
                data = pytesseract.image_to_data(
                    image,
                    lang=request.language,
                    config="--psm 3",
                    output_type=pytesseract.Output.DICT,
                    timeout=request.timeout_seconds,
                )
            except pytesseract.TesseractNotFoundError as e:
                raise ValidationError(
                    "Tesseract is not available for local OCR",
                    suggestion=OCR_INSTALL_SUGGESTION,
                ) from e
            except RuntimeError as e:
                raise ValidationError(
                    f"Local OCR timed out for {request.source_label}",
                    suggestion="Try a smaller image or split a large PDF into fewer pages.",
                ) from e
            except pytesseract.TesseractError as e:
                raise ValidationError(
                    f"Tesseract could not read {request.source_label}",
                    suggestion=(
                        "Check that the image is valid and that the requested OCR "
                        "language is installed."
                    ),
                ) from e
        finally:
            image.close()

        text, confidence = _text_and_confidence_from_tesseract(data)
        if not text:
            raise OCREmptyResultError(
                f"No readable text found by OCR on page {request.page_number}",
                suggestion="Use a clearer scan or verify that the page contains text.",
            )
        if confidence < request.min_confidence:
            raise OCRLowConfidenceError(confidence, request.page_number)

        return OCRResult(
            text=text,
            confidence=confidence,
            page_number=request.page_number,
            rotation_degrees=rotation_degrees,
            orientation_confidence=orientation_confidence,
            script=script,
            engine=self.NAME,
            engine_version=str(pytesseract.get_tesseract_version()),
        )


class OCRManager:
    """Select and invoke an OCR plugin through Inkwell's entry-point registry."""

    def __init__(
        self,
        engine: str | None = None,
        plugin: OCRPlugin | None = None,
    ) -> None:
        self.engine = engine or os.environ.get("INKWELL_OCR") or "tesseract"
        self._plugin = plugin

    def extract(self, request: OCRRequest) -> OCRResult:
        """Extract text with the selected configured OCR plugin."""
        plugin = self._plugin or self._load_plugin()
        try:
            if not plugin.is_initialized:
                plugin.configure({})
            plugin.validate()
        except PluginValidationError as e:
            raise ValidationError(
                f"Local OCR engine '{self.engine}' is not ready: {'; '.join(e.errors)}",
                suggestion=OCR_INSTALL_SUGGESTION,
            ) from e
        return plugin.extract(request)

    def _load_plugin(self) -> OCRPlugin:
        failures: list[str] = []
        for result in discover_plugins("inkwell.plugins.ocr"):
            if result.name != self.engine:
                continue
            if result.success and isinstance(result.plugin, OCRPlugin):
                return result.plugin
            failures.append(result.error or "plugin failed to load")

        if failures:
            raise ValidationError(
                f"OCR engine '{self.engine}' failed to load: {'; '.join(failures)}",
                suggestion=OCR_INSTALL_SUGGESTION,
            )
        raise ValidationError(
            f"OCR engine '{self.engine}' is not installed",
            suggestion="Run 'inkwell plugins list --type ocr' to see available local OCR engines.",
        )


def _optional_float(value: object) -> float | None:
    """Convert an optional OCR value to float without leaking parser quirks."""
    try:
        return round(float(str(value)), 2) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text_and_confidence_from_tesseract(data: dict[str, list[Any]]) -> tuple[str, float]:
    """Reconstruct stable line text and a word-weighted mean confidence."""
    words = data.get("text", [])
    confidences = data.get("conf", [])
    line_fields = [
        data.get("block_num", []),
        data.get("par_num", []),
        data.get("line_num", []),
    ]
    lines: OrderedDict[tuple[int, int, int], list[str]] = OrderedDict()
    accepted_confidences: list[float] = []

    for index, raw_word in enumerate(words):
        word = str(raw_word).strip()
        if not word:
            continue
        key_values: list[int] = []
        for field in line_fields:
            try:
                key_values.append(int(field[index]))
            except (IndexError, TypeError, ValueError):
                key_values.append(0)
        key = (key_values[0], key_values[1], key_values[2])
        lines.setdefault(key, []).append(word)

        try:
            confidence = float(confidences[index])
        except (IndexError, TypeError, ValueError):
            continue
        if confidence >= 0:
            accepted_confidences.append(confidence)

    text = "\n".join(" ".join(line) for line in lines.values()).strip()
    if not text or not accepted_confidences:
        return "", 0.0
    mean_confidence = sum(accepted_confidences) / len(accepted_confidences)
    return text, round(mean_confidence, 2)
