import uuid

from openai import OpenAI
from sqlalchemy.orm import Session

from invoice_processing.agent.result import AgentInvestigationResult
from invoice_processing.agent.runner import DEFAULT_ALLOWED_PERMISSIONS, run_investigation
from invoice_processing.agent.tools import ToolPermission
from invoice_processing.persistence.orm_models import AgentInvestigationRecord
from invoice_processing.persistence.repository import InvoiceRepository


class InvoiceNotFoundError(Exception):
    """Raised when investigate_invoice is called with an unknown invoice id."""


def investigate_invoice(
    invoice_id: uuid.UUID,
    session: Session,
    *,
    client: OpenAI | None = None,
    allowed_permissions: frozenset[ToolPermission] = DEFAULT_ALLOWED_PERMISSIONS,
) -> AgentInvestigationResult:
    repository = InvoiceRepository(session)
    stored = repository.get(invoice_id)
    if stored is None:
        raise InvoiceNotFoundError(f"No invoice found with id '{invoice_id}'.")

    raw_text = repository.get_raw_text(invoice_id) or ""

    result = run_investigation(
        stored, raw_text, session, client=client, allowed_permissions=allowed_permissions
    )

    investigation_id = uuid.uuid4()
    session.add(
        AgentInvestigationRecord(
            id=investigation_id,
            invoice_id=invoice_id,
            model=result.model,
            recommendation=result.recommendation,
            reasoning_summary=result.reasoning_summary,
            concerns=result.concerns,
            trace=result.trace,
            tool_call_count=result.tool_call_count,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            termination_reason=result.termination_reason,
            latency_ms=result.latency_ms,
        )
    )
    session.commit()

    result.id = investigation_id
    return result
