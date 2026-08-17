import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from invoice_processing.agent.result import Recommendation, TerminationReason
from invoice_processing.auth.seed import seed_demo_users
from invoice_processing.decision.apply import apply_decision
from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.main import app
from invoice_processing.persistence.db import SessionLocal, engine
from invoice_processing.persistence.orm_models import AgentInvestigationRecord
from invoice_processing.pipeline.process_invoice import process_invoice


@pytest.fixture(scope="module")
def db_session() -> Generator[Session, None, None]:
    """A session against the real, Alembic-migrated dev/test database.

    Deliberately does NOT create/drop tables here: this fixture runs against
    a shared, persistent database (not an ephemeral per-test one), so schema
    management belongs to `alembic upgrade head`, not test setup/teardown.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001  (any connection failure means "skip")
        pytest.skip(f"Postgres is not reachable at the configured DATABASE_URL: {exc}")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    return TestClient(app)


@pytest.fixture
def clerk_client(client: TestClient, db_session: Session) -> TestClient:
    seed_demo_users(db_session)
    response = client.post("/auth/login", json={"username": "clerk", "password": "clerk-demo-pass"})
    assert response.status_code == 200
    return client


@pytest.fixture
def manager_client(client: TestClient, db_session: Session) -> TestClient:
    seed_demo_users(db_session)
    response = client.post("/auth/login", json={"username": "manager", "password": "manager-demo-pass"})
    assert response.status_code == 200
    return client


@pytest.fixture
def make_exception_workflow_invoice(db_session: Session):
    """Factory fixture: seeds an invoice with an exception_workflow decision, without a
    real agent call, so tests exercising decision execution don't need OPENAI_API_KEY."""

    def _make(tmp_path: Path) -> tuple[uuid.UUID, uuid.UUID]:
        pdf_path = tmp_path / f"invoice_{uuid.uuid4().hex[:8]}.pdf"
        build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
        invoice_id = process_invoice(pdf_path, db_session).invoice_id

        investigation_id = uuid.uuid4()
        db_session.add(
            AgentInvestigationRecord(
                id=investigation_id,
                invoice_id=invoice_id,
                model="test-model",
                recommendation=Recommendation.HUMAN_REVIEW,
                reasoning_summary="synthetic",
                concerns=[],
                trace=[],
                tool_call_count=0,
                prompt_tokens=None,
                completion_tokens=None,
                termination_reason=TerminationReason.COMPLETED,
                latency_ms=0,
            )
        )
        db_session.commit()

        decision = apply_decision(invoice_id, investigation_id, Recommendation.HUMAN_REVIEW, db_session)
        return invoice_id, decision.id

    return _make
