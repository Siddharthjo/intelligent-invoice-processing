from pathlib import Path

import pytest

from invoice_processing.domain.enums import ExtractionMethod
from invoice_processing.extraction.base import ExtractionError
from invoice_processing.extraction.text_layer import extract_text_layer
from invoice_processing.parsing.mapper import map_to_invoice


def test_extract_text_layer_reads_real_pdf(sample_invoice_pdf: Path):
    document = extract_text_layer(sample_invoice_pdf)

    assert document.method == ExtractionMethod.TEXT_LAYER
    assert document.page_count == 1
    assert "INV-1001" in document.full_text
    assert document.tables, "expected the ruled line-item table to be detected"


def test_extract_and_map_end_to_end(sample_invoice_pdf: Path):
    document = extract_text_layer(sample_invoice_pdf)
    invoice = map_to_invoice(document)

    assert invoice.invoice_number == "INV-1001"
    assert invoice.vendor.name == "Acme Supplies Inc."
    assert len(invoice.line_items) == 2
    assert invoice.line_items[0].description == "Widget A"


def test_extract_text_layer_wraps_unparseable_pdf_as_extraction_error(tmp_path: Path):
    # A genuinely malformed PDF -- not a valid PDF at all -- must surface as our own
    # typed ExtractionError, not a raw pdfplumber/pdfminer exception. This is what
    # broke Gmail intake on a real-world attachment before this was fixed: an unhandled
    # third-party exception crashed the whole poll instead of failing just that message.
    bogus_pdf = tmp_path / "not_really_a_pdf.pdf"
    bogus_pdf.write_bytes(b"this is not a PDF file at all, just plain bytes")

    with pytest.raises(ExtractionError):
        extract_text_layer(bogus_pdf)
