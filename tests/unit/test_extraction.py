from pathlib import Path

from invoice_processing.domain.enums import ExtractionMethod
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
