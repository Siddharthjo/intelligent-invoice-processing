from pathlib import Path

import pdfplumber

from invoice_processing.domain.enums import ExtractionMethod
from invoice_processing.extraction.base import ExtractedDocument, ExtractedPage, ExtractionError


def extract_text_layer(pdf_path: Path) -> ExtractedDocument:
    # pdfplumber/pdfminer raise their own exception types (PdfminerException,
    # PDFSyntaxError, ...) on malformed, encrypted, or otherwise unparseable PDFs --
    # real-world attachments (e.g. from Gmail intake) hit this far more often than the
    # synthetic PDFs used in tests. Wrap broadly so callers only ever need to handle
    # our own ExtractionError, not every third-party parser exception.
    pages: list[ExtractedPage] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                pages.append(
                    ExtractedPage(
                        page_number=page_number,
                        text=page.extract_text() or "",
                        tables=page.extract_tables(),
                    )
                )
    except Exception as exc:
        raise ExtractionError(f"'{pdf_path.name}' could not be parsed as a PDF: {exc}") from exc
    return ExtractedDocument(
        source_filename=pdf_path.name,
        method=ExtractionMethod.TEXT_LAYER,
        pages=pages,
    )
