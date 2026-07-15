"""Local source-text extraction for articles, images, and PDFs."""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
import trafilatura
from pypdf import PdfReader

from inkwell.plugins.types.ocr import OCRRequest
from inkwell.utils.errors import ValidationError

from .models import ExtractionMethod, SourcePageProvenance, SourceTextResult
from .ocr import (
    OCR_INSTALL_SUGGESTION,
    OCREmptyResultError,
    OCRLowConfidenceError,
    OCRManager,
)

ARTICLE_MIN_CHARACTERS = 80
ARTICLE_TIMEOUT_SECONDS = 15.0
ARTICLE_USER_AGENT = "inkwell-cli/0.1 (+https://github.com/chekos/inkwell-cli)"
PDF_SELECTABLE_TEXT_MIN_CHARACTERS = 20
PDF_OCR_RENDER_DPI = 300.0
PDF_OCR_MAX_RENDER_PIXELS = 40_000_000
PDF_OCR_MAX_PAGES = 250
OCR_MAX_IMAGE_PIXELS = 40_000_000
OCR_MIN_CONFIDENCE = 30.0
OCR_TIMEOUT_SECONDS = 120.0

_IMAGE_MEDIA_TYPES = {
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pbm": "image/x-portable-bitmap",
    ".pgm": "image/x-portable-graymap",
    ".png": "image/png",
    ".pnm": "image/x-portable-anymap",
    ".ppm": "image/x-portable-pixmap",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


class OCRMode(str, Enum):
    """When PDF/image ingestion is allowed to invoke local OCR."""

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


@dataclass(frozen=True)
class RenderedPDFPage:
    """One rendered PDF page yielded without retaining the whole document."""

    page_index: int
    image: object
    render_dpi: float


def extract_article_text_from_url(url: str) -> str:
    """Fetch an HTTP(S) URL and extract readable article text locally."""
    html = fetch_article_html(url)
    return extract_article_text_from_html(html, url=url)


def fetch_article_html(url: str) -> str:
    """Fetch article HTML with user-facing failure messages."""
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=ARTICLE_TIMEOUT_SECONDS,
            headers={"User-Agent": ARTICLE_USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ValidationError(
            f"Article URL returned HTTP {e.response.status_code}: {url}",
            suggestion=(
                "Local-only article extraction cannot bypass blocked pages. "
                "Hosted extraction fallbacks are deferred to #112."
            ),
        ) from e
    except httpx.RequestError as e:
        raise ValidationError(
            f"Could not fetch article URL locally: {url}",
            suggestion=(
                "Check the URL or network connection. Hosted extraction fallbacks "
                "are deferred to #112."
            ),
        ) from e

    content_type = response.headers.get("content-type", "").lower()
    if content_type and not any(
        accepted in content_type
        for accepted in ("text/html", "application/xhtml+xml", "application/xml")
    ):
        raise ValidationError(
            f"Article URL did not return HTML content: {content_type}",
            suggestion="Use direct media URLs for audio/video, or provide a readable HTML article.",
        )

    if not response.text.strip():
        raise ValidationError(
            "Article URL returned an empty response",
            suggestion=(
                "The page may be blocked or script-rendered. Hosted fallbacks are deferred to #112."
            ),
        )

    return response.text


def extract_article_text_from_html(html: str, *, url: str | None = None) -> str:
    """Extract readable article text from an HTML string using local parsing."""
    if not html.strip():
        raise ValidationError(
            "Article HTML is empty",
            suggestion="Provide a readable HTML page or use local text input.",
        )

    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="txt",
        include_comments=False,
        include_tables=True,
        deduplicate=True,
    )
    text = _normalize_extracted_text(extracted or "")
    if len(text) < ARTICLE_MIN_CHARACTERS:
        raise ValidationError(
            "Could not extract readable article text locally",
            suggestion=(
                "The page may be blocked, script-rendered, or too thin. "
                "Hosted extraction fallbacks are deferred to #112."
            ),
        )
    return text


def extract_text_from_pdf(path: Path) -> str:
    """Extract selectable text from a PDF without invoking optional OCR.

    This compatibility wrapper preserves the pre-OCR programmatic contract.
    Use :func:`extract_source_text_from_pdf` for automatic OCR and provenance.
    """
    return extract_source_text_from_pdf(path, ocr_mode=OCRMode.NEVER).text


def extract_source_text_from_image(
    path: Path,
    *,
    ocr_mode: OCRMode = OCRMode.AUTO,
    ocr_engine: str | None = None,
    ocr_language: str = "eng",
    ocr_manager: OCRManager | None = None,
) -> SourceTextResult:
    """Extract local image text through the selected OCR plugin."""
    if ocr_mode is OCRMode.NEVER:
        raise ValidationError(
            "Local image files require OCR, but --ocr-mode never was selected",
            suggestion="Use --ocr-mode auto (the default) or --ocr-mode always.",
        )

    try:
        from PIL import Image, UnidentifiedImageError
    except ModuleNotFoundError as e:
        raise ValidationError(
            "Local image OCR dependencies are not installed",
            suggestion=OCR_INSTALL_SUGGESTION,
        ) from e

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as opened_image:
                if opened_image.width * opened_image.height > OCR_MAX_IMAGE_PIXELS:
                    raise ValidationError(
                        f"Local image exceeds the {OCR_MAX_IMAGE_PIXELS:,}-pixel OCR limit",
                        suggestion="Resize or split the image before running local OCR.",
                    )
                opened_image.load()
                image = opened_image.copy()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
    ) as e:
        raise ValidationError(
            f"Could not read local image file: {path}",
            suggestion="Use a valid PNG, JPEG, TIFF, BMP, GIF, WebP, or PNM image.",
        ) from e

    manager = ocr_manager or OCRManager(engine=ocr_engine)
    try:
        ocr_result = manager.extract(
            OCRRequest(
                image=image,
                source_label=path.name,
                page_number=1,
                language=ocr_language,
                min_confidence=OCR_MIN_CONFIDENCE,
                timeout_seconds=OCR_TIMEOUT_SECONDS,
            )
        )
    finally:
        image.close()

    text = _normalize_extracted_text(ocr_result.text)
    return SourceTextResult(
        text=text,
        source_kind="image",
        media_type=_IMAGE_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        source_path=path,
        method="ocr",
        pages=(
            SourcePageProvenance(
                page_number=1,
                extraction_method="ocr",
                character_count=len(text),
                confidence=ocr_result.confidence,
                rotation_degrees=ocr_result.rotation_degrees,
                orientation_confidence=ocr_result.orientation_confidence,
            ),
        ),
        ocr_engine=ocr_result.engine,
        ocr_engine_version=ocr_result.engine_version,
        ocr_language=ocr_language,
    )


