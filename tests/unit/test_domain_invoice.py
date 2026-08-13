from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from invoice_processing.domain.invoice import Invoice, LineItem, Party


def _base_kwargs() -> dict:
    return dict(
        invoice_number="INV-1",
        vendor=Party(name="Acme"),
        issue_date=date(2026, 1, 1),
        currency="USD",
        total_amount=Decimal("100.00"),
    )


def test_invoice_constructs_with_required_fields():
    invoice = Invoice(**_base_kwargs())
    assert invoice.total_amount == Decimal("100.00")
    assert invoice.line_items == []


def test_invoice_rejects_invalid_currency_format():
    kwargs = _base_kwargs()
    kwargs["currency"] = "usd"
    with pytest.raises(ValidationError):
        Invoice(**kwargs)


def test_line_item_holds_decimal_values():
    item = LineItem(
        description="Widget",
        quantity=Decimal("2"),
        unit_price=Decimal("10.00"),
        extended_price=Decimal("20.00"),
    )
    assert item.extended_price == Decimal("20.00")
