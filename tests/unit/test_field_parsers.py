from datetime import date
from decimal import Decimal

from invoice_processing.parsing import fields


def test_parse_invoice_number():
    text = "Invoice Number: INV-1001\nSome other text"
    assert fields.parse_invoice_number(text) == "INV-1001"


def test_parse_date():
    text = "Invoice Date: January 15, 2026"
    assert fields.parse_date(text, "issue_date") == date(2026, 1, 15)


def test_parse_decimal_strips_currency_symbols_and_commas():
    assert fields.parse_decimal("$1,234.56") == Decimal("1234.56")


def test_parse_decimal_returns_none_for_empty():
    assert fields.parse_decimal(None) is None
    assert fields.parse_decimal("") is None


def test_parse_currency_from_symbol():
    assert fields.parse_currency("Total: $55.00") == "USD"


def test_parse_currency_defaults_to_usd():
    assert fields.parse_currency("no currency info here") == "USD"


def test_parse_vendor_name_returns_first_nonblank_line():
    text = "\n\nAcme Supplies Inc.\nInvoice Number: INV-1"
    assert fields.parse_vendor_name(text) == "Acme Supplies Inc."
