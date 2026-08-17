import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from invoice_processing.config import get_settings
from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.erp_mock.seed import seed_mock_erp_data


@pytest.fixture(scope="module", autouse=True)
def _skip_without_openai_key():
    if not get_settings().openai_api_key:
        pytest.skip("OPENAI_API_KEY is not set; skipping live agent investigation test.")


def test_investigate_endpoint_returns_trace_and_decision(
    clerk_client: TestClient, db_session: Session, tmp_path: Path
):
    seed_mock_erp_data(db_session)

    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(
        pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}", vendor_name="Northwind Traders Ltd."
    )

    with open(pdf_path, "rb") as f:
        upload_response = clerk_client.post(
            "/invoices", files={"file": ("invoice.pdf", f, "application/pdf")}
        )
    assert upload_response.status_code == 201
    invoice_id = upload_response.json()["id"]

    investigate_response = clerk_client.post(f"/invoices/{invoice_id}/investigate")
    assert investigate_response.status_code == 200
    body = investigate_response.json()

    assert body["invoice_id"] == invoice_id
    assert body["recommendation"] in {"auto_approve", "human_review", "return_to_vendor"}
    assert body["decision_status"] in {"posted", "exception_workflow", "returned_to_vendor"}
    assert isinstance(body["steps"], list)
    assert all(step["tool"] != "submit_recommendation" for step in body["steps"])

    # GET should return the same (latest) investigation without re-running the agent.
    get_response = clerk_client.get(f"/invoices/{invoice_id}/investigation")
    assert get_response.status_code == 200
    assert get_response.json()["agent_investigation_id"] == body["agent_investigation_id"]


def test_investigate_unknown_invoice_404s(clerk_client: TestClient):
    response = clerk_client.post(f"/invoices/{uuid.uuid4()}/investigate")
    assert response.status_code == 404


def test_get_investigation_404s_when_none_run_yet(
    clerk_client: TestClient, db_session: Session, tmp_path: Path
):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")

    with open(pdf_path, "rb") as f:
        upload_response = clerk_client.post(
            "/invoices", files={"file": ("invoice.pdf", f, "application/pdf")}
        )
    invoice_id = upload_response.json()["id"]

    response = clerk_client.get(f"/invoices/{invoice_id}/investigation")
    assert response.status_code == 404


def test_investigate_requires_login(client: TestClient):
    response = client.post(f"/invoices/{uuid.uuid4()}/investigate")
    assert response.status_code == 401
