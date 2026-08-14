import re
from datetime import date
from decimal import Decimal, InvalidOperation

from dateutil import parser as dateutil_parser

_LABEL_PATTERNS: dict[str, list[str]] = {
    "invoice_number": [r"invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*(\S+)"],
    "issue_date": [
        r"invoice\s*date\s*[:\-]?\s*([A-Za-z0-9,/\-\s]+?)(?:\n|$)",
        r"\bdate\s*[:\-]?\s*([A-Za-z0-9,/\-\s]+?)(?:\n|$)",
    ],
    "due_date": [r"due\s*date\s*[:\-]?\s*([A-Za-z0-9,/\-\s]+?)(?:\n|$)"],
    "subtotal": [r"sub-?total\s*[:\-]?\s*([^\n]+)"],
    # The (?=[$\d]) lookahead requires what follows to actually look like a monetary
    # value, so a "VAT Number: ..." or "Tax ID: ..." label line (neither an amount)
    # doesn't get mistaken for the tax_amount field.
    "tax_amount": [r"\b(?:tax|vat|gst)\b\s*[:\-]?\s*(?=[$\d])([^\n]+)"],
    "discount_amount": [r"\bdiscount\b\s*[:\-]?\s*([^\n]+)"],
    "total_amount": [r"(?:grand\s*total|amount\s*due|total\s*due|\btotal\b)\s*[:\-]?\s*([^\n]+)"],
    "po_number": [r"(?:PO\s*Number|PO\s*#|Purchase\s*Order)\s*[:\-]?\s*(\S+)"],
    "vendor_tax_id": [r"(?:VAT\s*Number|VAT|Tax\s*ID)\s*[:\-]?\s*(\S+)"],
    "vendor_country": [r"Country\s*[:\-]?\s*([^\n]+)"],
}

_CURRENCY_SYMBOL_TO_CODE = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}


def find_label(text: str, field: str) -> str | None:
    for pattern in _LABEL_PATTERNS[field]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def parse_invoice_number(text: str) -> str | None:
    return find_label(text, "invoice_number")


def parse_po_number(text: str) -> str | None:
    return find_label(text, "po_number")


def parse_vendor_tax_id(text: str) -> str | None:
    return find_label(text, "vendor_tax_id")


def parse_vendor_country(text: str) -> str | None:
    return find_label(text, "vendor_country")


def parse_date(text: str, field: str) -> date | None:
    raw = find_label(text, field)
    if not raw:
        return None
    try:
        return dateutil_parser.parse(raw, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", raw.replace(",", ""))
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_money_field(text: str, field: str) -> Decimal | None:
    return parse_decimal(find_label(text, field))


def parse_currency(text: str) -> str:
    for symbol, code in _CURRENCY_SYMBOL_TO_CODE.items():
        if symbol in text:
            return code
    match = re.search(r"\b([A-Z]{3})\b(?=\s*[\d,]+\.\d{2})", text)
    if match:
        return match.group(1)
    return "USD"


def parse_vendor_name(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None
