import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import invoice_processing.api.routes.gmail as gmail_route
from invoice_processing.intake.gmail import GmailNotConfiguredError, GmailPollResult
from invoice_processing.main import app


@pytest.fixture
def client(db_session: Session) -> TestClient:
    return TestClient(app)


def test_check_now_returns_503_when_gmail_not_configured(client: TestClient, monkeypatch):
    def _raise(session):
        raise GmailNotConfiguredError("GMAIL_ENABLED is not true; Gmail intake is disabled.")

    monkeypatch.setattr(gmail_route, "poll_inbox", _raise)

    response = client.post("/gmail/check-now")

    assert response.status_code == 503
    assert "GMAIL_ENABLED" in response.json()["detail"]


def test_check_now_returns_poll_summary_on_success(client: TestClient, monkeypatch):
    invoice_id = uuid.uuid4()

    def _fake_poll(session):
        return GmailPollResult(
            checked_messages=3, processed_invoice_ids=[invoice_id], failed_message_ids=["m2"]
        )

    monkeypatch.setattr(gmail_route, "poll_inbox", _fake_poll)

    response = client.post("/gmail/check-now")

    assert response.status_code == 200
    body = response.json()
    assert body["checked_messages"] == 3
    assert body["processed_invoice_ids"] == [str(invoice_id)]
    assert body["failed_message_count"] == 1
