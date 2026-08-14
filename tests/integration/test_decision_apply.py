import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.agent.result import Recommendation, TerminationReason
from invoice_processing.decision.apply import apply_decision
from invoice_processing.decision.result import DecisionStatus
from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.persistence.orm_models import AgentInvestigationRecord
from invoice_processing.persistence.repository import InvoiceRepository
from invoice_processing.pipeline.process_invoice import process_invoice


def _make_investigation(session: Session, invoice_id: uuid.UUID, recommendation: Recommendation) -> uuid.UUID:
    investigation_id = uuid.uuid4()
    session.add(
        AgentInvestigationRecord(
            id=investigation_id,
            invoice_id=invoice_id,
            model="test-model",
            recommendation=recommendation,
            reasoning_summary="synthetic reasoning for test",
            concerns=[],
            trace=[],
            tool_call_count=0,
            prompt_tokens=None,
            completion_tokens=None,
            termination_reason=TerminationReason.COMPLETED,
            latency_ms=0,
        )
    )
    session.commit()
    return investigation_id


def test_apply_decision_persists_row_and_updates_invoice(db_session: Session, tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    result = process_invoice(pdf_path, db_session)

    investigation_id = _make_investigation(db_session, result.invoice_id, Recommendation.AUTO_APPROVE)
    decision = apply_decision(result.invoice_id, investigation_id, Recommendation.AUTO_APPROVE, db_session)

    assert decision.decision_status == DecisionStatus.POSTED
    assert decision.agent_investigation_id == investigation_id

    stored = InvoiceRepository(db_session).get(result.invoice_id)
    assert stored.decision_status == "posted"


def test_apply_decision_is_append_only_and_invoice_reflects_the_latest(db_session: Session, tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    result = process_invoice(pdf_path, db_session)

    investigation_1 = _make_investigation(db_session, result.invoice_id, Recommendation.HUMAN_REVIEW)
    apply_decision(result.invoice_id, investigation_1, Recommendation.HUMAN_REVIEW, db_session)

    investigation_2 = _make_investigation(db_session, result.invoice_id, Recommendation.AUTO_APPROVE)
    apply_decision(result.invoice_id, investigation_2, Recommendation.AUTO_APPROVE, db_session)

    stored = InvoiceRepository(db_session).get(result.invoice_id)
    assert stored.decision_status == "posted"

    latest = InvoiceRepository(db_session).get_latest_investigation_and_decision(result.invoice_id)
    assert latest is not None
    investigation, decision = latest
    assert investigation.id == investigation_2
    assert decision.decision == "posted"
