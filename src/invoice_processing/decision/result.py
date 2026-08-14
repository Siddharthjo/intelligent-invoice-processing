import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class DecisionStatus(StrEnum):
    """An invoice's lifecycle status.

    Ordered roughly as an invoice progresses: RECEIVED and VALIDATED are set by the
    deterministic pipeline; PENDING_APPROVAL is the resting state awaiting an agent
    decision; EXCEPTION_WORKFLOW, POSTED, REJECTED, and RETURNED_TO_VENDOR are the
    possible outcomes of that decision (EXCEPTION_WORKFLOW itself later resolves to
    POSTED or RETURNED_TO_VENDOR once a human acts on it).
    """

    RECEIVED = "received"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    EXCEPTION_WORKFLOW = "exception_workflow"
    POSTED = "posted"
    REJECTED = "rejected"
    RETURNED_TO_VENDOR = "returned_to_vendor"


class DecisionResult(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    agent_investigation_id: uuid.UUID
    agent_recommendation: str
    decision_status: DecisionStatus
    decision_reasoning: str
    policy_version: str


class ActionType(StrEnum):
    POST = "post"
    RETURN = "return"


class ExecutionResult(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    decision_id: uuid.UUID
    action: ActionType
    reason: str | None
    resulting_decision_status: DecisionStatus
    executed_at: datetime
