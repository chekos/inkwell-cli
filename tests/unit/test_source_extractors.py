"""Tests for local article and PDF source extraction."""

from pathlib import Path

import pytest

from inkwell.ingestion.source_extractors import (
    extract_article_text_from_html,
    extract_text_from_pdf,
)
from inkwell.utils.errors import ValidationError


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
    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        is_encrypted = False
        pages = [
            FakePage(" Page one text. \n\n"),
            FakePage("Page two text."),
        ]

    monkeypatch.setattr("inkwell.ingestion.source_extractors.PdfReader", lambda _path: FakeReader())

    text = extract_text_from_pdf(Path("paper.pdf"))

    assert text == "Page one text.\n\nPage two text."


def test_extract_text_from_pdf_errors_for_empty_or_scanned_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return ""

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

    monkeypatch.setattr("inkwell.ingestion.source_extractors.PdfReader", lambda _path: FakeReader())

    with pytest.raises(ValidationError, match="No selectable text"):
        extract_text_from_pdf(Path("scanned.pdf"))


def test_extract_text_from_pdf_errors_for_encrypted_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeReader:
        is_encrypted = True
        pages: list[object] = []

    monkeypatch.setattr("inkwell.ingestion.source_extractors.PdfReader", lambda _path: FakeReader())

    with pytest.raises(ValidationError, match="Encrypted PDFs"):
        extract_text_from_pdf(Path("locked.pdf"))
