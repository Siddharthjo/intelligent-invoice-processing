import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.agent.result import Recommendation, TerminationReason
from invoice_processing.analytics.service import get_exception_reasons, get_status_counts, get_usage_by_day
from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.persistence.orm_models import AgentInvestigationRecord, ValidationIssueRecord
from invoice_processing.pipeline.process_invoice import process_invoice

# This project's shared dev/test database accumulates rows across the whole test suite
# (see conftest.py's db_session docstring), so these tests can't assert exact totals --
# they assert that freshly-inserted, uniquely-identifiable data is present and correct
# within the aggregate, matching the pattern already used elsewhere in this suite
# (e.g. test_pipeline_postgres.py's random invoice numbers).


def test_get_status_counts_includes_a_freshly_processed_invoice(db_session: Session, tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    result = process_invoice(pdf_path, db_session)

    counts = get_status_counts(db_session)
    matching = [c for c in counts if c.decision_status == result.decision_status.value]
    assert matching, f"expected a status_counts entry for {result.decision_status.value}"
    assert matching[0].count >= 1


def test_get_exception_reasons_includes_a_uniquely_tagged_issue(db_session: Session, tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    result = process_invoice(pdf_path, db_session)

    unique_rule_code = f"TEST_MARKER_{uuid.uuid4().hex[:8]}"
    db_session.add(
        ValidationIssueRecord(
            invoice_id=result.invoice_id,
            step="TEST",
            rule_code=unique_rule_code,
            severity="warning",
            message="synthetic for analytics test",
        )
    )
    db_session.commit()

    reasons = get_exception_reasons(db_session, limit=10_000)
    matching = [r for r in reasons if r.rule_code == unique_rule_code]
    assert len(matching) == 1
    assert matching[0].step == "TEST"
    assert matching[0].count == 1


def test_get_usage_by_day_includes_a_fresh_investigation_and_computes_cost(
    db_session: Session, tmp_path: Path
):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    result = process_invoice(pdf_path, db_session)

    investigation = AgentInvestigationRecord(
        id=uuid.uuid4(),
        invoice_id=result.invoice_id,
        model="test-model",
        recommendation=Recommendation.AUTO_APPROVE,
        reasoning_summary="synthetic for analytics test",
        concerns=[],
        trace=[],
        tool_call_count=0,
        prompt_tokens=1000,
        completion_tokens=1000,
        termination_reason=TerminationReason.COMPLETED,
        latency_ms=0,
    )
    db_session.add(investigation)
    db_session.commit()
    db_session.refresh(investigation)
    # Derive the expected date from the row's own created_at (server-side, via
    # func.now()) rather than client-side "today" -- a naive local-vs-server
    # timezone mismatch would make this flaky right at day boundaries otherwise.
    expected_date = investigation.created_at.date().isoformat()

    days = get_usage_by_day(db_session)
    entry = next((d for d in days if d.date == expected_date), None)
    assert entry is not None, f"expected a usage_by_day entry for {expected_date}"
    assert entry.investigations >= 1
    assert entry.total_tokens >= 2000
    assert entry.estimated_cost_usd > Decimal("0")


def test_get_exception_reasons_respects_limit(db_session: Session):
    reasons = get_exception_reasons(db_session, limit=2)
    assert len(reasons) <= 2
