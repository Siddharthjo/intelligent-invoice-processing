import uuid
from pathlib import Path

from fastapi.testclient import TestClient


def test_execute_post_via_api(manager_client: TestClient, make_exception_workflow_invoice, tmp_path: Path):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = manager_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resulting_decision_status"] == "posted"
    assert body["action"] == "post"


def test_execute_return_requires_reason(
    manager_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = manager_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "return"}
    )

    assert response.status_code == 422


def test_execute_return_with_reason_via_api(
    manager_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = manager_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute",
        json={"action": "return", "reason": "amount does not match PO"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resulting_decision_status"] == "returned_to_vendor"
    assert body["reason"] == "amount does not match PO"


def test_execute_unknown_decision_404s(
    manager_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, _ = make_exception_workflow_invoice(tmp_path)

    response = manager_client.post(
        f"/invoices/{invoice_id}/decisions/{uuid.uuid4()}/execute", json={"action": "post"}
    )
    assert response.status_code == 404


def test_execute_already_resolved_409s(
    manager_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)
    manager_client.post(f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"})

    response = manager_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )
    assert response.status_code == 409


def test_execute_requires_login(client: TestClient, make_exception_workflow_invoice, tmp_path: Path):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )
    assert response.status_code == 401


def test_execute_rejects_a_clerk_even_with_a_valid_exception_workflow_decision(
    clerk_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    """The core Part 2 guarantee: a clerk can't execute a decision even when every
    other precondition (login, real exception_workflow decision, valid action) is met --
    this is the backend gate the UI's button-hiding is not a substitute for."""
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = clerk_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )

    assert response.status_code == 403
