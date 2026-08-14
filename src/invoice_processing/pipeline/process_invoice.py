import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.decision.result import DecisionStatus
from invoice_processing.domain.enums import InvoiceStatus
from invoice_processing.domain.invoice import Invoice
from invoice_processing.extraction.router import extract
from invoice_processing.parsing.mapper import map_to_invoice
from invoice_processing.persistence.repository import InvoiceRepository, StatusHistoryEntry
from invoice_processing.validation.result import ValidationResult
from invoice_processing.validation.rules import run_validation_pipeline

_SEVERE_FAILURE_REJECTION_REASON = (
    "Deterministic validation found a severe arithmetic/total failure -- the invoice's "
    "own numbers don't reconcile, so agent investigation is skipped and it is rejected "
    "outright."
)


@dataclass
class PipelineResult:
    invoice_id: uuid.UUID
    invoice: Invoice
    validation_result: ValidationResult
    decision_status: DecisionStatus
    status_history: list[StatusHistoryEntry]


def process_invoice(
    pdf_path: Path, session: Session, *, source_filename: str | None = None
) -> PipelineResult:
    document = extract(pdf_path)
    invoice = map_to_invoice(document)

    repository = InvoiceRepository(session)
    issues = run_validation_pipeline(invoice, session)

    validation_result = ValidationResult(issues=issues)
    invoice.status = InvoiceStatus.VALID if validation_result.is_valid else InvoiceStatus.INVALID

    invoice_id = repository.save(
        invoice,
        source_filename=source_filename or pdf_path.name,
        extraction_method=document.method,
        raw_text=document.full_text,
        page_count=document.page_count,
        validation_result=validation_result,
    )

    # The pipeline runs synchronously end to end, but every stage still gets its own
    # status_history entry so the full lifecycle -- not just the resting state -- is
    # traceable after the fact.
    repository.update_decision_status(invoice_id, DecisionStatus.RECEIVED)
    repository.update_decision_status(invoice_id, DecisionStatus.VALIDATED)
    if validation_result.has_severe_failure:
        repository.update_decision_status(
            invoice_id, DecisionStatus.REJECTED, reason=_SEVERE_FAILURE_REJECTION_REASON
        )
    else:
        repository.update_decision_status(invoice_id, DecisionStatus.PENDING_APPROVAL)
    session.commit()

    stored = repository.get(invoice_id)
    assert stored is not None and stored.decision_status is not None

    return PipelineResult(
        invoice_id=invoice_id,
        invoice=invoice,
        validation_result=validation_result,
        decision_status=DecisionStatus(stored.decision_status),
        status_history=stored.status_history,
    )
