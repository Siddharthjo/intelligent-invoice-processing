from sqlalchemy import func, select
from sqlalchemy.orm import Session

from invoice_processing.erp_mock.models import PurchaseOrderRecord, SupplierRecord


class SupplierRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_name(self, name: str) -> SupplierRecord | None:
        stmt = select(SupplierRecord).where(func.lower(SupplierRecord.name) == name.lower())
        return self._session.execute(stmt).scalar_one_or_none()


class PurchaseOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_number(self, po_number: str) -> PurchaseOrderRecord | None:
        stmt = select(PurchaseOrderRecord).where(
            func.lower(PurchaseOrderRecord.po_number) == po_number.lower()
        )
        return self._session.execute(stmt).scalar_one_or_none()
