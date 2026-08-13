import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from invoice_processing.persistence.db import Base

MONEY = Numeric(14, 2)


class InvoiceRecord(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    invoice_number: Mapped[str]
    vendor_name: Mapped[str]
    vendor_tax_id: Mapped[str | None]
    bill_to_name: Mapped[str | None]

    issue_date: Mapped[date]
    due_date: Mapped[date | None]

    currency: Mapped[str] = mapped_column(Text)

    subtotal: Mapped[Decimal | None] = mapped_column(MONEY)
    tax_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    discount_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    total_amount: Mapped[Decimal] = mapped_column(MONEY)

    status: Mapped[str]
    source_filename: Mapped[str | None]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    line_items: Mapped[list["LineItemRecord"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="LineItemRecord.line_number"
    )
    validation_issues: Mapped[list["ValidationIssueRecord"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    raw_extraction: Mapped["RawExtractionRecord | None"] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    agent_investigations: Mapped[list["AgentInvestigationRecord"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="AgentInvestigationRecord.created_at"
    )


class LineItemRecord(Base):
    __tablename__ = "invoice_line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    line_number: Mapped[int]

    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    extended_price: Mapped[Decimal] = mapped_column(MONEY)

    invoice: Mapped["InvoiceRecord"] = relationship(back_populates="line_items")


class ValidationIssueRecord(Base):
    __tablename__ = "invoice_validation_issues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))

    rule_code: Mapped[str]
    severity: Mapped[str]
    message: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    invoice: Mapped["InvoiceRecord"] = relationship(back_populates="validation_issues")


class RawExtractionRecord(Base):
    __tablename__ = "raw_extractions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), unique=True
    )

    source_filename: Mapped[str]
    extraction_method: Mapped[str]
    raw_text: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    invoice: Mapped["InvoiceRecord"] = relationship(back_populates="raw_extraction")


class AgentInvestigationRecord(Base):
    __tablename__ = "agent_investigations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))

    model: Mapped[str]
    recommendation: Mapped[str]
    reasoning_summary: Mapped[str] = mapped_column(Text)
    concerns: Mapped[list[str]] = mapped_column(JSONB)
    trace: Mapped[list[dict]] = mapped_column(JSONB)
    tool_call_count: Mapped[int]
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    invoice: Mapped["InvoiceRecord"] = relationship(back_populates="agent_investigations")
