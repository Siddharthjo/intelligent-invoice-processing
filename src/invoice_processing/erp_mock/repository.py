from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from invoice_processing.erp_mock.models import PurchaseOrderRecord, SupplierRecord

DEFAULT_FUZZY_MATCH_THRESHOLD = 0.85


class SupplierRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_name(self, name: str) -> SupplierRecord | None:
        stmt = select(SupplierRecord).where(func.lower(SupplierRecord.name) == name.lower())
        return self._session.execute(stmt).scalar_one_or_none()

    def find_best_fuzzy_match(
        self, name: str, threshold: float = DEFAULT_FUZZY_MATCH_THRESHOLD
    ) -> SupplierRecord | None:
        """Fallback for V1 vendor identification when no exact name match is found.

        Small supplier-master scale (dozens, not millions of rows) makes a full
        in-memory scan with stdlib difflib perfectly adequate -- no new dependency
        or search infrastructure needed for this.
        """
        normalized = name.strip().lower()
        suppliers = self._session.execute(select(SupplierRecord)).scalars().all()

        best_match: SupplierRecord | None = None
        best_score = 0.0
        for supplier in suppliers:
            score = SequenceMatcher(None, normalized, supplier.name.strip().lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = supplier

        return best_match if best_score >= threshold else None


class PurchaseOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_number(self, po_number: str) -> PurchaseOrderRecord | None:
        stmt = select(PurchaseOrderRecord).where(
            func.lower(PurchaseOrderRecord.po_number) == po_number.lower()
        )
        return self._session.execute(stmt).scalar_one_or_none()
