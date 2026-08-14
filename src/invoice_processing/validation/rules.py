from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from invoice_processing.domain.invoice import Invoice
from invoice_processing.erp_mock.enums import SupplierStatus
from invoice_processing.erp_mock.repository import PurchaseOrderRepository, SupplierRepository
from invoice_processing.persistence.repository import InvoiceRepository
from invoice_processing.validation.context import ValidationContext, ValidationStep
from invoice_processing.validation.currencies import ISO_4217_CODES
from invoice_processing.validation.result import Severity, ValidationIssue

MONEY_TOLERANCE = Decimal("0.01")
TAX_RATE_TOLERANCE = Decimal("0.005")

# --- Structural pre-checks (unnumbered) -------------------------------------------
# Well-formedness checks, not business-validation steps -- they don't fit the V1-V9
# business-validation sequence, so they run first under a distinct "PRE" step tag
# rather than being forced into a V-number they don't semantically belong to.


def _check_line_items_present(ctx: ValidationContext) -> list[ValidationIssue]:
    if not ctx.invoice.line_items:
        return [
            ValidationIssue(
                step="PRE",
                rule_code="NO_LINE_ITEMS_EXTRACTED",
                severity=Severity.WARNING,
                message="No line items were extracted from this invoice.",
            )
        ]
    return []


def _check_due_date_after_issue_date(ctx: ValidationContext) -> list[ValidationIssue]:
    invoice = ctx.invoice
    if invoice.due_date is not None and invoice.due_date < invoice.issue_date:
        return [
            ValidationIssue(
                step="PRE",
                rule_code="DUE_DATE_BEFORE_ISSUE_DATE",
                severity=Severity.ERROR,
                message=f"due_date {invoice.due_date} is before issue_date {invoice.issue_date}.",
            )
        ]
    return []


def _check_issue_date_not_in_future(ctx: ValidationContext) -> list[ValidationIssue]:
    if ctx.invoice.issue_date > date.today() + timedelta(days=1):
        return [
            ValidationIssue(
                step="PRE",
                rule_code="ISSUE_DATE_IN_FUTURE",
                severity=Severity.ERROR,
                message=f"issue_date {ctx.invoice.issue_date} is in the future.",
            )
        ]
    return []


PRE_CHECKS = [
    _check_line_items_present,
    _check_due_date_after_issue_date,
    _check_issue_date_not_in_future,
]


# --- V1: vendor identification (from PO, then exact, then fuzzy name match) -------


def _check_v1_vendor_identification(ctx: ValidationContext) -> list[ValidationIssue]:
    invoice = ctx.invoice

    if invoice.po_number:
        po = PurchaseOrderRepository(ctx.session).get_by_number(invoice.po_number)
        if po is not None:
            ctx.resolved_po = po
            ctx.resolved_supplier = po.supplier
            return []

    supplier = SupplierRepository(ctx.session).get_by_name(invoice.vendor.name)
    if supplier is not None:
        ctx.resolved_supplier = supplier
        return []

    supplier = SupplierRepository(ctx.session).find_best_fuzzy_match(invoice.vendor.name)
    if supplier is not None:
        ctx.resolved_supplier = supplier
        return [
            ValidationIssue(
                step="V1",
                rule_code="VENDOR_IDENTIFIED_BY_FUZZY_MATCH",
                severity=Severity.WARNING,
                message=(
                    f"Vendor '{invoice.vendor.name}' matched to master record "
                    f"'{supplier.name}' by approximate name match, not an exact match "
                    "or PO reference -- confirm this is the correct vendor."
                ),
            )
        ]

    return [
        ValidationIssue(
            step="V1",
            rule_code="VENDOR_NOT_IDENTIFIED",
            severity=Severity.ERROR,
            message=(
                f"Could not identify vendor '{invoice.vendor.name}' in supplier master "
                "data: no PO reference to resolve it, and no exact or approximate name match."
            ),
        )
    ]


# --- V2: vendor active / not blocked ------------------------------------------------


def _check_v2_vendor_active(ctx: ValidationContext) -> list[ValidationIssue]:
    supplier = ctx.resolved_supplier
    if supplier is None:
        return []  # V1 already reported the identification failure
    if supplier.status != SupplierStatus.ACTIVE:
        return [
            ValidationIssue(
                step="V2",
                rule_code="VENDOR_NOT_ACTIVE",
                severity=Severity.ERROR,
                message=f"Vendor '{supplier.name}' has status '{supplier.status}', not active.",
            )
        ]
    return []


