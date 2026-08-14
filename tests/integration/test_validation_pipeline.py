import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.domain.invoice import Invoice, LineItem, Party
from invoice_processing.erp_mock.seed import seed_mock_erp_data
from invoice_processing.pipeline.process_invoice import process_invoice
from invoice_processing.validation.context import ValidationContext
from invoice_processing.validation.rules import (
    _check_v1_vendor_identification,
    _check_v2_vendor_active,
    _check_v3_field_cross_validation,
    _check_v4_company_code_determination,
    _check_v6_bank_validation,
    _check_v7_currency_rate_validation,
    _check_v8_tax_determination,
    run_validation_pipeline,
)


def _invoice(**overrides) -> Invoice:
    base = dict(
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        vendor=Party(name="Northwind Traders Ltd."),
        issue_date=date(2026, 1, 1),
        currency="USD",
        total_amount=Decimal("100.00"),
    )
    base.update(overrides)
    return Invoice(**base)


def test_v1_exact_name_match(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(), session=db_session)
    issues = _check_v1_vendor_identification(ctx)
    assert issues == []
    assert ctx.resolved_supplier is not None
    assert ctx.resolved_supplier.name == "Northwind Traders Ltd."


def test_v1_fuzzy_name_match(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(vendor=Party(name="Northwind Traders Ltd")), session=db_session)
    issues = _check_v1_vendor_identification(ctx)
    assert issues[0].rule_code == "VENDOR_IDENTIFIED_BY_FUZZY_MATCH"
    assert ctx.resolved_supplier is not None
    assert ctx.resolved_supplier.name == "Northwind Traders Ltd."


def test_v1_vendor_not_identified(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(
        invoice=_invoice(vendor=Party(name="Totally Unrelated Vendor XYZ")), session=db_session
    )
    issues = _check_v1_vendor_identification(ctx)
    assert issues[0].rule_code == "VENDOR_NOT_IDENTIFIED"
    assert ctx.resolved_supplier is None


def test_v1_resolves_via_po_regardless_of_vendor_name(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(
        invoice=_invoice(vendor=Party(name="Whatever Was Extracted"), po_number="PO-1001"),
        session=db_session,
    )
    issues = _check_v1_vendor_identification(ctx)
    assert issues == []
    assert ctx.resolved_po is not None
    assert ctx.resolved_po.po_number == "PO-1001"
    assert ctx.resolved_supplier.name == "Northwind Traders Ltd."


def test_v2_flags_blocked_supplier(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(vendor=Party(name="Initech Consulting")), session=db_session)
    _check_v1_vendor_identification(ctx)
    issues = _check_v2_vendor_active(ctx)
    assert issues[0].rule_code == "VENDOR_NOT_ACTIVE"


def test_v3_flags_tax_id_and_country_mismatch(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(
        invoice=_invoice(vendor=Party(name="Northwind Traders Ltd.", tax_id="GB-99-9999999", country="UK")),
        session=db_session,
    )
    _check_v1_vendor_identification(ctx)
    issues = _check_v3_field_cross_validation(ctx)
    codes = {i.rule_code for i in issues}
    assert "VENDOR_TAX_ID_MISMATCH" in codes
    assert "VENDOR_COUNTRY_MISMATCH" in codes


def test_v4_determines_company_code_from_po(db_session: Session):
    seed_mock_erp_data(db_session)
    invoice = _invoice(po_number="PO-1001")
    ctx = ValidationContext(invoice=invoice, session=db_session)
    _check_v1_vendor_identification(ctx)
    issues = _check_v4_company_code_determination(ctx)
    assert issues == []
    assert invoice.company_code == "CC-100"


def test_v4_warns_when_no_po_to_determine_company_code(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(), session=db_session)
    _check_v1_vendor_identification(ctx)
    issues = _check_v4_company_code_determination(ctx)
    assert issues[0].rule_code == "COMPANY_CODE_NOT_DETERMINED"


def test_v5_full_pipeline_flags_duplicate(db_session: Session, tmp_path: Path):
    seed_mock_erp_data(db_session)
    invoice_number = f"INV-{uuid.uuid4().hex[:8]}"
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=invoice_number, vendor_name="Northwind Traders Ltd.")
    process_invoice(pdf_path, db_session)

    second = _invoice(invoice_number=invoice_number, vendor=Party(name="Northwind Traders Ltd."))
    issues = run_validation_pipeline(second, db_session)
    assert any(i.rule_code == "DUPLICATE_INVOICE" and i.step == "V5" for i in issues)


def test_v6_flags_missing_bank_details(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(vendor=Party(name="Globex Corporation")), session=db_session)
    _check_v1_vendor_identification(ctx)
    issues = _check_v6_bank_validation(ctx)
    assert issues[0].rule_code == "SUPPLIER_BANK_DETAILS_MISSING"


def test_v6_passes_when_bank_details_present(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(), session=db_session)  # Northwind has bank_reference
    _check_v1_vendor_identification(ctx)
    assert _check_v6_bank_validation(ctx) == []


def test_v7_flags_invalid_currency_code(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(currency="ZZZ"), session=db_session)
    issues = _check_v7_currency_rate_validation(ctx)
    assert any(i.rule_code == "INVALID_CURRENCY_CODE" for i in issues)


def test_v7_flags_currency_po_mismatch(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(invoice=_invoice(currency="EUR", po_number="PO-1001"), session=db_session)
    _check_v1_vendor_identification(ctx)
    issues = _check_v7_currency_rate_validation(ctx)
    assert any(i.rule_code == "CURRENCY_PO_MISMATCH" for i in issues)


def test_v8_flags_tax_rate_mismatch(db_session: Session):
    seed_mock_erp_data(db_session)
    # Northwind's default_tax_rate is 8%; a 1% implied rate should be flagged.
    ctx = ValidationContext(
        invoice=_invoice(subtotal=Decimal("100.00"), tax_amount=Decimal("1.00")), session=db_session
    )
    _check_v1_vendor_identification(ctx)
    issues = _check_v8_tax_determination(ctx)
    assert issues[0].rule_code == "TAX_RATE_MISMATCH"


def test_v8_passes_when_tax_rate_matches(db_session: Session):
    seed_mock_erp_data(db_session)
    ctx = ValidationContext(
        invoice=_invoice(subtotal=Decimal("100.00"), tax_amount=Decimal("8.00")), session=db_session
    )
    _check_v1_vendor_identification(ctx)
    assert _check_v8_tax_determination(ctx) == []


def test_fully_clean_invoice_produces_zero_issues(db_session: Session):
    seed_mock_erp_data(db_session)
    invoice = _invoice(
        po_number="PO-1001",
        currency="USD",
        line_items=[
            LineItem(
                description="Consulting Services",
                quantity=Decimal("1"),
                unit_price=Decimal("1999.00"),
                extended_price=Decimal("1999.00"),
            )
        ],
        subtotal=Decimal("1999.00"),
        tax_amount=Decimal("159.92"),  # 8% of 1999.00, matches Northwind's default_tax_rate
        total_amount=Decimal("2158.92"),
    )
    issues = run_validation_pipeline(invoice, db_session)
    assert issues == []
    assert invoice.company_code == "CC-100"
