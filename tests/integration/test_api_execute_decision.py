import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from invoice_processing.main import app


@pytest.fixture
def client(db_session: Session) -> TestClient:
    return TestClient(app)


def test_execute_post_via_api(client: TestClient, make_pending_review_invoice, tmp_path: Path):
    invoice_id, decision_id = make_pending_review_invoice(tmp_path)

    response = client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resulting_decision_status"] == "auto_posted"
    assert body["action"] == "post"


def test_execute_return_requires_reason(client: TestClient, make_pending_review_invoice, tmp_path: Path):
    invoice_id, decision_id = make_pending_review_invoice(tmp_path)

    response = client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "return"}
    )

    assert response.status_code == 422


def test_execute_return_with_reason_via_api(client: TestClient, make_pending_review_invoice, tmp_path: Path):
    invoice_id, decision_id = make_pending_review_invoice(tmp_path)

    response = client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute",
        json={"action": "return", "reason": "amount does not match PO"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resulting_decision_status"] == "returned_to_vendor"
    assert body["reason"] == "amount does not match PO"


def test_execute_unknown_decision_404s(client: TestClient, make_pending_review_invoice, tmp_path: Path):
    invoice_id, _ = make_pending_review_invoice(tmp_path)

    response = client.post(
        f"/invoices/{invoice_id}/decisions/{uuid.uuid4()}/execute", json={"action": "post"}
    )
    assert response.status_code == 404


def test_execute_already_resolved_409s(client: TestClient, make_pending_review_invoice, tmp_path: Path):
    invoice_id, decision_id = make_pending_review_invoice(tmp_path)
    client.post(f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"})

    response = client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )
    assert response.status_code == 409
