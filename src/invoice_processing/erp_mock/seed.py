from decimal import Decimal

from sqlalchemy.orm import Session

from invoice_processing.erp_mock.enums import PurchaseOrderStatus, PurchaseOrderType, SupplierStatus
from invoice_processing.erp_mock.models import PurchaseOrderRecord, SupplierRecord

_SUPPLIERS = [
    {
        "name": "Northwind Traders Ltd.",
        "tax_id": "US-11-2233445",
        "country": "US",
        "default_tax_rate": Decimal("0.0800"),
        "bank_reference": "REF-NW-4471",
        "status": SupplierStatus.ACTIVE,
        "notes": None,
    },
    {
        "name": "Southgate Supplies Inc.",
        "tax_id": "US-22-3344556",
        "country": "US",
        "default_tax_rate": Decimal("0.0725"),
        "bank_reference": "REF-SG-2290",
        "status": SupplierStatus.ACTIVE,
        "notes": None,
    },
    {
        "name": "Globex Corporation",
        "tax_id": "US-33-4455667",
        "country": "US",
        "default_tax_rate": Decimal("0.0800"),
        # Deliberately missing -- gives V6 bank validation a genuine, otherwise-clean
        # supplier to catch, distinct from the already-blocked Initech Consulting.
        "bank_reference": None,
        "status": SupplierStatus.ACTIVE,
        "notes": None,
    },
    {
        "name": "Initech Consulting",
        "tax_id": None,
        "country": "US",
        "default_tax_rate": None,
        "bank_reference": None,
        "status": SupplierStatus.BLOCKED,
        "notes": "Blocked pending compliance review as of 2026-06-01.",
    },
]

_PURCHASE_ORDERS = [
    {
        "po_number": "PO-1001",
        "supplier_name": "Northwind Traders Ltd.",
        "company_code": "CC-100",
        "po_type": PurchaseOrderType.SERVICES,
        "total_amount": Decimal("2158.92"),
        "currency": "USD",
        "status": PurchaseOrderStatus.OPEN,
    },
    {
        "po_number": "PO-2002",
        "supplier_name": "Southgate Supplies Inc.",
        "company_code": "CC-100",
        "po_type": PurchaseOrderType.GOODS,
        "total_amount": Decimal("1274.40"),
        "currency": "USD",
        "status": PurchaseOrderStatus.OPEN,
    },
    {
        "po_number": "PO-3003",
        "supplier_name": "Globex Corporation",
        "company_code": "CC-200",
        "po_type": PurchaseOrderType.INDIRECT,
        "total_amount": Decimal("500.00"),
        "currency": "USD",
        "status": PurchaseOrderStatus.CLOSED,
    },
    {
        "po_number": "PO-4004",
        "supplier_name": "Northwind Traders Ltd.",
        "company_code": "CC-100",
        "po_type": PurchaseOrderType.GOODS,
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
            country=data["country"],
            default_tax_rate=data["default_tax_rate"],
            bank_reference=data["bank_reference"],
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
                company_code=data["company_code"],
                po_type=data["po_type"],
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
