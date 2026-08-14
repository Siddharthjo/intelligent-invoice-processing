import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class DecisionStatus(StrEnum):
    AUTO_POSTED = "auto_posted"
    PENDING_REVIEW = "pending_review"
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
