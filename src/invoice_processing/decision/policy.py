from invoice_processing.agent.result import Recommendation
from invoice_processing.decision.result import DecisionStatus

POLICY_VERSION = "v1"

_RECOMMENDATION_TO_DECISION: dict[Recommendation, DecisionStatus] = {
    Recommendation.AUTO_APPROVE: DecisionStatus.POSTED,
    Recommendation.HUMAN_REVIEW: DecisionStatus.EXCEPTION_WORKFLOW,
    Recommendation.RETURN_TO_VENDOR: DecisionStatus.RETURNED_TO_VENDOR,
}


def decide(recommendation: Recommendation) -> DecisionStatus:
    return _RECOMMENDATION_TO_DECISION[recommendation]
