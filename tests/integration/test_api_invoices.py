from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from invoice_processing.main import app
from tests.support import build_invoice_pdf


@pytest.fixture
def client(db_session: Session) -> TestClient:
    return TestClient(app)


def test_upload_and_retrieve_invoice(client: TestClient, tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number="INV-API-1")

    with open(pdf_path, "rb") as f:
        response = client.post("/invoices", files={"file": ("invoice.pdf", f, "application/pdf")})

    assert response.status_code == 201
    body = response.json()
    assert body["invoice_number"] == "INV-API-1"
    assert body["status"] == "valid"

    get_response = client.get(f"/invoices/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["invoice_number"] == "INV-API-1"


def test_upload_rejects_non_pdf(client: TestClient, tmp_path: Path):
    text_path = tmp_path / "not_a_pdf.txt"
    text_path.write_text("hello")

    with open(text_path, "rb") as f:
        response = client.post("/invoices", files={"file": ("not_a_pdf.txt", f, "text/plain")})

    assert response.status_code == 400


def test_get_invoice_404_for_unknown_id(client: TestClient):
    response = client.get("/invoices/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
