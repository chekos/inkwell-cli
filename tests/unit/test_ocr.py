"""Tests for the local OCR plugin and manager."""

from typing import Any

import pytest
from PIL import Image

from inkwell.ingestion.ocr import (
    OCRLowConfidenceError,
    OCRManager,
    TesseractOCRPlugin,
    _text_and_confidence_from_tesseract,
)
from inkwell.plugins.base import PluginValidationError
from inkwell.plugins.types.ocr import OCRRequest
from inkwell.utils.errors import ValidationError


def _ocr_data(*, confidence: str = "96") -> dict[str, list[Any]]:
    return {
        "text": ["Public", "fixture", "Second", "line"],
        "conf": [confidence, confidence, confidence, confidence],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 2, 2],
    }


def test_text_and_confidence_reconstructs_stable_lines() -> None:
    text, confidence = _text_and_confidence_from_tesseract(_ocr_data())

    assert text == "Public fixture\nSecond line"
    assert confidence == 96.0


def test_tesseract_plugin_applies_orientation_and_reports_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytesseract

    image = Image.new("RGB", (80, 40), "white")
    observed_sizes: list[tuple[int, int]] = []
    monkeypatch.setattr(TesseractOCRPlugin, "validate", lambda _self: None)
    monkeypatch.setattr(
        pytesseract,
        "image_to_osd",
        lambda *_args, **_kwargs: {
            "rotate": 90,
            "orientation_conf": 12.5,
            "script": "Latin",
        },
    )

    def fake_image_to_data(rotated_image, **_kwargs):
        observed_sizes.append(rotated_image.size)
        return _ocr_data()

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)
    monkeypatch.setattr(pytesseract, "get_tesseract_version", lambda: "5.5.1")

    result = TesseractOCRPlugin().extract(
        OCRRequest(image=image, source_label="public-fixture.png")
    )

    assert observed_sizes == [(40, 80)]
    assert result.text == "Public fixture\nSecond line"
    assert result.rotation_degrees == 90
    assert result.orientation_confidence == 12.5
    assert result.script == "Latin"
    assert result.engine == "tesseract"
    assert result.engine_version == "5.5.1"


def test_tesseract_plugin_rejects_low_confidence_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytesseract

    monkeypatch.setattr(TesseractOCRPlugin, "validate", lambda _self: None)
    monkeypatch.setattr(
        pytesseract,
        "image_to_osd",
        lambda *_args, **_kwargs: {"rotate": 0},
    )
    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *_args, **_kwargs: _ocr_data(confidence="8"),
    )

    with pytest.raises(OCRLowConfidenceError, match="too low"):
        TesseractOCRPlugin().extract(
            OCRRequest(
                image=Image.new("RGB", (20, 20), "white"),
                source_label="low-confidence.png",
                min_confidence=30,
            )
        )


def test_tesseract_plugin_validation_reports_missing_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("inkwell.ingestion.ocr.shutil.which", lambda _name: None)

    with pytest.raises(PluginValidationError, match="executable is not on PATH"):
        TesseractOCRPlugin().validate()


def test_ocr_manager_turns_missing_dependency_into_actionable_error() -> None:
    class InvalidPlugin(TesseractOCRPlugin):
        def validate(self) -> None:
            raise PluginValidationError(self.NAME, ["the tesseract executable is not on PATH"])

    with pytest.raises(ValidationError, match="uv sync --extra ocr") as exc_info:
        OCRManager(plugin=InvalidPlugin()).extract(
            OCRRequest(
                image=Image.new("RGB", (20, 20), "white"),
                source_label="fixture.png",
            )
        )

    assert "brew install tesseract" in str(exc_info.value)


def test_tesseract_plugin_rejects_unsafe_language_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(TesseractOCRPlugin, "validate", lambda _self: None)

    with pytest.raises(ValidationError, match="Invalid OCR language"):
        TesseractOCRPlugin().extract(
            OCRRequest(
                image=Image.new("RGB", (20, 20), "white"),
                source_label="fixture.png",
                language="eng --config /tmp/file",
            )
        )
