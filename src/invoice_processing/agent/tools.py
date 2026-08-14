import uuid
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from sqlalchemy.orm import Session

from invoice_processing.config import get_settings
from invoice_processing.erp_mock.repository import PurchaseOrderRepository, SupplierRepository
from invoice_processing.persistence.repository import InvoiceRepository

SUBMIT_RECOMMENDATION_TOOL_NAME = "submit_recommendation"


class ToolPermission(StrEnum):
    """Explicit permission tiers a tool is registered under.

    The runner only ever advertises/executes tools whose permission is in the caller's
    allowed set -- this is the enforcement point for "the agent can only read data" that
    write tools (post_invoice, approve_invoice, ...) will need to be deliberately granted
    into later, rather than becoming callable just by being defined.
    """

    READ = "read"
    WRITE = "write"


@dataclass
class ToolContext:
    session: Session
    invoice_id: uuid.UUID
    raw_text: str


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    schema: dict
    handler: Callable[[dict, "ToolContext"], dict]
    permission: ToolPermission


@dataclass
class ToolDispatchResult:
    result: dict
    permitted: bool


GET_SUPPLIER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_supplier",
        "description": (
            "Look up a supplier by name (case-insensitive) in the supplier master data. "
            "Use before recommending approval to confirm the vendor is known and active."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Vendor name as it appears on the invoice."}
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}

GET_PURCHASE_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_purchase_order",
        "description": (
            "Look up a purchase order by PO number in the mock ERP data, for three-way matching. "
            "Only call this with a PO number that appears verbatim in the invoice's raw extracted "
            "text -- never a guess, inference, or a PO number seen on a different invoice. If the "
            "raw text has no explicit PO reference, do not call this tool at all."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "po_number": {
                    "type": "string",
                    "description": (
                        "A PO number copied verbatim from the invoice's raw extracted text, e.g. "
                        "'PO-1001'. Never a guessed or inferred value."
                    ),
                }
            },
            "required": ["po_number"],
            "additionalProperties": False,
        },
    },
}

CHECK_DUPLICATE_TOOL = {
    "type": "function",
    "function": {
        "name": "check_duplicate",
        "description": (
            "Check whether another invoice already exists for this vendor and invoice number, "
            "excluding the invoice currently under investigation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Vendor name to check."},
                "invoice_number": {"type": "string", "description": "Invoice number to check."},
            },
            "required": ["vendor", "invoice_number"],
            "additionalProperties": False,
        },
    },
}

CALCULATE_VARIANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate_variance",
        "description": (
            "Compute absolute and percentage variance between the invoice total and a reference "
            "amount (typically a PO total), and whether it's within standard matching tolerance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_amount": {"type": "number", "description": "The invoice's total_amount."},
                "po_amount": {"type": "number", "description": "The purchase order's total_amount."},
            },
            "required": ["invoice_amount", "po_amount"],
            "additionalProperties": False,
        },
    },
}

SUBMIT_RECOMMENDATION_TOOL = {
    "type": "function",
    "function": {
        "name": SUBMIT_RECOMMENDATION_TOOL_NAME,
        "description": (
            "Submit your final disposition. Call exactly once, after investigating with the other tools."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "recommendation": {
                    "type": "string",
                    "enum": ["auto_approve", "human_review", "return_to_vendor"],
                },
                "reasoning": {
                    "type": "string",
                    "description": "Concise explanation citing specific tool evidence.",
                },
                "concerns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Short tags for specific issues found, e.g. 'PO_AMOUNT_MISMATCH', "
                        "'UNKNOWN_SUPPLIER', 'DUPLICATE_SUSPECTED', 'NO_PO_REFERENCE_FOUND'. "
                        "Empty if none."
                    ),
                },
            },
            "required": ["recommendation", "reasoning", "concerns"],
            "additionalProperties": False,
        },
    },
}

def _handle_get_supplier(arguments: dict, context: ToolContext) -> dict:
    supplier = SupplierRepository(context.session).get_by_name(arguments["name"])
    if supplier is None:
        return {"found": False}
    return {
        "found": True,
        "supplier": {
            "name": supplier.name,
            "tax_id": supplier.tax_id,
            "status": supplier.status,
            "notes": supplier.notes,
        },
    }


