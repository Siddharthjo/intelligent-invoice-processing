from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from invoice_processing.domain.enums import InvoiceStatus


class Party(BaseModel):
    name: str
    tax_id: str | None = None
    country: str | None = None
    address: str | None = None
    email: str | None = None


class LineItem(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    extended_price: Decimal


class Invoice(BaseModel):
    invoice_number: str
    vendor: Party
    bill_to: Party | None = None
    po_number: str | None = None
    company_code: str | None = None

    issue_date: date
    due_date: date | None = None

    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    line_items: list[LineItem] = Field(default_factory=list)

    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    total_amount: Decimal

    status: InvoiceStatus = InvoiceStatus.PENDING_VALIDATION
