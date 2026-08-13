from decimal import Decimal

from sqlalchemy.orm import Session

from invoice_processing.erp_mock.enums import PurchaseOrderStatus, SupplierStatus
from invoice_processing.erp_mock.models import PurchaseOrderRecord, SupplierRecord

_SUPPLIERS = [
    {
        "name": "Northwind Traders Ltd.",
        "tax_id": "US-11-2233445",
        "status": SupplierStatus.ACTIVE,
        "notes": None,
    },
    {
        "name": "Southgate Supplies Inc.",
        "tax_id": "US-22-3344556",
        "status": SupplierStatus.ACTIVE,
        "notes": None,
    },
    {
        "name": "Globex Corporation",
        "tax_id": "US-33-4455667",
        "status": SupplierStatus.ACTIVE,
        "notes": None,
    },
    {
        "name": "Initech Consulting",
        "tax_id": None,
        "status": SupplierStatus.BLOCKED,
        "notes": "Blocked pending compliance review as of 2026-06-01.",
    },
]

_PURCHASE_ORDERS = [
    {
        "po_number": "PO-1001",
        "supplier_name": "Northwind Traders Ltd.",
        "total_amount": Decimal("2158.92"),
        "currency": "USD",
        "status": PurchaseOrderStatus.OPEN,
    },
    {
        "po_number": "PO-2002",
        "supplier_name": "Southgate Supplies Inc.",
        "total_amount": Decimal("1274.40"),
        "currency": "USD",
        "status": PurchaseOrderStatus.OPEN,
    },
    {
        "po_number": "PO-3003",
        "supplier_name": "Globex Corporation",
        "total_amount": Decimal("500.00"),
        "currency": "USD",
        "status": PurchaseOrderStatus.CLOSED,
    },
    {
        "po_number": "PO-4004",
        "supplier_name": "Northwind Traders Ltd.",
        "total_amount": Decimal("750.00"),
        "currency": "USD",
        "status": PurchaseOrderStatus.CANCELLED,
    },
]


def seed_mock_erp_data(session: Session) -> None:
    if session.query(SupplierRecord).count() > 0:
        return

    suppliers_by_name: dict[str, SupplierRecord] = {}
    for data in _SUPPLIERS:
        supplier = SupplierRecord(
            name=data["name"],
            tax_id=data["tax_id"],
            status=data["status"],
            notes=data["notes"],
        )
        session.add(supplier)
        suppliers_by_name[data["name"]] = supplier

    session.flush()

    for data in _PURCHASE_ORDERS:
        supplier = suppliers_by_name[data["supplier_name"]]
        session.add(
            PurchaseOrderRecord(
                po_number=data["po_number"],
                supplier_id=supplier.id,
                vendor_name=supplier.name,
                total_amount=data["total_amount"],
                currency=data["currency"],
                status=data["status"],
            )
        )

    session.commit()


def main() -> None:
    from invoice_processing.persistence.db import SessionLocal

    session = SessionLocal()
    try:
        seed_mock_erp_data(session)
        print("Mock ERP data seeded (or already present).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
