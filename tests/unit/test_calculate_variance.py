import uuid

from invoice_processing.agent.tools import TOOL_HANDLERS, ToolContext

_CONTEXT = ToolContext(session=None, invoice_id=uuid.uuid4(), raw_text="")


def _variance(invoice_amount, po_amount) -> dict:
    return TOOL_HANDLERS["calculate_variance"](
        {"invoice_amount": invoice_amount, "po_amount": po_amount}, _CONTEXT
    )


def test_exact_match_has_zero_variance_and_is_within_tolerance():
    result = _variance(100.00, 100.00)
    assert float(result["absolute_variance"]) == 0.0
    assert result["within_tolerance"] is True


def test_variance_at_exactly_the_tolerance_boundary_is_within_tolerance():
    # default tolerance is 2%; 102.00 vs 100.00 is exactly 2% over.
    result = _variance(102.00, 100.00)
    assert result["within_tolerance"] is True


def test_variance_beyond_tolerance_is_flagged():
    result = _variance(110.00, 100.00)
    assert result["within_tolerance"] is False


def test_zero_po_amount_is_not_within_tolerance():
    result = _variance(50.00, 0)
    assert result["percentage_variance"] is None
    assert result["within_tolerance"] is False
