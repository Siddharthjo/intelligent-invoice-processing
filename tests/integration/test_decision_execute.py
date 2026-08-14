from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from invoice_processing.decision.execute import (
    DecisionNotFoundError,
    DecisionNotInExceptionWorkflowError,
    execute_decision,
)
from invoice_processing.decision.result import ActionType, DecisionStatus
from invoice_processing.persistence.repository import InvoiceRepository


def test_execute_post_action_updates_decision_status(
    make_exception_workflow_invoice, db_session: Session, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    result = execute_decision(invoice_id, decision_id, ActionType.POST, None, db_session)

    assert result.resulting_decision_status == DecisionStatus.POSTED
    assert result.reason is None
    stored = InvoiceRepository(db_session).get(invoice_id)
    assert stored.decision_status == "posted"


def test_execute_return_action_records_reason(
    make_exception_workflow_invoice, db_session: Session, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    result = execute_decision(invoice_id, decision_id, ActionType.RETURN, "wrong amount", db_session)

    assert result.resulting_decision_status == DecisionStatus.RETURNED_TO_VENDOR
    assert result.reason == "wrong amount"
    stored = InvoiceRepository(db_session).get(invoice_id)
    assert stored.decision_status == "returned_to_vendor"


def test_execute_raises_when_decision_does_not_belong_to_invoice(
    make_exception_workflow_invoice, db_session: Session, tmp_path: Path
):
    invoice_id_1, decision_id_1 = make_exception_workflow_invoice(tmp_path)
    invoice_id_2, _ = make_exception_workflow_invoice(tmp_path)

    with pytest.raises(DecisionNotFoundError):
        execute_decision(invoice_id_2, decision_id_1, ActionType.POST, None, db_session)


def test_execute_raises_when_already_resolved(
    make_exception_workflow_invoice, db_session: Session, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)
    execute_decision(invoice_id, decision_id, ActionType.POST, None, db_session)

    with pytest.raises(DecisionNotInExceptionWorkflowError):
        execute_decision(invoice_id, decision_id, ActionType.POST, None, db_session)
