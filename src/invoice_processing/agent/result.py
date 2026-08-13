import uuid
from enum import StrEnum

from pydantic import BaseModel


class Recommendation(StrEnum):
    AUTO_APPROVE = "auto_approve"
    HUMAN_REVIEW = "human_review"
    RETURN_TO_VENDOR = "return_to_vendor"


class AgentInvestigationResult(BaseModel):
    id: uuid.UUID | None = None
    recommendation: Recommendation
    reasoning_summary: str
    concerns: list[str]
    trace: list[dict]
    tool_call_count: int
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
