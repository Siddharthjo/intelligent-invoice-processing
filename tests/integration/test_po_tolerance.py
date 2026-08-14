import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from invoice_processing.agent.tools import TOOL_HANDLERS, ToolContext
from invoice_processing.erp_mock.seed import seed_mock_erp_data


def test_same_percentage_variance_passes_for_services_but_fails_for_goods(db_session: Session):
    seed_mock_erp_data(db_session)
    context = ToolContext(session=db_session, invoice_id=uuid.uuid4(), raw_text="PO Number: PO-1001")

    # PO-1001 (Northwind, services, tolerance 5%, amount 2158.92): 3% over is within tolerance.
    services_result = TOOL_HANDLERS["calculate_variance"](
        {"invoice_amount": 2223.69, "po_number": "PO-1001"}, context
    )
    assert services_result["found"] is True
    assert services_result["po_type"] == "services"
    assert services_result["within_tolerance"] is True

    # PO-2002 (Southgate, goods, tolerance 2%, amount 1274.40): the *same* ~3% variance
    # fails -- proving tolerance is genuinely type-specific, not a flat rate.
    context_goods = ToolContext(session=db_session, invoice_id=uuid.uuid4(), raw_text="PO Number: PO-2002")
    goods_result = TOOL_HANDLERS["calculate_variance"](
        {"invoice_amount": 1312.63, "po_number": "PO-2002"}, context_goods
    )
    assert goods_result["found"] is True
    assert goods_result["po_type"] == "goods"
    assert goods_result["within_tolerance"] is False


def test_exact_match_is_within_tolerance_regardless_of_type(db_session: Session):
    seed_mock_erp_data(db_session)
    context = ToolContext(session=db_session, invoice_id=uuid.uuid4(), raw_text="PO Number: PO-3003")
    result = TOOL_HANDLERS["calculate_variance"](
        {"invoice_amount": 500.00, "po_number": "PO-3003"}, context
    )
    assert result["po_type"] == "indirect"
    assert Decimal(result["absolute_variance"]) == Decimal("0.00")
    assert result["within_tolerance"] is True


def test_calculate_variance_rejects_an_ungrounded_po_number(db_session: Session):
    seed_mock_erp_data(db_session)
    # PO-1001 genuinely exists, but this "invoice" never mentions it.
    context = ToolContext(session=db_session, invoice_id=uuid.uuid4(), raw_text="no PO reference here")
    result = TOOL_HANDLERS["calculate_variance"]({"invoice_amount": 100, "po_number": "PO-1001"}, context)
    assert result["found"] is False
    assert "rejected_reason" in result


def test_calculate_variance_reports_not_found_for_unknown_po(db_session: Session):
    seed_mock_erp_data(db_session)
    context = ToolContext(session=db_session, invoice_id=uuid.uuid4(), raw_text="PO Number: PO-9999")
    result = TOOL_HANDLERS["calculate_variance"](
        {"invoice_amount": 100, "po_number": "PO-9999"}, context
    )
    assert result == {"found": False}
