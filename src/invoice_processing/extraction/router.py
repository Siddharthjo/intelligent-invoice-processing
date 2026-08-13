from pathlib import Path

from invoice_processing.config import get_settings
from invoice_processing.extraction.base import ExtractedDocument, ExtractionError
from invoice_processing.extraction.ocr import extract_ocr
from invoice_processing.extraction.text_layer import extract_text_layer


def extract(pdf_path: Path) -> ExtractedDocument:
    settings = get_settings()
    document = extract_text_layer(pdf_path)

    if _has_sufficient_text(document, settings.text_layer_min_chars_per_page):
        return document

    if not settings.ocr_enabled:
        raise ExtractionError(
            f"'{pdf_path.name}' has no usable text layer and OCR extraction is disabled."
        )

    document = extract_ocr(pdf_path)
    if not _has_sufficient_text(document, settings.text_layer_min_chars_per_page):
        raise ExtractionError(f"'{pdf_path.name}' produced no usable text via text-layer or OCR extraction.")

    return document


def _has_sufficient_text(document: ExtractedDocument, min_chars_per_page: int) -> bool:
    if not document.pages:
        return False
    return all(len(page.text.strip()) >= min_chars_per_page for page in document.pages)
