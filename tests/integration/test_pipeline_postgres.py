import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.persistence.repository import InvoiceRepository
from invoice_processing.pipeline.process_invoice import process_invoice


def test_process_invoice_persists_a_valid_invoice(db_session: Session, tmp_path: Path):
    invoice_number = f"INV-{uuid.uuid4().hex[:8]}"
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=invoice_number)

    result = process_invoice(pdf_path, db_session)

    assert result.invoice.status.value == "valid"
    assert result.validation_result.is_valid

    stored = InvoiceRepository(db_session).get(result.invoice_id)
    assert stored is not None
    assert stored.invoice.invoice_number == invoice_number
    assert len(stored.invoice.line_items) == 2


def test_duplicate_invoice_is_persisted_but_flagged_invalid(db_session: Session, tmp_path: Path):
    invoice_number = f"INV-{uuid.uuid4().hex[:8]}"
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=invoice_number)

    process_invoice(pdf_path, db_session)
    second = process_invoice(pdf_path, db_session)

    assert second.invoice.status.value == "invalid"
    assert any(issue.rule_code == "DUPLICATE_INVOICE" for issue in second.validation_result.issues)
