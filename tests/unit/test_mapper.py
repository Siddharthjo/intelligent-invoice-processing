from datetime import date
from decimal import Decimal

import pytest

from invoice_processing.domain.enums import ExtractionMethod
from invoice_processing.extraction.base import ExtractedDocument, ExtractedPage
from invoice_processing.parsing.mapper import MappingError, map_to_invoice


def _document(text: str, tables=None) -> ExtractedDocument:
    return ExtractedDocument(
        source_filename="test.pdf",
        method=ExtractionMethod.TEXT_LAYER,
        pages=[ExtractedPage(page_number=1, text=text, tables=tables or [])],
    )


def test_map_to_invoice_extracts_core_fields():
    text = (
        "Acme Supplies Inc.\n"
        "Invoice Number: INV-1001\n"
        "Invoice Date: January 15, 2026\n"
        "Due Date: February 14, 2026\n"
        "Subtotal: $50.00\n"
        "Tax: $5.00\n"
        "Total: $55.00\n"
    )
    invoice = map_to_invoice(_document(text))

    assert invoice.invoice_number == "INV-1001"
    assert invoice.vendor.name == "Acme Supplies Inc."
    assert invoice.issue_date == date(2026, 1, 15)
    assert invoice.due_date == date(2026, 2, 14)
    assert invoice.subtotal == Decimal("50.00")
    assert invoice.total_amount == Decimal("55.00")


def test_map_to_invoice_raises_when_required_fields_missing():
    with pytest.raises(MappingError):
        map_to_invoice(_document("Nothing useful here."))
