from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from invoice_processing.domain.enums import InvoiceStatus
from invoice_processing.domain.invoice import Invoice
from invoice_processing.persistence.repository import StoredInvoice
from invoice_processing.pipeline.process_invoice import PipelineResult
from invoice_processing.validation.result import Severity, ValidationIssue


class LineItemOut(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    extended_price: Decimal


class ValidationIssueOut(BaseModel):
    rule_code: str
    severity: Severity
    message: str


class InvoiceOut(BaseModel):
    id: UUID
    invoice_number: str
    vendor_name: str
    bill_to_name: str | None
    issue_date: date
    due_date: date | None
    currency: str
    line_items: list[LineItemOut]
    subtotal: Decimal | None
    tax_amount: Decimal | None
    discount_amount: Decimal | None
    total_amount: Decimal
    status: InvoiceStatus
    source_filename: str | None
    validation_issues: list[ValidationIssueOut]

    @classmethod
    def build(
        cls,
        *,
        id: UUID,
        invoice: Invoice,
        source_filename: str | None,
        validation_issues: list[ValidationIssue],
    ) -> "InvoiceOut":
        return cls(
            id=id,
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor.name,
            bill_to_name=invoice.bill_to.name if invoice.bill_to else None,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            currency=invoice.currency,
            line_items=[LineItemOut(**item.model_dump()) for item in invoice.line_items],
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            discount_amount=invoice.discount_amount,
            total_amount=invoice.total_amount,
            status=invoice.status,
            source_filename=source_filename,
            validation_issues=[ValidationIssueOut(**issue.model_dump()) for issue in validation_issues],
        )

    @classmethod
    def from_pipeline_result(cls, result: PipelineResult, *, source_filename: str) -> "InvoiceOut":
        return cls.build(
            id=result.invoice_id,
            invoice=result.invoice,
            source_filename=source_filename,
            validation_issues=result.validation_result.issues,
        )

    @classmethod
    def from_stored(cls, stored: StoredInvoice) -> "InvoiceOut":
        return cls.build(
            id=stored.id,
            invoice=stored.invoice,
            source_filename=stored.source_filename,
            validation_issues=stored.validation_issues,
        )


class InvoiceSummaryOut(BaseModel):
    id: UUID
    invoice_number: str
    vendor_name: str
    issue_date: date
    currency: str
    total_amount: Decimal
    status: InvoiceStatus

    @classmethod
    def from_stored(cls, stored: StoredInvoice) -> "InvoiceSummaryOut":
        return cls(
            id=stored.id,
            invoice_number=stored.invoice.invoice_number,
            vendor_name=stored.invoice.vendor.name,
            issue_date=stored.invoice.issue_date,
            currency=stored.invoice.currency,
            total_amount=stored.invoice.total_amount,
            status=stored.invoice.status,
        )
