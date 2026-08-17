import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.erp_mock.seed import seed_mock_erp_data


def test_upload_and_retrieve_invoice(clerk_client: TestClient, db_session: Session, tmp_path: Path):
    seed_mock_erp_data(db_session)
    invoice_number = f"INV-{uuid.uuid4().hex[:8]}"
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=invoice_number, vendor_name="Northwind Traders Ltd.")

    with open(pdf_path, "rb") as f:
        response = clerk_client.post("/invoices", files={"file": ("invoice.pdf", f, "application/pdf")})

    assert response.status_code == 201
    body = response.json()
    assert body["invoice_number"] == invoice_number
    assert body["status"] == "valid"
    assert body["source"] == "manual_upload"

    get_response = clerk_client.get(f"/invoices/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["invoice_number"] == invoice_number
    assert get_response.json()["source"] == "manual_upload"

    list_response = clerk_client.get("/invoices", params={"limit": 50})
    assert list_response.status_code == 200
    summaries = {item["id"]: item for item in list_response.json()}
    assert summaries[body["id"]]["source"] == "manual_upload"
    assert summaries[body["id"]]["invoice_number"] == invoice_number


def test_upload_rejects_non_pdf(clerk_client: TestClient, tmp_path: Path):
    text_path = tmp_path / "not_a_pdf.txt"
    text_path.write_text("hello")

    with open(text_path, "rb") as f:
        response = clerk_client.post("/invoices", files={"file": ("not_a_pdf.txt", f, "text/plain")})

    assert response.status_code == 400


def test_get_invoice_404_for_unknown_id(clerk_client: TestClient):
    response = clerk_client.get("/invoices/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_upload_requires_login(client: TestClient, tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")

    with open(pdf_path, "rb") as f:
        response = client.post("/invoices", files={"file": ("invoice.pdf", f, "application/pdf")})

    assert response.status_code == 401


def test_list_invoices_requires_login(client: TestClient):
    assert client.get("/invoices").status_code == 401