# --- V3: field cross-validation (VAT, country vs master data) ----------------------
# Name is intentionally not re-checked here -- V1 already resolved it (exact or fuzzy).


def _check_v3_field_cross_validation(ctx: ValidationContext) -> list[ValidationIssue]:
    supplier = ctx.resolved_supplier
    if supplier is None:
        return []
    invoice = ctx.invoice
    issues: list[ValidationIssue] = []

    if invoice.vendor.tax_id and supplier.tax_id and invoice.vendor.tax_id != supplier.tax_id:
        issues.append(
            ValidationIssue(
                step="V3",
                rule_code="VENDOR_TAX_ID_MISMATCH",
                severity=Severity.ERROR,
                message=(
                    f"Invoice VAT/tax ID '{invoice.vendor.tax_id}' does not match master "
                    f"data '{supplier.tax_id}' for '{supplier.name}'."
                ),
            )
        )

    if (
        invoice.vendor.country
        and supplier.country
        and invoice.vendor.country.strip().lower() != supplier.country.strip().lower()
    ):
        issues.append(
            ValidationIssue(
                step="V3",
                rule_code="VENDOR_COUNTRY_MISMATCH",
                severity=Severity.WARNING,
                message=(
                    f"Invoice country '{invoice.vendor.country}' does not match master "
                    f"data '{supplier.country}' for '{supplier.name}'."
                ),
            )
        )

    return issues


# --- V4: company code determination -------------------------------------------------
# A determination, not just a check: on success it assigns invoice.company_code.


def _check_v4_company_code_determination(ctx: ValidationContext) -> list[ValidationIssue]:
    if ctx.resolved_po is not None and ctx.resolved_po.company_code:
        ctx.invoice.company_code = ctx.resolved_po.company_code
        return []
    return [
        ValidationIssue(
            step="V4",
            rule_code="COMPANY_CODE_NOT_DETERMINED",
            severity=Severity.WARNING,
            message=(
                "Could not determine a company code for this invoice (no purchase order "
                "resolved); manual assignment required."
            ),
        )
    ]


# --- V5: duplicate check -------------------------------------------------------------


def duplicate_invoice_issue(*, vendor_name: str, invoice_number: str) -> ValidationIssue:
    return ValidationIssue(
        step="V5",
        rule_code="DUPLICATE_INVOICE",
        severity=Severity.ERROR,
        message=f"An invoice with number '{invoice_number}' from vendor '{vendor_name}' already exists.",
    )


def _check_v5_duplicate(ctx: ValidationContext) -> list[ValidationIssue]:
    invoice = ctx.invoice
    if InvoiceRepository(ctx.session).duplicate_exists(
        vendor_name=invoice.vendor.name, invoice_number=invoice.invoice_number
    ):
        return [
            duplicate_invoice_issue(
                vendor_name=invoice.vendor.name, invoice_number=invoice.invoice_number
            )
        ]
    return []


# --- V6: bank validation (mock-only: does the resolved supplier have bank details) --


def _check_v6_bank_validation(ctx: ValidationContext) -> list[ValidationIssue]:
    supplier = ctx.resolved_supplier
    if supplier is None:
        return []
    if not supplier.bank_reference:
        return [
            ValidationIssue(
                step="V6",
                rule_code="SUPPLIER_BANK_DETAILS_MISSING",
                severity=Severity.WARNING,
                message=(
                    f"No bank details on file for vendor '{supplier.name}'; payment cannot "
                    "be routed until this is resolved."
                ),
            )
        ]
    return []


# --- V7: currency / rate validation ---------------------------------------------------


def _check_v7_currency_rate_validation(ctx: ValidationContext) -> list[ValidationIssue]:
    invoice = ctx.invoice
    issues: list[ValidationIssue] = []

    if invoice.currency not in ISO_4217_CODES:
        issues.append(
            ValidationIssue(
                step="V7",
                rule_code="INVALID_CURRENCY_CODE",
                severity=Severity.ERROR,
                message=f"'{invoice.currency}' is not a recognized ISO 4217 currency code.",
            )
        )

    if ctx.resolved_po is not None and invoice.currency != ctx.resolved_po.currency:
        issues.append(
            ValidationIssue(
                step="V7",
                rule_code="CURRENCY_PO_MISMATCH",
                severity=Severity.ERROR,
                message=(
                    f"Invoice currency '{invoice.currency}' does not match purchase order "
                    f"'{ctx.resolved_po.po_number}' currency '{ctx.resolved_po.currency}'."
                ),
            )
        )

    return issues


# --- V8: tax determination (mock) -----------------------------------------------------


