import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from invoice_processing.domain.enums import ExtractionMethod, InvoiceStatus
from invoice_processing.domain.invoice import Invoice, LineItem, Party
from invoice_processing.persistence.orm_models import (
    AgentInvestigationRecord,
    InvoiceDecisionRecord,
    InvoiceRecord,
    InvoiceStatusHistoryRecord,
    LineItemRecord,
    RawExtractionRecord,
    ValidationIssueRecord,
)
from invoice_processing.validation.result import Severity, ValidationIssue, ValidationResult


@dataclass
class StatusHistoryEntry:
    status: str
    reason: str | None
    created_at: datetime


@dataclass
class StoredInvoice:
    id: uuid.UUID
    invoice: Invoice
    source_filename: str | None
    validation_issues: list[ValidationIssue]
    decision_status: str | None
    status_history: list[StatusHistoryEntry]


class InvoiceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def duplicate_exists(
        self, *, vendor_name: str, invoice_number: str, exclude_invoice_id: uuid.UUID | None = None
    ) -> bool:
        return self.find_duplicate(
            vendor_name=vendor_name, invoice_number=invoice_number, exclude_invoice_id=exclude_invoice_id
        ) is not None

    def find_duplicate(
        self, *, vendor_name: str, invoice_number: str, exclude_invoice_id: uuid.UUID | None = None
    ) -> uuid.UUID | None:
        stmt = select(InvoiceRecord.id).where(
            InvoiceRecord.vendor_name == vendor_name,
            InvoiceRecord.invoice_number == invoice_number,
        )
        if exclude_invoice_id is not None:
            stmt = stmt.where(InvoiceRecord.id != exclude_invoice_id)
        return self._session.execute(stmt).scalars().first()

    def save(
        self,
        invoice: Invoice,
        *,
        source_filename: str,
        extraction_method: ExtractionMethod,
        raw_text: str,
        page_count: int,
        validation_result: ValidationResult,
    ) -> uuid.UUID:
        record = InvoiceRecord(
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor.name,
            vendor_tax_id=invoice.vendor.tax_id,
            vendor_country=invoice.vendor.country,
            bill_to_name=invoice.bill_to.name if invoice.bill_to else None,
            po_number=invoice.po_number,
            company_code=invoice.company_code,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            currency=invoice.currency,
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            discount_amount=invoice.discount_amount,
            total_amount=invoice.total_amount,
            status=invoice.status,
            source_filename=source_filename,
            line_items=[
                LineItemRecord(
                    line_number=index,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    extended_price=item.extended_price,
                )
                for index, item in enumerate(invoice.line_items, start=1)
            ],
            validation_issues=[
                ValidationIssueRecord(
                    step=issue.step,
                    rule_code=issue.rule_code,
                    severity=issue.severity,
                    message=issue.message,
                )
                for issue in validation_result.issues
            ],
            raw_extraction=RawExtractionRecord(
                source_filename=source_filename,
                extraction_method=extraction_method,
                raw_text=raw_text,
                page_count=page_count,
            ),
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record.id

    def get(self, invoice_id: uuid.UUID) -> StoredInvoice | None:
        record = self._session.get(InvoiceRecord, invoice_id)
        if record is None:
            return None
        return _to_stored(record)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[StoredInvoice]:
        stmt = select(InvoiceRecord).order_by(InvoiceRecord.created_at.desc()).limit(limit).offset(offset)
        records = self._session.execute(stmt).scalars().all()
        return [_to_stored(record) for record in records]

    def get_raw_text(self, invoice_id: uuid.UUID) -> str | None:
        stmt = select(RawExtractionRecord.raw_text).where(RawExtractionRecord.invoice_id == invoice_id)
        return self._session.execute(stmt).scalars().first()

    def update_decision_status(
        self, invoice_id: uuid.UUID, decision_status: str, *, reason: str | None = None
    ) -> None:
        record = self._session.get(InvoiceRecord, invoice_id)
        if record is not None:
            record.decision_status = decision_status
        self._session.add(
            InvoiceStatusHistoryRecord(invoice_id=invoice_id, status=decision_status, reason=reason)
        )

    def get_latest_investigation_and_decision(
        self, invoice_id: uuid.UUID
    ) -> tuple[AgentInvestigationRecord, InvoiceDecisionRecord] | None:
        record = self._session.get(InvoiceRecord, invoice_id)
        if record is None or not record.agent_investigations or not record.decisions:
            return None
        return record.agent_investigations[-1], record.decisions[-1]

    def get_decision(self, decision_id: uuid.UUID) -> InvoiceDecisionRecord | None:
        return self._session.get(InvoiceDecisionRecord, decision_id)


def _to_domain(record: InvoiceRecord) -> Invoice:
    return Invoice(
        invoice_number=record.invoice_number,
        vendor=Party(name=record.vendor_name, tax_id=record.vendor_tax_id, country=record.vendor_country),
        bill_to=Party(name=record.bill_to_name) if record.bill_to_name else None,
        po_number=record.po_number,
        company_code=record.company_code,
        issue_date=record.issue_date,
        due_date=record.due_date,
        currency=record.currency,
        line_items=[
            LineItem(
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                extended_price=item.extended_price,
            )
            for item in record.line_items
        ],
        subtotal=record.subtotal,
        tax_amount=record.tax_amount,
        discount_amount=record.discount_amount,
        total_amount=record.total_amount,
        status=InvoiceStatus(record.status),
    )


def _to_stored(record: InvoiceRecord) -> StoredInvoice:
    return StoredInvoice(
        id=record.id,
        invoice=_to_domain(record),
        source_filename=record.source_filename,
        validation_issues=[
            ValidationIssue(
                step=issue.step,
                rule_code=issue.rule_code,
                severity=Severity(issue.severity),
                message=issue.message,
            )
            for issue in record.validation_issues
        ],
        decision_status=record.decision_status,
        status_history=[
            StatusHistoryEntry(status=entry.status, reason=entry.reason, created_at=entry.created_at)
            for entry in record.status_history
        ],
    )
