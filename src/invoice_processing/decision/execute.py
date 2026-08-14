import uuid

from sqlalchemy.orm import Session

from invoice_processing.agent.tools import ToolContext, ToolPermission, dispatch_tool
from invoice_processing.decision.result import ActionType, DecisionStatus, ExecutionResult
from invoice_processing.persistence.orm_models import InvoiceActionRecord
from invoice_processing.persistence.repository import InvoiceRepository

_WRITE_PERMISSIONS: frozenset[ToolPermission] = frozenset({ToolPermission.WRITE})

_ACTION_TOOL_NAME = {
    ActionType.POST: "post_invoice",
    ActionType.RETURN: "return_to_vendor",
}

_RESULTING_STATUS = {
    ActionType.POST: DecisionStatus.AUTO_POSTED,
    ActionType.RETURN: DecisionStatus.RETURNED_TO_VENDOR,
}


class DecisionNotFoundError(Exception):
    """Raised when decision_id doesn't exist, or doesn't belong to the given invoice."""


class DecisionNotPendingReviewError(Exception):
    """Raised when the invoice's current decision_status isn't pending_review."""


def execute_decision(
    invoice_id: uuid.UUID,
    decision_id: uuid.UUID,
    action: ActionType,
    reason: str | None,
    session: Session,
) -> ExecutionResult:
    repository = InvoiceRepository(session)

    decision = repository.get_decision(decision_id)
    if decision is None or decision.invoice_id != invoice_id:
        raise DecisionNotFoundError(f"No decision '{decision_id}' found for invoice '{invoice_id}'.")

    stored = repository.get(invoice_id)
    if stored is None or stored.decision_status != DecisionStatus.PENDING_REVIEW.value:
        current = stored.decision_status if stored else None
        raise DecisionNotPendingReviewError(
            f"Invoice '{invoice_id}' is not pending review (current decision_status: {current!r})."
        )

    context = ToolContext(session=session, invoice_id=invoice_id, raw_text="")
    tool_name = _ACTION_TOOL_NAME[action]
    arguments: dict = {"invoice_id": str(invoice_id)}
    if action == ActionType.RETURN:
        arguments["reason"] = reason

    dispatch = dispatch_tool(tool_name, arguments, context, _WRITE_PERMISSIONS)
    assert dispatch.permitted, f"'{tool_name}' must always be permitted under WRITE dispatch"

    resulting_status = _RESULTING_STATUS[action]

    record = InvoiceActionRecord(
        invoice_id=invoice_id,
        decision_id=decision_id,
        action=action,
        reason=reason,
        resulting_decision_status=resulting_status,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    return ExecutionResult(
        id=record.id,
        invoice_id=invoice_id,
        decision_id=decision_id,
        action=action,
        reason=reason,
        resulting_decision_status=resulting_status,
        executed_at=record.created_at,
    )
