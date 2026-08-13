from pathlib import Path

import pdfplumber

from invoice_processing.domain.enums import ExtractionMethod
from invoice_processing.extraction.base import ExtractedDocument, ExtractedPage


def extract_text_layer(pdf_path: Path) -> ExtractedDocument:
    pages: list[ExtractedPage] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    text=page.extract_text() or "",
                    tables=page.extract_tables(),
                )
            )
    return ExtractedDocument(
        source_filename=pdf_path.name,
        method=ExtractionMethod.TEXT_LAYER,
        pages=pages,
    )
