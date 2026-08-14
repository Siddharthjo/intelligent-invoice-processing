import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.decision.result import DecisionStatus
from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.erp_mock.seed import seed_mock_erp_data
from invoice_processing.persistence.repository import InvoiceRepository
from invoice_processing.pipeline.process_invoice import process_invoice


def test_process_invoice_persists_a_valid_invoice(db_session: Session, tmp_path: Path):
    seed_mock_erp_data(db_session)
    invoice_number = f"INV-{uuid.uuid4().hex[:8]}"
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=invoice_number, vendor_name="Northwind Traders Ltd.")

    result = process_invoice(pdf_path, db_session)

    assert result.invoice.status.value == "valid"
    assert result.validation_result.is_valid
    assert result.decision_status == DecisionStatus.PENDING_APPROVAL
    assert [entry.status for entry in result.status_history] == [
        DecisionStatus.RECEIVED,
        DecisionStatus.VALIDATED,
        DecisionStatus.PENDING_APPROVAL,
    ]

    stored = InvoiceRepository(db_session).get(result.invoice_id)
    assert stored is not None
    assert stored.invoice.invoice_number == invoice_number
    assert len(stored.invoice.line_items) == 2
    assert stored.decision_status == DecisionStatus.PENDING_APPROVAL


def test_duplicate_invoice_is_persisted_but_flagged_invalid(db_session: Session, tmp_path: Path):
    invoice_number = f"INV-{uuid.uuid4().hex[:8]}"
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=invoice_number)

    process_invoice(pdf_path, db_session)
    second = process_invoice(pdf_path, db_session)

    assert second.invoice.status.value == "invalid"
    assert any(issue.rule_code == "DUPLICATE_INVOICE" for issue in second.validation_result.issues)
    # A duplicate is an ERROR-severity issue, but not a V9 arithmetic failure -- it's
    # ambiguous enough (could be a legitimate resubmission) to still warrant an agent
    # look rather than an automatic rejection.
    assert second.decision_status == DecisionStatus.PENDING_APPROVAL


def test_severe_arithmetic_failure_short_circuits_straight_to_rejected(
    db_session: Session, tmp_path: Path
):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}", total="999.00")

    result = process_invoice(pdf_path, db_session)

    assert any(issue.rule_code == "TOTAL_MISMATCH" for issue in result.validation_result.issues)
    assert result.decision_status == DecisionStatus.REJECTED
    assert [entry.status for entry in result.status_history] == [
        DecisionStatus.RECEIVED,
        DecisionStatus.VALIDATED,
        DecisionStatus.REJECTED,
    ]
    assert result.status_history[-1].reason is not None

    stored = InvoiceRepository(db_session).get(result.invoice_id)
    assert stored is not None
    assert stored.decision_status == DecisionStatus.REJECTED