def _handle_get_purchase_order(arguments: dict, context: ToolContext) -> dict:
    po_number = arguments["po_number"]
    if po_number.lower() not in context.raw_text.lower():
        return {
            "found": False,
            "rejected_reason": (
                "po_number does not appear verbatim in this invoice's raw extracted text; "
                "lookup was not performed."
            ),
        }

    po = PurchaseOrderRepository(context.session).get_by_number(po_number)
    if po is None:
        return {"found": False}
    return {
        "found": True,
        "purchase_order": {
            "po_number": po.po_number,
            "vendor_name": po.vendor_name,
            "total_amount": str(po.total_amount),
            "currency": po.currency,
            "status": po.status,
        },
    }


def _handle_check_duplicate(arguments: dict, context: ToolContext) -> dict:
    matching_id = InvoiceRepository(context.session).find_duplicate(
        vendor_name=arguments["vendor"],
        invoice_number=arguments["invoice_number"],
        exclude_invoice_id=context.invoice_id,
    )
    return {
        "is_duplicate": matching_id is not None,
        "matching_invoice_id": str(matching_id) if matching_id is not None else None,
    }


def _handle_calculate_variance(arguments: dict, context: ToolContext) -> dict:
    tolerance_pct = get_settings().agent_po_variance_tolerance_pct
    invoice_amount = Decimal(str(arguments["invoice_amount"]))
    po_amount = Decimal(str(arguments["po_amount"]))

    absolute_variance = invoice_amount - po_amount
    percentage_variance = abs(absolute_variance) / po_amount if po_amount != 0 else None
    within_tolerance = percentage_variance is not None and percentage_variance <= tolerance_pct

    return {
        "absolute_variance": str(absolute_variance),
        "percentage_variance": str(percentage_variance) if percentage_variance is not None else None,
        "within_tolerance": within_tolerance,
        "tolerance_pct": str(tolerance_pct),
    }


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "get_supplier": ToolDefinition(
        name="get_supplier",
        schema=GET_SUPPLIER_TOOL,
        handler=_handle_get_supplier,
        permission=ToolPermission.READ,
    ),
    "get_purchase_order": ToolDefinition(
        name="get_purchase_order",
        schema=GET_PURCHASE_ORDER_TOOL,
        handler=_handle_get_purchase_order,
        permission=ToolPermission.READ,
    ),
    "check_duplicate": ToolDefinition(
        name="check_duplicate",
        schema=CHECK_DUPLICATE_TOOL,
        handler=_handle_check_duplicate,
        permission=ToolPermission.READ,
    ),
    "calculate_variance": ToolDefinition(
        name="calculate_variance",
        schema=CALCULATE_VARIANCE_TOOL,
        handler=_handle_calculate_variance,
        permission=ToolPermission.READ,
    ),
}

# Backward-compatible convenience view over the registry -- name -> handler only.
TOOL_HANDLERS: dict[str, Callable[[dict, ToolContext], dict]] = {
    name: definition.handler for name, definition in TOOL_REGISTRY.items()
}


def get_allowed_tool_schemas(allowed_permissions: frozenset[ToolPermission]) -> list[dict]:
    """Schemas to advertise to the model: registered tools within the allowed permission
    set, plus the always-available terminal submit_recommendation control tool."""
    schemas = [
        definition.schema
        for definition in TOOL_REGISTRY.values()
        if definition.permission in allowed_permissions
    ]
    schemas.append(SUBMIT_RECOMMENDATION_TOOL)
    return schemas


def dispatch_tool(
    name: str,
    arguments: dict,
    context: ToolContext,
    allowed_permissions: frozenset[ToolPermission],
) -> ToolDispatchResult:
    """Execute a tool call only if it's registered AND within the caller's allowed
    permissions -- the enforcement point, not just "we didn't define other tools."""
    definition = TOOL_REGISTRY.get(name)
    if definition is None or definition.permission not in allowed_permissions:
        return ToolDispatchResult(
            result={
                "error": "tool_not_permitted",
                "tool": name,
                "message": f"Tool '{name}' is not in the allowed permission set for this run.",
            },
            permitted=False,
        )
    return ToolDispatchResult(result=definition.handler(arguments, context), permitted=True)
