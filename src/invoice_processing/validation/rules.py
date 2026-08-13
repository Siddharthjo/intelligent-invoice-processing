from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

from invoice_processing.domain.invoice import Invoice
from invoice_processing.validation.currencies import ISO_4217_CODES
from invoice_processing.validation.result import Severity, ValidationIssue

MONEY_TOLERANCE = Decimal("0.01")

Rule = Callable[[Invoice], list[ValidationIssue]]


def rule_total_amount_positive(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.total_amount <= 0:
        return [
            ValidationIssue(
                rule_code="NON_POSITIVE_TOTAL",
                severity=Severity.ERROR,
                message=f"total_amount must be positive, got {invoice.total_amount}.",
            )
        ]
    return []


def rule_currency_valid(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.currency not in ISO_4217_CODES:
        return [
            ValidationIssue(
                rule_code="INVALID_CURRENCY_CODE",
                severity=Severity.ERROR,
                message=f"'{invoice.currency}' is not a recognized ISO 4217 currency code.",
            )
        ]
    return []


def rule_due_date_after_issue_date(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.due_date is not None and invoice.due_date < invoice.issue_date:
        return [
            ValidationIssue(
                rule_code="DUE_DATE_BEFORE_ISSUE_DATE",
                severity=Severity.ERROR,
                message=f"due_date {invoice.due_date} is before issue_date {invoice.issue_date}.",
            )
        ]
    return []


def rule_issue_date_not_in_future(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.issue_date > date.today() + timedelta(days=1):
        return [
            ValidationIssue(
                rule_code="ISSUE_DATE_IN_FUTURE",
                severity=Severity.ERROR,
                message=f"issue_date {invoice.issue_date} is in the future.",
            )
        ]
    return []


def rule_line_items_present(invoice: Invoice) -> list[ValidationIssue]:
    if not invoice.line_items:
        return [
            ValidationIssue(
                rule_code="NO_LINE_ITEMS_EXTRACTED",
                severity=Severity.WARNING,
                message="No line items were extracted from this invoice.",
            )
        ]
    return []


def rule_line_item_math(invoice: Invoice) -> list[ValidationIssue]:
    issues = []
    for index, item in enumerate(invoice.line_items, start=1):
        expected = item.quantity * item.unit_price
        if abs(expected - item.extended_price) > MONEY_TOLERANCE:
            issues.append(
                ValidationIssue(
                    rule_code="LINE_ITEM_MATH_MISMATCH",
                    severity=Severity.ERROR,
                    message=(
                        f"Line item {index} ('{item.description}'): "
                        f"quantity ({item.quantity}) * unit_price ({item.unit_price}) = {expected}, "
                        f"but extended_price is {item.extended_price}."
                    ),
                )
            )
    return issues


def rule_subtotal_matches_line_items(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.subtotal is None or not invoice.line_items:
        return []
    computed = sum((item.extended_price for item in invoice.line_items), Decimal("0"))
    if abs(computed - invoice.subtotal) > MONEY_TOLERANCE:
        return [
            ValidationIssue(
                rule_code="SUBTOTAL_MISMATCH",
                severity=Severity.ERROR,
                message=(
                    f"Sum of line item extended_price ({computed}) does not match "
                    f"subtotal ({invoice.subtotal})."
                ),
            )
        ]
    return []


def rule_total_matches_components(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.subtotal is None:
        return []
    tax = invoice.tax_amount or Decimal("0")
    discount = invoice.discount_amount or Decimal("0")
    expected_total = invoice.subtotal + tax - discount
    if abs(expected_total - invoice.total_amount) > MONEY_TOLERANCE:
        return [
            ValidationIssue(
                rule_code="TOTAL_MISMATCH",
                severity=Severity.ERROR,
                message=(
                    f"subtotal ({invoice.subtotal}) + tax ({tax}) - discount ({discount}) "
                    f"= {expected_total}, but total_amount is {invoice.total_amount}."
                ),
            )
        ]
    return []


RULES: list[Rule] = [
    rule_total_amount_positive,
    rule_currency_valid,
    rule_due_date_after_issue_date,
    rule_issue_date_not_in_future,
    rule_line_items_present,
    rule_line_item_math,
    rule_subtotal_matches_line_items,
    rule_total_matches_components,
]


def run_rules(invoice: Invoice) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for rule in RULES:
        issues.extend(rule(invoice))
    return issues


def duplicate_invoice_issue(*, vendor_name: str, invoice_number: str) -> ValidationIssue:
    return ValidationIssue(
        rule_code="DUPLICATE_INVOICE",
        severity=Severity.ERROR,
        message=f"An invoice with number '{invoice_number}' from vendor '{vendor_name}' already exists.",
    )
