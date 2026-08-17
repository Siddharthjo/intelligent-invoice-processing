import uuid
from pathlib import Path

from fastapi.testclient import TestClient


def test_execute_post_via_api(clerk_client: TestClient, make_exception_workflow_invoice, tmp_path: Path):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = clerk_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resulting_decision_status"] == "posted"
    assert body["action"] == "post"


def test_execute_return_requires_reason(
    clerk_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = clerk_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "return"}
    )

    assert response.status_code == 422


def test_execute_return_with_reason_via_api(
    clerk_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = clerk_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute",
        json={"action": "return", "reason": "amount does not match PO"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resulting_decision_status"] == "returned_to_vendor"
    assert body["reason"] == "amount does not match PO"


def test_execute_unknown_decision_404s(
    clerk_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, _ = make_exception_workflow_invoice(tmp_path)

    response = clerk_client.post(
        f"/invoices/{invoice_id}/decisions/{uuid.uuid4()}/execute", json={"action": "post"}
    )
    assert response.status_code == 404


def test_execute_already_resolved_409s(
    clerk_client: TestClient, make_exception_workflow_invoice, tmp_path: Path
):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)
    clerk_client.post(f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"})

    response = clerk_client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )
    assert response.status_code == 409


def test_execute_requires_login(client: TestClient, make_exception_workflow_invoice, tmp_path: Path):
    invoice_id, decision_id = make_exception_workflow_invoice(tmp_path)

    response = client.post(
        f"/invoices/{invoice_id}/decisions/{decision_id}/execute", json={"action": "post"}
    )
    assert response.status_code == 401
