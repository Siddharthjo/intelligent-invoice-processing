from invoice_processing.agent.result import Recommendation
from invoice_processing.decision.policy import decide
from invoice_processing.decision.result import DecisionStatus


def test_auto_approve_maps_to_auto_posted():
    assert decide(Recommendation.AUTO_APPROVE) == DecisionStatus.AUTO_POSTED


def test_human_review_maps_to_pending_review():
    assert decide(Recommendation.HUMAN_REVIEW) == DecisionStatus.PENDING_REVIEW


def test_return_to_vendor_maps_to_returned_to_vendor():
    assert decide(Recommendation.RETURN_TO_VENDOR) == DecisionStatus.RETURNED_TO_VENDOR
