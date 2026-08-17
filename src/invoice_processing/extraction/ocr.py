from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

from invoice_processing.config import get_settings
from invoice_processing.domain.enums import ExtractionMethod
from invoice_processing.extraction.base import ExtractedDocument, ExtractedPage, ExtractionError


def extract_ocr(pdf_path: Path) -> ExtractedDocument:
    # Same rationale as extract_text_layer: poppler (via pdf2image) and tesseract each
    # raise their own exception types on a PDF they can't handle -- normalize all of
    # that to our own ExtractionError.
    settings = get_settings()
    try:
        images = convert_from_path(str(pdf_path), dpi=settings.ocr_dpi)
        pages = [
            ExtractedPage(page_number=page_number, text=pytesseract.image_to_string(image))
            for page_number, image in enumerate(images, start=1)
        ]
    except Exception as exc:
        raise ExtractionError(f"'{pdf_path.name}' could not be OCR'd: {exc}") from exc
    return ExtractedDocument(
        source_filename=pdf_path.name,
        method=ExtractionMethod.OCR,
        pages=pages,
    )