def extract_source_text_from_pdf(
    path: Path,
    *,
    ocr_mode: OCRMode = OCRMode.AUTO,
    ocr_engine: str | None = None,
    ocr_language: str = "eng",
    ocr_manager: OCRManager | None = None,
    rendered_pages: Iterable[RenderedPDFPage] | None = None,
) -> SourceTextResult:
    """Extract selectable text and locally OCR pages that need it."""
    try:
        reader = PdfReader(path)
    except Exception as e:
        raise ValidationError(
            f"Could not read PDF file: {path}",
            suggestion="Use a valid, unencrypted PDF.",
        ) from e

    if reader.is_encrypted:
        raise ValidationError(
            f"Encrypted PDFs are not supported: {path}",
            suggestion="Export an unencrypted PDF or convert the content to .txt or .md.",
        )

    page_count = len(reader.pages)
    if page_count == 0:
        raise ValidationError("PDF contains no pages")
    if page_count > PDF_OCR_MAX_PAGES and ocr_mode is not OCRMode.NEVER:
        raise ValidationError(
            f"PDF has {page_count} pages; local OCR is limited to {PDF_OCR_MAX_PAGES}",
            suggestion="Split the document into smaller PDFs and process each part separately.",
        )

    selectable_pages: dict[int, str] = {}
    extraction_failures: set[int] = set()
    for page_index, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            extraction_failures.add(page_index)
            page_text = ""
        page_text = _normalize_extracted_text(page_text)
        if page_text:
            selectable_pages[page_index] = page_text

    if ocr_mode is OCRMode.NEVER:
        if extraction_failures:
            first_page = min(extraction_failures) + 1
            raise ValidationError(
                f"Could not extract selectable text from PDF page {first_page}: {path}",
                suggestion="Install local OCR support or export a text PDF.",
            )
        return _selectable_pdf_result(path, page_count, selectable_pages)

    if ocr_mode is OCRMode.ALWAYS:
        ocr_page_indexes = list(range(page_count))
    else:
        ocr_page_indexes = [
            page_index
            for page_index in range(page_count)
            if len(selectable_pages.get(page_index, "")) < PDF_SELECTABLE_TEXT_MIN_CHARACTERS
            or page_index in extraction_failures
        ]

    if not ocr_page_indexes:
        return _selectable_pdf_result(path, page_count, selectable_pages)

    manager = ocr_manager or OCRManager(engine=ocr_engine)
    page_texts: dict[int, str] = {}
    page_provenance: dict[int, SourcePageProvenance] = {}
    warnings_list: list[str] = []

    if ocr_mode is OCRMode.AUTO:
        for page_index, selectable_text in selectable_pages.items():
            if page_index not in ocr_page_indexes:
                page_texts[page_index] = selectable_text
                page_provenance[page_index] = _selectable_page_provenance(
                    page_index, selectable_text
                )

    ocr_engine_name: str | None = None
    ocr_engine_version: str | None = None
    rendered_page_iterable = (
        rendered_pages
        if rendered_pages is not None
        else _iter_rendered_pdf_pages(path, ocr_page_indexes)
    )
    rendered_indexes: set[int] = set()

    for rendered_page in rendered_page_iterable:
        page_index = rendered_page.page_index
        if page_index not in ocr_page_indexes:
            raise ValidationError(
                f"PDF renderer returned unexpected page {page_index + 1}",
                suggestion="Retry with a valid PDF or report the renderer mismatch.",
            )
        rendered_indexes.add(page_index)
        selectable_fallback = selectable_pages.get(page_index, "")
        try:
            try:
                ocr_result = manager.extract(
                    OCRRequest(
                        image=rendered_page.image,
                        source_label=f"{path.name} page {page_index + 1}",
                        page_number=page_index + 1,
                        language=ocr_language,
                        min_confidence=OCR_MIN_CONFIDENCE,
                        timeout_seconds=OCR_TIMEOUT_SECONDS,
                    )
                )
            except OCREmptyResultError:
                if selectable_fallback and ocr_mode is OCRMode.AUTO:
                    page_texts[page_index] = selectable_fallback
                    page_provenance[page_index] = _selectable_page_provenance(
                        page_index, selectable_fallback
                    )
                    warnings_list.append(
                        f"Page {page_index + 1} OCR was empty; kept available selectable text."
                    )
                    continue
                page_provenance[page_index] = SourcePageProvenance(
                    page_number=page_index + 1,
                    extraction_method="empty",
                    character_count=0,
                    render_dpi=rendered_page.render_dpi,
                )
                warnings_list.append(f"Page {page_index + 1} produced no readable text.")
                continue
            except OCRLowConfidenceError as e:
                if selectable_fallback and ocr_mode is OCRMode.AUTO:
                    page_texts[page_index] = selectable_fallback
                    page_provenance[page_index] = _selectable_page_provenance(
                        page_index, selectable_fallback
                    )
                    warnings_list.append(
                        f"Page {page_index + 1} OCR confidence was {e.confidence:.1f}%; "
                        "kept available selectable text."
                    )
                    continue
                raise

            normalized_ocr_text = _normalize_extracted_text(ocr_result.text)
            page_texts[page_index] = normalized_ocr_text
            page_provenance[page_index] = SourcePageProvenance(
                page_number=page_index + 1,
                extraction_method="ocr",
                character_count=len(normalized_ocr_text),
                confidence=ocr_result.confidence,
                rotation_degrees=ocr_result.rotation_degrees,
                orientation_confidence=ocr_result.orientation_confidence,
                render_dpi=rendered_page.render_dpi,
            )
            ocr_engine_name = ocr_result.engine
            ocr_engine_version = ocr_result.engine_version
        finally:
            close_image = getattr(rendered_page.image, "close", None)
            if callable(close_image):
                close_image()

    missing_rendered_indexes = set(ocr_page_indexes) - rendered_indexes
    if missing_rendered_indexes:
        first_page = min(missing_rendered_indexes) + 1
        raise ValidationError(f"PDF renderer did not return requested page {first_page}")

    ordered_texts = [page_texts[index] for index in range(page_count) if page_texts.get(index)]
    text = "\n\n".join(ordered_texts).strip()
    if not text:
        raise ValidationError(
            "No readable text found in PDF after local extraction",
            suggestion=(
                "Use a clearer scan, verify the page orientation and OCR language, "
                "or convert the document to selectable text."
            ),
        )

    ordered_provenance = tuple(page_provenance[index] for index in range(page_count))
    methods = {
        page.extraction_method for page in ordered_provenance if page.extraction_method != "empty"
    }
    method: ExtractionMethod
    if "ocr" in methods and "selectable_text" in methods:
        method = "hybrid"
    elif "ocr" in methods:
        method = "ocr"
    else:
        method = "selectable_text"
    return SourceTextResult(
        text=text,
        source_kind="pdf",
        media_type="application/pdf",
        source_path=path,
        method=method,
        pages=ordered_provenance,
        ocr_engine=ocr_engine_name,
        ocr_engine_version=ocr_engine_version,
        ocr_language=ocr_language if ocr_engine_name else None,
        warnings=tuple(warnings_list),
    )


