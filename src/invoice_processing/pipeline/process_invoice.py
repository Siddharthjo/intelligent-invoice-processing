import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.domain.enums import InvoiceStatus
from invoice_processing.domain.invoice import Invoice
from invoice_processing.extraction.router import extract
from invoice_processing.parsing.mapper import map_to_invoice
from invoice_processing.persistence.repository import InvoiceRepository
from invoice_processing.validation.result import ValidationResult
from invoice_processing.validation.rules import duplicate_invoice_issue, run_rules


@dataclass
class PipelineResult:
    invoice_id: uuid.UUID
    invoice: Invoice
    validation_result: ValidationResult


def process_invoice(
    pdf_path: Path, session: Session, *, source_filename: str | None = None
) -> PipelineResult:
    document = extract(pdf_path)
    invoice = map_to_invoice(document)

    issues = run_rules(invoice)

    repository = InvoiceRepository(session)
    if repository.duplicate_exists(vendor_name=invoice.vendor.name, invoice_number=invoice.invoice_number):
        issues.append(
            duplicate_invoice_issue(vendor_name=invoice.vendor.name, invoice_number=invoice.invoice_number)
        )

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

    return PipelineResult(invoice_id=invoice_id, invoice=invoice, validation_result=validation_result)
