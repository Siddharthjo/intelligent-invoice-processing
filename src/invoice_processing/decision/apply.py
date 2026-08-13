import uuid

from sqlalchemy.orm import Session

from invoice_processing.agent.result import Recommendation
from invoice_processing.decision.policy import POLICY_VERSION, decide
from invoice_processing.decision.result import DecisionResult
from invoice_processing.persistence.orm_models import InvoiceDecisionRecord
from invoice_processing.persistence.repository import InvoiceRepository


def apply_decision(
    invoice_id: uuid.UUID,
    agent_investigation_id: uuid.UUID,
    recommendation: Recommendation,
    session: Session,
) -> DecisionResult:
    decision_status = decide(recommendation)
    reasoning = (
        f"Policy {POLICY_VERSION}: agent recommended '{recommendation.value}', "
        f"which maps directly to '{decision_status.value}'."
    )

    record = InvoiceDecisionRecord(
        invoice_id=invoice_id,
        agent_investigation_id=agent_investigation_id,
        agent_recommendation=recommendation,
        decision=decision_status,
        decision_reasoning=reasoning,
        policy_version=POLICY_VERSION,
    )
    session.add(record)

    InvoiceRepository(session).update_decision_status(invoice_id, decision_status)

    session.commit()
    session.refresh(record)

    return DecisionResult(
        id=record.id,
        invoice_id=invoice_id,
        agent_investigation_id=agent_investigation_id,
        agent_recommendation=recommendation.value,
        decision_status=decision_status,
        decision_reasoning=reasoning,
        policy_version=POLICY_VERSION,
    )
