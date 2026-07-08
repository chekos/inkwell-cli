"""Local source-text extraction for article URLs and text PDFs."""

from __future__ import annotations

from pathlib import Path

import httpx
import trafilatura
from pypdf import PdfReader

from inkwell.utils.errors import ValidationError

ARTICLE_MIN_CHARACTERS = 80
ARTICLE_TIMEOUT_SECONDS = 15.0
ARTICLE_USER_AGENT = "inkwell-cli/0.1 (+https://github.com/chekos/inkwell-cli)"


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
    """Extract selectable text from a local text PDF."""
    try:
        reader = PdfReader(path)
    except Exception as e:
        raise ValidationError(
            f"Could not read PDF file: {path}",
            suggestion="Only unencrypted text PDFs are supported right now.",
        ) from e

    if reader.is_encrypted:
        raise ValidationError(
            f"Encrypted PDFs are not supported: {path}",
            suggestion="Export an unencrypted text PDF, or convert the content to .txt or .md.",
        )

    pages: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception as e:
            raise ValidationError(
                f"Could not extract selectable text from PDF: {path}",
                suggestion="Text-only PDFs are supported; OCR/image PDFs are deferred to #111.",
            ) from e
        page_text = _normalize_extracted_text(page_text)
        if page_text:
            pages.append(page_text)

    text = "\n\n".join(pages).strip()
    if not text:
        raise ValidationError(
            "No selectable text found in PDF",
            suggestion=(
                "Text-only PDF extraction is supported now. OCR/image PDF support "
                "is deferred to #111."
            ),
        )
    return text


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