def _selectable_pdf_result(
    path: Path,
    page_count: int,
    selectable_pages: dict[int, str],
) -> SourceTextResult:
    """Build the fast-path result for a PDF that does not need OCR."""
    text = "\n\n".join(
        selectable_pages[index] for index in range(page_count) if selectable_pages.get(index)
    ).strip()
    if not text:
        raise ValidationError(
            "No selectable text found in PDF",
            suggestion=(
                "Install the optional local OCR dependencies and use --ocr-mode auto, "
                "or convert the document to selectable text."
            ),
        )
    pages = tuple(
        _selectable_page_provenance(index, selectable_pages[index])
        if selectable_pages.get(index)
        else SourcePageProvenance(
            page_number=index + 1,
            extraction_method="empty",
            character_count=0,
        )
        for index in range(page_count)
    )
    return SourceTextResult(
        text=text,
        source_kind="pdf",
        media_type="application/pdf",
        source_path=path,
        method="selectable_text",
        pages=pages,
    )


def _selectable_page_provenance(page_index: int, text: str) -> SourcePageProvenance:
    """Create provenance for one page read through pypdf."""
    return SourcePageProvenance(
        page_number=page_index + 1,
        extraction_method="selectable_text",
        character_count=len(text),
    )


def _iter_rendered_pdf_pages(
    path: Path,
    page_indexes: Iterable[int],
) -> Iterator[RenderedPDFPage]:
    """Render requested PDF pages at an OCR-friendly bounded resolution."""
    try:
        import pypdfium2 as pdfium
    except ModuleNotFoundError as e:
        raise ValidationError(
            "PDF OCR rendering dependencies are not installed",
            suggestion=OCR_INSTALL_SUGGESTION,
        ) from e

    try:
        pdf = pdfium.PdfDocument(path)
    except Exception as e:
        raise ValidationError(
            f"Could not render PDF for local OCR: {path}",
            suggestion="Use a valid, unencrypted PDF.",
        ) from e

    with pdf:
        for page_index in page_indexes:
            page = pdf[page_index]
            bitmap: Any | None = None
            image: Any | None = None
            try:
                width, height = page.get_size()
                scale = _bounded_pdf_render_scale(width, height)
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                yield RenderedPDFPage(
                    page_index=page_index,
                    image=image,
                    render_dpi=round(scale * 72.0, 2),
                )
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(
                    f"Could not render PDF page {page_index + 1} for local OCR",
                    suggestion="Use a valid PDF or split the document into smaller parts.",
                ) from e
            finally:
                # The caller closes the PIL image immediately after OCR. PDFium
                # page/bitmap handles are safe to release once the generator resumes.
                if bitmap is not None:
                    bitmap.close()
                page.close()


def _bounded_pdf_render_scale(width: float, height: float) -> float:
    """Choose 300 DPI unless that would exceed the per-page pixel safety cap."""
    if width <= 0 or height <= 0:
        raise ValidationError("PDF page has invalid dimensions")
    target_scale = PDF_OCR_RENDER_DPI / 72.0
    bounded_scale = math.sqrt(PDF_OCR_MAX_RENDER_PIXELS / (width * height))
    return min(target_scale, bounded_scale)


def _normalize_extracted_text(text: str) -> str:
    """Trim lines and collapse excessive blank space without reflowing prose."""
    lines = [line.strip() for line in text.splitlines()]
    normalized_lines: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank
    return "\n".join(normalized_lines).strip()
