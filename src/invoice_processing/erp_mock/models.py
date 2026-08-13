import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from invoice_processing.persistence.db import Base

MONEY = Numeric(14, 2)


class SupplierRecord(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True)
    tax_id: Mapped[str | None]
    status: Mapped[str]
    notes: Mapped[str | None] = mapped_column(Text)

    purchase_orders: Mapped[list["PurchaseOrderRecord"]] = relationship(back_populates="supplier")


class PurchaseOrderRecord(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    po_number: Mapped[str] = mapped_column(unique=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"))
    vendor_name: Mapped[str]
    total_amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(Text)
    status: Mapped[str]

    supplier: Mapped["SupplierRecord"] = relationship(back_populates="purchase_orders")
