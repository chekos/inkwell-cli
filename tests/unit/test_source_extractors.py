"""Tests for local article, image, and PDF source extraction."""

from pathlib import Path

import pytest
from PIL import Image

from inkwell.ingestion.models import SourceTextResult
from inkwell.ingestion.ocr import OCREmptyResultError, OCRLowConfidenceError
from inkwell.ingestion.source_extractors import (
    PDF_OCR_MAX_RENDER_PIXELS,
    OCRMode,
    RenderedPDFPage,
    _bounded_pdf_render_scale,
    extract_article_text_from_html,
    extract_source_text_from_image,
    extract_source_text_from_pdf,
    extract_text_from_pdf,
)
from inkwell.plugins.types.ocr import OCRRequest, OCRResult
from inkwell.utils.errors import ValidationError


class FakePage:
    """Minimal selectable-text PDF page."""

    def __init__(self, text: str = "", error: Exception | None = None) -> None:
        self.text = text
        self.error = error

    def extract_text(self) -> str:
        if self.error:
            raise self.error
        return self.text


class FakeImage:
    """Closable image stand-in for injected PDF renders."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeOCRManager:
    """Deterministic OCR manager for source-extractor tests."""

    def __init__(self, results: list[OCRResult | Exception]) -> None:
        self.results = results
        self.requests: list[OCRRequest] = []

    def extract(self, request: OCRRequest) -> OCRResult:
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _ocr_result(text: str, *, page: int = 1, confidence: float = 95.0) -> OCRResult:
    return OCRResult(
        text=text,
        confidence=confidence,
        page_number=page,
        rotation_degrees=0,
        orientation_confidence=11.0,
        script="Latin",
        engine="tesseract",
        engine_version="5.5.1",
    )


def _patch_pdf_reader(
    monkeypatch: pytest.MonkeyPatch,
    pages: list[FakePage],
    *,
    encrypted: bool = False,
) -> None:
    class FakeReader:
        is_encrypted = encrypted

        def __init__(self) -> None:
            self.pages = pages

    monkeypatch.setattr("inkwell.ingestion.source_extractors.PdfReader", lambda _path: FakeReader())


def test_extract_article_text_from_html_returns_clean_readable_text() -> None:
    html = """
    <html>
      <head><title>Readable Article</title></head>
      <body>
        <nav>Navigation links should not matter</nav>
        <article>
          <h1>Readable Article</h1>
          <p>This article explains a useful workflow with enough detail for extraction.</p>
          <p>It includes a second paragraph so local cleanup has meaningful article text.</p>
        </article>
      </body>
    </html>
    """

    text = extract_article_text_from_html(html, url="https://example.com/article")

    assert "Readable Article" in text
    assert "useful workflow" in text
    assert "second paragraph" in text


def test_extract_article_text_from_html_errors_for_thin_pages() -> None:
    html = "<html><body><main>Subscribe</main></body></html>"

    with pytest.raises(ValidationError, match="readable article text"):
        extract_article_text_from_html(html, url="https://example.com/blocked")


def test_extract_text_from_pdf_combines_selectable_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pdf_reader(
        monkeypatch,
        [
            FakePage(" Page one text. \n\n"),
            FakePage("Page two text."),
        ],
    )

    text = extract_text_from_pdf(Path("paper.pdf"))

    assert text == "Page one text.\n\nPage two text."


def test_extract_text_from_pdf_errors_for_empty_or_scanned_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pdf_reader(monkeypatch, [FakePage()])

    with pytest.raises(ValidationError, match="No selectable text"):
        extract_text_from_pdf(Path("scanned.pdf"))


def test_extract_text_from_pdf_errors_for_encrypted_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pdf_reader(monkeypatch, [], encrypted=True)

    with pytest.raises(ValidationError, match="Encrypted PDFs"):
        extract_text_from_pdf(Path("locked.pdf"))


def test_extract_source_text_from_image_reports_local_ocr_provenance(tmp_path: Path) -> None:
    image_path = tmp_path / "public-fixture.png"
    Image.new("RGB", (80, 40), "white").save(image_path)
    manager = FakeOCRManager([_ocr_result("Public fixture text.", confidence=93.25)])

    result = extract_source_text_from_image(image_path, ocr_manager=manager)  # type: ignore[arg-type]

    assert result.text == "Public fixture text."
    assert result.source_kind == "image"
    assert result.method == "ocr"
    assert result.pages[0].confidence == 93.25
    assert result.ocr_engine == "tesseract"
    provenance = result.provenance()
    assert provenance["local_only"] is True
    assert provenance["source"]["filename"] == "public-fixture.png"
    assert provenance["ocr"]["language"] == "eng"


def test_extract_source_text_from_image_honors_never_mode(tmp_path: Path) -> None:
    image_path = tmp_path / "fixture.png"
    image_path.write_bytes(b"not-read")

    with pytest.raises(ValidationError, match="--ocr-mode never"):
        extract_source_text_from_image(image_path, ocr_mode=OCRMode.NEVER)


def test_extract_source_text_from_image_rejects_corrupt_input(tmp_path: Path) -> None:
    image_path = tmp_path / "corrupt.png"
    image_path.write_bytes(b"this is not an image")

    with pytest.raises(ValidationError, match="Could not read local image"):
        extract_source_text_from_image(image_path)


def test_extract_source_text_from_image_rejects_oversized_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HugeImage:
        width = 10_000
        height = 5_000

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    image_path = tmp_path / "huge.png"
    image_path.write_bytes(b"synthetic oversized header")
    monkeypatch.setattr("PIL.Image.open", lambda _path: HugeImage())

    with pytest.raises(ValidationError, match="40,000,000-pixel OCR limit"):
        extract_source_text_from_image(image_path)


def test_extract_source_text_from_pdf_combines_selectable_and_ocr_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "mixed.pdf"
    pdf_path.write_bytes(b"synthetic mixed PDF fixture")
    _patch_pdf_reader(
        monkeypatch,
        [
            FakePage("Selectable text on the first page is long enough."),
            FakePage(""),
        ],
    )
    rendered_image = FakeImage()
    manager = FakeOCRManager([_ocr_result("OCR text on page two.", page=2)])

    result = extract_source_text_from_pdf(
        pdf_path,
        ocr_manager=manager,  # type: ignore[arg-type]
        rendered_pages=[RenderedPDFPage(1, rendered_image, 300.0)],
    )

    assert result.text == (
        "Selectable text on the first page is long enough.\n\nOCR text on page two."
    )
    assert result.method == "hybrid"
    assert [page.extraction_method for page in result.pages] == ["selectable_text", "ocr"]
    assert result.pages[1].render_dpi == 300.0
    assert result.ocr_engine == "tesseract"
    assert rendered_image.closed is True
    assert manager.requests[0].page_number == 2


def test_extract_source_text_from_pdf_always_ocrs_every_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "multipage.pdf"
    pdf_path.write_bytes(b"synthetic multipage PDF fixture")
    _patch_pdf_reader(monkeypatch, [FakePage("Selectable one"), FakePage("Selectable two")])
    manager = FakeOCRManager(
        [
            _ocr_result("OCR page one", page=1),
            _ocr_result("OCR page two", page=2),
        ]
    )

    result = extract_source_text_from_pdf(
        pdf_path,
        ocr_mode=OCRMode.ALWAYS,
        ocr_manager=manager,  # type: ignore[arg-type]
        rendered_pages=[
            RenderedPDFPage(0, FakeImage(), 300.0),
            RenderedPDFPage(1, FakeImage(), 300.0),
        ],
    )

    assert result.text == "OCR page one\n\nOCR page two"
    assert result.method == "ocr"
    assert [request.page_number for request in manager.requests] == [1, 2]


def test_pdf_auto_mode_keeps_thin_selectable_text_when_ocr_confidence_is_low(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "thin.pdf"
    pdf_path.write_bytes(b"synthetic thin PDF fixture")
    _patch_pdf_reader(monkeypatch, [FakePage("Small label")])
    manager = FakeOCRManager([OCRLowConfidenceError(8.0, 1)])

    result = extract_source_text_from_pdf(
        pdf_path,
        ocr_manager=manager,  # type: ignore[arg-type]
        rendered_pages=[RenderedPDFPage(0, FakeImage(), 300.0)],
    )

    assert result.text == "Small label"
    assert result.method == "selectable_text"
    assert result.pages[0].extraction_method == "selectable_text"
    assert "confidence was 8.0%" in result.warnings[0]


def test_pdf_without_selectable_text_rejects_low_confidence_ocr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "unreadable.pdf"
    pdf_path.write_bytes(b"synthetic unreadable PDF fixture")
    _patch_pdf_reader(monkeypatch, [FakePage("")])
    manager = FakeOCRManager([OCRLowConfidenceError(9.0, 1)])

    with pytest.raises(OCRLowConfidenceError, match="page 1"):
        extract_source_text_from_pdf(
            pdf_path,
            ocr_manager=manager,  # type: ignore[arg-type]
            rendered_pages=[RenderedPDFPage(0, FakeImage(), 300.0)],
        )


def test_pdf_empty_ocr_result_fails_when_document_has_no_other_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"synthetic empty PDF fixture")
    _patch_pdf_reader(monkeypatch, [FakePage("")])
    manager = FakeOCRManager([OCREmptyResultError("No readable text")])

    with pytest.raises(ValidationError, match="No readable text found in PDF"):
        extract_source_text_from_pdf(
            pdf_path,
            ocr_manager=manager,  # type: ignore[arg-type]
            rendered_pages=[RenderedPDFPage(0, FakeImage(), 300.0)],
        )


def test_extract_source_text_from_pdf_rejects_corrupt_input(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_bytes(b"this is not a PDF")

    with pytest.raises(ValidationError, match="Could not read PDF"):
        extract_source_text_from_pdf(pdf_path)


def test_source_provenance_is_deterministic_and_omits_absolute_path(tmp_path: Path) -> None:
    source_path = tmp_path / "public.txt"
    source_path.write_text("Public deterministic source", encoding="utf-8")
    result = SourceTextResult(
        text="Public deterministic source",
        source_kind="image",
        media_type="image/png",
        source_path=source_path,
        method="ocr",
        pages=(),
        ocr_engine="tesseract",
        ocr_engine_version="5.5.1",
        ocr_language="eng",
    )

    first = result.provenance()
    second = result.provenance()

    assert first == second
    assert first["source"]["filename"] == "public.txt"
    assert str(tmp_path) not in str(first)


def test_pdf_render_scale_caps_large_pages() -> None:
    scale = _bounded_pdf_render_scale(20_000, 20_000)

    assert 20_000 * scale * 20_000 * scale <= PDF_OCR_MAX_RENDER_PIXELS + 1
