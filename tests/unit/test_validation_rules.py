from datetime import date, timedelta
from decimal import Decimal

from invoice_processing.domain.invoice import Invoice, LineItem, Party
from invoice_processing.validation import rules
from invoice_processing.validation.context import ValidationContext
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


def _ctx(**overrides) -> ValidationContext:
    return ValidationContext(invoice=_invoice(**overrides), session=None)


# --- PRE tier (pure, no DB) ---------------------------------------------------------


def test_pre_line_items_present_warns_when_empty():
    issues = rules._check_line_items_present(_ctx(line_items=[]))
    assert issues[0].step == "PRE"
    assert issues[0].rule_code == "NO_LINE_ITEMS_EXTRACTED"
    assert issues[0].severity == Severity.WARNING


def test_pre_due_date_before_issue_date():
    issues = rules._check_due_date_after_issue_date(_ctx(due_date=date(2025, 12, 1)))
    assert issues[0].step == "PRE"
    assert issues[0].rule_code == "DUE_DATE_BEFORE_ISSUE_DATE"


def test_pre_issue_date_in_future():
    ctx = _ctx(issue_date=date.today() + timedelta(days=30))
    issues = rules._check_issue_date_not_in_future(ctx)
    assert issues[0].step == "PRE"
    assert issues[0].rule_code == "ISSUE_DATE_IN_FUTURE"


# --- V9 arithmetic/total (pure, no DB) -----------------------------------------------


def test_v9_flags_non_positive_total():
    issues = rules._check_v9_arithmetic_total(_ctx(total_amount=Decimal("0")))
    codes = {i.rule_code for i in issues}
    assert "NON_POSITIVE_TOTAL" in codes
    assert all(i.step == "V9" for i in issues)


def test_v9_flags_line_item_math_mismatch():
    mismatched = LineItem(
        description="Widget",
        quantity=Decimal("2"),
        unit_price=Decimal("10.00"),
        extended_price=Decimal("25.00"),
    )
    issues = rules._check_v9_arithmetic_total(_ctx(line_items=[mismatched]))
    assert any(i.rule_code == "LINE_ITEM_MATH_MISMATCH" for i in issues)


def test_v9_flags_subtotal_mismatch():
    issues = rules._check_v9_arithmetic_total(_ctx(subtotal=Decimal("999.00")))
    assert any(i.rule_code == "SUBTOTAL_MISMATCH" for i in issues)


def test_v9_flags_total_mismatch():
    issues = rules._check_v9_arithmetic_total(_ctx(total_amount=Decimal("999.00")))
    assert any(i.rule_code == "TOTAL_MISMATCH" for i in issues)


def test_v9_clean_invoice_has_no_issues():
    assert rules._check_v9_arithmetic_total(_ctx()) == []


# --- V5 duplicate issue builder (pure) ------------------------------------------------


def test_duplicate_invoice_issue():
    issue = rules.duplicate_invoice_issue(vendor_name="Acme", invoice_number="INV-1")
    assert issue.step == "V5"
    assert issue.rule_code == "DUPLICATE_INVOICE"
    assert issue.severity == Severity.ERROR
