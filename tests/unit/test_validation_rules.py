from datetime import date, timedelta
from decimal import Decimal

from invoice_processing.domain.invoice import Invoice, LineItem, Party
from invoice_processing.validation import rules
from invoice_processing.validation.result import Severity


def _invoice(**overrides) -> Invoice:
    base = dict(
        invoice_number="INV-1",
        vendor=Party(name="Acme"),
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        currency="USD",
        line_items=[
            LineItem(
                description="Widget",
                quantity=Decimal("2"),
                unit_price=Decimal("10.00"),
                extended_price=Decimal("20.00"),
            )
        ],
        subtotal=Decimal("20.00"),
        tax_amount=Decimal("2.00"),
        discount_amount=None,
        total_amount=Decimal("22.00"),
    )
    base.update(overrides)
    return Invoice(**base)


def test_valid_invoice_has_no_error_issues():
    issues = rules.run_rules(_invoice())
    assert not any(issue.severity == Severity.ERROR for issue in issues)


def test_rule_total_amount_positive_flags_zero():
    issues = rules.rule_total_amount_positive(_invoice(total_amount=Decimal("0")))
    assert issues[0].rule_code == "NON_POSITIVE_TOTAL"


def test_rule_currency_valid_flags_unknown_code():
    issues = rules.rule_currency_valid(_invoice(currency="ZZZ"))
    assert issues[0].rule_code == "INVALID_CURRENCY_CODE"


def test_rule_due_date_before_issue_date():
    issues = rules.rule_due_date_after_issue_date(_invoice(due_date=date(2025, 12, 1)))
    assert issues[0].rule_code == "DUE_DATE_BEFORE_ISSUE_DATE"


def test_rule_issue_date_in_future():
    issues = rules.rule_issue_date_not_in_future(_invoice(issue_date=date.today() + timedelta(days=30)))
    assert issues[0].rule_code == "ISSUE_DATE_IN_FUTURE"


def test_rule_line_items_present_warns_when_empty():
    issues = rules.rule_line_items_present(_invoice(line_items=[]))
    assert issues[0].rule_code == "NO_LINE_ITEMS_EXTRACTED"
    assert issues[0].severity == Severity.WARNING


def test_rule_line_item_math_mismatch():
    mismatched = LineItem(
        description="Widget",
        quantity=Decimal("2"),
        unit_price=Decimal("10.00"),
        extended_price=Decimal("25.00"),
    )
    issues = rules.rule_line_item_math(_invoice(line_items=[mismatched]))
    assert issues[0].rule_code == "LINE_ITEM_MATH_MISMATCH"


def test_rule_subtotal_mismatch():
    issues = rules.rule_subtotal_matches_line_items(_invoice(subtotal=Decimal("999.00")))
    assert issues[0].rule_code == "SUBTOTAL_MISMATCH"


def test_rule_total_mismatch():
    issues = rules.rule_total_matches_components(_invoice(total_amount=Decimal("999.00")))
    assert issues[0].rule_code == "TOTAL_MISMATCH"


def test_duplicate_invoice_issue():
    issue = rules.duplicate_invoice_issue(vendor_name="Acme", invoice_number="INV-1")
    assert issue.rule_code == "DUPLICATE_INVOICE"
    assert issue.severity == Severity.ERROR
