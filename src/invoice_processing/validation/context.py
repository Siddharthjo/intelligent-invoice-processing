from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from invoice_processing.domain.invoice import Invoice
from invoice_processing.erp_mock.models import PurchaseOrderRecord, SupplierRecord
from invoice_processing.validation.result import ValidationIssue


@dataclass
class ValidationContext:
    """Threaded through the validation pipeline in order. V1 resolves the vendor/PO;
    later steps read what V1 found rather than re-resolving it themselves -- steps are
    no longer independent/order-agnostic the way the old flat rule list was."""

    invoice: Invoice
    session: Session
    resolved_supplier: SupplierRecord | None = None
    resolved_po: PurchaseOrderRecord | None = None


@dataclass(frozen=True)
class ValidationStep:
    step: str
    name: str
    check: Callable[[ValidationContext], list[ValidationIssue]]
