from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

from invoice_processing.config import get_settings
from invoice_processing.domain.enums import ExtractionMethod
from invoice_processing.extraction.base import ExtractedDocument, ExtractedPage


def extract_ocr(pdf_path: Path) -> ExtractedDocument:
    settings = get_settings()
    images = convert_from_path(str(pdf_path), dpi=settings.ocr_dpi)

    pages = [
        ExtractedPage(page_number=page_number, text=pytesseract.image_to_string(image))
        for page_number, image in enumerate(images, start=1)
    ]
    return ExtractedDocument(
        source_filename=pdf_path.name,
        method=ExtractionMethod.OCR,
        pages=pages,
    )
