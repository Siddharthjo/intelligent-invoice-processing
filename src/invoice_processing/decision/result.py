import uuid
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
