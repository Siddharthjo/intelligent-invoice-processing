from invoice_processing.domain.invoice import Invoice, Party
from invoice_processing.extraction.base import ExtractedDocument
from invoice_processing.parsing import fields
from invoice_processing.parsing.line_items import parse_line_items


class MappingError(Exception):
    """Raised when required invoice fields cannot be parsed from the extracted document."""


def map_to_invoice(document: ExtractedDocument) -> Invoice:
    text = document.full_text

    invoice_number = fields.parse_invoice_number(text)
    vendor_name = fields.parse_vendor_name(text)
    issue_date = fields.parse_date(text, "issue_date")
    total_amount = fields.parse_money_field(text, "total_amount")

    missing = [
        name
        for name, value in (
            ("invoice_number", invoice_number),
            ("vendor_name", vendor_name),
            ("issue_date", issue_date),
            ("total_amount", total_amount),
        )
        if value is None
    ]
    if missing:
        raise MappingError(f"Could not extract required field(s): {', '.join(missing)}")

    return Invoice(
        invoice_number=invoice_number,
        vendor=Party(name=vendor_name),
        issue_date=issue_date,
        due_date=fields.parse_date(text, "due_date"),
        currency=fields.parse_currency(text),
        line_items=parse_line_items(document.tables),
        subtotal=fields.parse_money_field(text, "subtotal"),
        tax_amount=fields.parse_money_field(text, "tax_amount"),
        discount_amount=fields.parse_money_field(text, "discount_amount"),
        total_amount=total_amount,
    )
