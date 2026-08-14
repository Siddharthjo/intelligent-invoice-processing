from enum import StrEnum


class SupplierStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class PurchaseOrderStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PurchaseOrderType(StrEnum):
    GOODS = "goods"
    SERVICES = "services"
    INDIRECT = "indirect"
