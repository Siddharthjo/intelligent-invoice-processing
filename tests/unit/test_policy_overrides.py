from invoice_processing.agent.result import Recommendation
from invoice_processing.agent.runner import _apply_policy_overrides


def test_auto_approve_with_no_po_reference_is_overridden_to_human_review():
    recommendation, reasoning = _apply_policy_overrides(
        Recommendation.AUTO_APPROVE, "Looks fine.", ["NO_PO_REFERENCE_FOUND"]
    )
    assert recommendation == Recommendation.HUMAN_REVIEW
    assert "Overridden" in reasoning
    assert "Looks fine." in reasoning


def test_auto_approve_without_that_concern_is_left_alone():
    recommendation, reasoning = _apply_policy_overrides(Recommendation.AUTO_APPROVE, "Looks fine.", [])
    assert recommendation == Recommendation.AUTO_APPROVE
    assert reasoning == "Looks fine."


def test_human_review_with_no_po_reference_is_left_alone():
    recommendation, reasoning = _apply_policy_overrides(
        Recommendation.HUMAN_REVIEW, "Needs a look.", ["NO_PO_REFERENCE_FOUND"]
    )
    assert recommendation == Recommendation.HUMAN_REVIEW
    assert reasoning == "Needs a look."


def test_return_to_vendor_with_no_po_reference_is_left_alone():
    recommendation, reasoning = _apply_policy_overrides(
        Recommendation.RETURN_TO_VENDOR, "Duplicate.", ["NO_PO_REFERENCE_FOUND", "DUPLICATE_SUSPECTED"]
    )
    assert recommendation == Recommendation.RETURN_TO_VENDOR
    assert reasoning == "Duplicate."


def test_auto_approve_with_supplier_blocked_is_overridden_to_human_review():
    recommendation, reasoning = _apply_policy_overrides(
        Recommendation.AUTO_APPROVE, "Looks fine.", ["SUPPLIER_BLOCKED"]
    )
    assert recommendation == Recommendation.HUMAN_REVIEW
    assert "Overridden" in reasoning
    assert "Looks fine." in reasoning


def test_return_to_vendor_with_supplier_blocked_is_overridden_to_human_review():
    recommendation, reasoning = _apply_policy_overrides(
        Recommendation.RETURN_TO_VENDOR, "Send it back.", ["SUPPLIER_BLOCKED"]
    )
    assert recommendation == Recommendation.HUMAN_REVIEW
    assert "Overridden" in reasoning
    assert "Send it back." in reasoning


def test_human_review_with_supplier_blocked_is_left_alone():
    recommendation, reasoning = _apply_policy_overrides(
        Recommendation.HUMAN_REVIEW, "Needs a look.", ["SUPPLIER_BLOCKED"]
    )
    assert recommendation == Recommendation.HUMAN_REVIEW
    assert reasoning == "Needs a look."