def _check_v8_tax_determination(ctx: ValidationContext) -> list[ValidationIssue]:
    supplier = ctx.resolved_supplier
    invoice = ctx.invoice
    if supplier is None or supplier.default_tax_rate is None:
        return []
    if not invoice.subtotal or invoice.tax_amount is None:
        return []

    implied_rate = invoice.tax_amount / invoice.subtotal
    if abs(implied_rate - supplier.default_tax_rate) > TAX_RATE_TOLERANCE:
        return [
            ValidationIssue(
                step="V8",
                rule_code="TAX_RATE_MISMATCH",
                severity=Severity.WARNING,
                message=(
                    f"Invoice implies a tax rate of {implied_rate:.2%}, but the expected "
                    f"rate for '{supplier.name}' is {supplier.default_tax_rate:.2%}."
                ),
            )
        ]
    return []


# --- V9: arithmetic / total validation (existing checks, consolidated) ---------------


def _v9_total_amount_positive(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.total_amount <= 0:
        return [
            ValidationIssue(
                step="V9",
                rule_code="NON_POSITIVE_TOTAL",
                severity=Severity.ERROR,
                message=f"total_amount must be positive, got {invoice.total_amount}.",
            )
        ]
    return []


def _v9_line_item_math(invoice: Invoice) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, item in enumerate(invoice.line_items, start=1):
        expected = item.quantity * item.unit_price
        if abs(expected - item.extended_price) > MONEY_TOLERANCE:
            issues.append(
                ValidationIssue(
                    step="V9",
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


def _v9_subtotal_matches_line_items(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.subtotal is None or not invoice.line_items:
        return []
    computed = sum((item.extended_price for item in invoice.line_items), Decimal("0"))
    if abs(computed - invoice.subtotal) > MONEY_TOLERANCE:
        return [
            ValidationIssue(
                step="V9",
                rule_code="SUBTOTAL_MISMATCH",
                severity=Severity.ERROR,
                message=(
                    f"Sum of line item extended_price ({computed}) does not match "
                    f"subtotal ({invoice.subtotal})."
                ),
            )
        ]
    return []


def _v9_total_matches_components(invoice: Invoice) -> list[ValidationIssue]:
    if invoice.subtotal is None:
        return []
    tax = invoice.tax_amount or Decimal("0")
    discount = invoice.discount_amount or Decimal("0")
    expected_total = invoice.subtotal + tax - discount
    if abs(expected_total - invoice.total_amount) > MONEY_TOLERANCE:
        return [
            ValidationIssue(
                step="V9",
                rule_code="TOTAL_MISMATCH",
                severity=Severity.ERROR,
                message=(
                    f"subtotal ({invoice.subtotal}) + tax ({tax}) - discount ({discount}) "
                    f"= {expected_total}, but total_amount is {invoice.total_amount}."
                ),
            )
        ]
    return []


def _check_v9_arithmetic_total(ctx: ValidationContext) -> list[ValidationIssue]:
    invoice = ctx.invoice
    issues: list[ValidationIssue] = []
    issues.extend(_v9_total_amount_positive(invoice))
    issues.extend(_v9_line_item_math(invoice))
    issues.extend(_v9_subtotal_matches_line_items(invoice))
    issues.extend(_v9_total_matches_components(invoice))
    return issues


# --- Pipeline registry + runner -------------------------------------------------------

VALIDATION_STEPS: list[ValidationStep] = [
    ValidationStep("V1", "vendor_identification", _check_v1_vendor_identification),
    ValidationStep("V2", "vendor_active", _check_v2_vendor_active),
    ValidationStep("V3", "field_cross_validation", _check_v3_field_cross_validation),
    ValidationStep("V4", "company_code_determination", _check_v4_company_code_determination),
    ValidationStep("V5", "duplicate_check", _check_v5_duplicate),
    ValidationStep("V6", "bank_validation", _check_v6_bank_validation),
    ValidationStep("V7", "currency_rate_validation", _check_v7_currency_rate_validation),
    ValidationStep("V8", "tax_determination", _check_v8_tax_determination),
    ValidationStep("V9", "arithmetic_total_validation", _check_v9_arithmetic_total),
]


def run_validation_pipeline(invoice: Invoice, session: Session) -> list[ValidationIssue]:
    context = ValidationContext(invoice=invoice, session=session)
    issues: list[ValidationIssue] = []

    for check in PRE_CHECKS:
        issues.extend(check(context))

    for step in VALIDATION_STEPS:
        issues.extend(step.check(context))

    return issues
