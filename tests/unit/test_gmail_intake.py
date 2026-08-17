import base64
import uuid

import pytest

from invoice_processing.config import Settings
from invoice_processing.extraction.base import ExtractionError
from invoice_processing.intake import gmail
from invoice_processing.intake.gmail import (
    GmailNotConfiguredError,
    _effective_query,
    _iter_parts,
    download_pdf_attachments,
    get_gmail_client,
    list_candidate_messages,
    poll_inbox,
)

# --- Lightweight fake mirroring googleapiclient's fluent Resource API -----------------


class _FakeExecutable:
    def __init__(self, result: dict) -> None:
        self._result = result

    def execute(self) -> dict:
        return self._result


class _FakeAttachmentsResource:
    def __init__(self, client: "FakeGmailClient") -> None:
        self._client = client

    def get(self, userId: str, messageId: str, id: str) -> _FakeExecutable:  # noqa: A002
        return _FakeExecutable({"data": self._client.attachments_by_id[id]})


class _FakeMessagesResource:
    def __init__(self, client: "FakeGmailClient") -> None:
        self._client = client

    def list(self, userId: str, q: str, pageToken: str | None = None) -> _FakeExecutable:
        self._client.list_queries.append(q)
        page = self._client.pages.pop(0) if self._client.pages else {"messages": []}
        return _FakeExecutable(page)

    def get(self, userId: str, id: str, format: str) -> _FakeExecutable:  # noqa: A002
        return _FakeExecutable(self._client.messages_by_id[id])

    def attachments(self) -> _FakeAttachmentsResource:
        return _FakeAttachmentsResource(self._client)

    def modify(self, userId: str, id: str, body: dict) -> _FakeExecutable:  # noqa: A002
        self._client.modify_calls.append((id, tuple(body["addLabelIds"])))
        return _FakeExecutable({})


class _FakeLabelsResource:
    def __init__(self, client: "FakeGmailClient") -> None:
        self._client = client

    def list(self, userId: str) -> _FakeExecutable:
        return _FakeExecutable({"labels": self._client.labels})

    def create(self, userId: str, body: dict) -> _FakeExecutable:
        label = {"id": f"Label_{len(self._client.labels) + 1}", "name": body["name"]}
        self._client.labels.append(label)
        return _FakeExecutable(label)


class _FakeUsersResource:
    def __init__(self, client: "FakeGmailClient") -> None:
        self._client = client

    def messages(self) -> _FakeMessagesResource:
        return _FakeMessagesResource(self._client)

    def labels(self) -> _FakeLabelsResource:
        return _FakeLabelsResource(self._client)


class FakeGmailClient:
    def __init__(
        self,
        pages: list[dict] | None = None,
        messages_by_id: dict[str, dict] | None = None,
        attachments_by_id: dict[str, str] | None = None,
        labels: list[dict] | None = None,
    ) -> None:
        self.pages = list(pages or [])
        self.messages_by_id = messages_by_id or {}
        self.attachments_by_id = attachments_by_id or {}
        self.labels = labels if labels is not None else []
        self.list_queries: list[str] = []
        self.modify_calls: list[tuple[str, tuple[str, ...]]] = []

    def users(self) -> _FakeUsersResource:
        return _FakeUsersResource(self)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def _pdf_part(filename: str, attachment_id: str) -> dict:
    return {
        "filename": filename,
        "mimeType": "application/pdf",
        "body": {"attachmentId": attachment_id},
    }


# --- get_gmail_client configuration guard ---------------------------------------------


def test_get_gmail_client_raises_when_disabled(monkeypatch):
    get_gmail_client.cache_clear()
    settings = Settings(
        gmail_enabled=False, gmail_client_id="x", gmail_client_secret="y", gmail_refresh_token="z"
    )
    monkeypatch.setattr(gmail, "get_settings", lambda: settings)
    with pytest.raises(GmailNotConfiguredError, match="GMAIL_ENABLED"):
        get_gmail_client()
    get_gmail_client.cache_clear()


def test_get_gmail_client_raises_when_credentials_missing(monkeypatch):
    get_gmail_client.cache_clear()
    settings = Settings(
        gmail_enabled=True, gmail_client_id=None, gmail_client_secret=None, gmail_refresh_token=None
    )
    monkeypatch.setattr(gmail, "get_settings", lambda: settings)
    with pytest.raises(GmailNotConfiguredError, match="GMAIL_CLIENT_ID"):
        get_gmail_client()
    get_gmail_client.cache_clear()


# --- _effective_query -------------------------------------------------------------------


def test_effective_query_appends_label_exclusions(monkeypatch):
    settings = Settings(
        gmail_query="has:attachment filename:pdf",
        gmail_processed_label="done",
        gmail_failed_label="failed",
    )
    monkeypatch.setattr(gmail, "get_settings", lambda: settings)
    assert _effective_query() == "has:attachment filename:pdf -label:done -label:failed"


# --- _iter_parts (pure) -----------------------------------------------------------------


def test_iter_parts_yields_the_payload_itself_when_no_parts():
    payload = {"filename": "invoice.pdf", "mimeType": "application/pdf"}
    assert list(_iter_parts(payload)) == [payload]


def test_iter_parts_recurses_through_nested_multipart():
    leaf_a = {"filename": "", "mimeType": "text/plain"}
    leaf_b = {"filename": "invoice.pdf", "mimeType": "application/pdf"}
    payload = {
        "parts": [
            {"parts": [leaf_a]},  # nested multipart/alternative
            leaf_b,
        ]
    }
    assert list(_iter_parts(payload)) == [leaf_a, leaf_b]


# --- list_candidate_messages (pagination) ------------------------------------------------


def test_list_candidate_messages_paginates(monkeypatch):
    settings = Settings(gmail_query="q", gmail_processed_label="p", gmail_failed_label="f")
    monkeypatch.setattr(gmail, "get_settings", lambda: settings)
    client = FakeGmailClient(
        pages=[
            {"messages": [{"id": "m1"}], "nextPageToken": "tok"},
            {"messages": [{"id": "m2"}]},
        ]
    )
    assert list_candidate_messages(client) == ["m1", "m2"]
    assert len(client.list_queries) == 2


# --- download_pdf_attachments ------------------------------------------------------------


def test_download_pdf_attachments_filters_by_mimetype_and_extension(monkeypatch):
    settings = Settings(max_upload_size_bytes=20 * 1024 * 1024)
    monkeypatch.setattr(gmail, "get_settings", lambda: settings)
    pdf_bytes = b"%PDF-1.4 fake content"
    client = FakeGmailClient(
        messages_by_id={
            "m1": {
                "payload": {
                    "parts": [
                        {"filename": "notes.txt", "mimeType": "text/plain", "body": {}},
                        _pdf_part("invoice.pdf", "att1"),
                        # filename says pdf but mimeType doesn't -- must be excluded
                        {
                            "filename": "renamed.pdf",
                            "mimeType": "text/plain",
                            "body": {"attachmentId": "att2"},
                        },
                    ]
                }
            }
        },
        attachments_by_id={"att1": _b64(pdf_bytes)},
    )
    result = download_pdf_attachments(client, "m1")
    assert result == [("invoice.pdf", pdf_bytes)]


def test_download_pdf_attachments_skips_oversized_attachment(monkeypatch):
    settings = Settings(max_upload_size_bytes=10)
    monkeypatch.setattr(gmail, "get_settings", lambda: settings)
    client = FakeGmailClient(
        messages_by_id={"m1": {"payload": _pdf_part("big.pdf", "att1")}},
        attachments_by_id={"att1": _b64(b"way more than ten bytes of pdf content")},
    )
    assert download_pdf_attachments(client, "m1") == []


# --- poll_inbox orchestration --------------------------------------------------------------


def _stub_process_invoice_success(path, session, *, source_filename=None, source=None):
    from dataclasses import dataclass

    @dataclass
    class _Result:
        invoice_id: uuid.UUID

    return _Result(invoice_id=uuid.uuid4())


def _stub_process_invoice_failure(path, session, *, source_filename=None, source=None):
    raise ExtractionError("could not extract text")


def _settings_for_poll() -> Settings:
    return Settings(
        gmail_query="has:attachment filename:pdf",
        gmail_processed_label="invoice-processed",
        gmail_failed_label="invoice-intake-failed",
    )


def test_poll_inbox_labels_successful_message_as_processed(monkeypatch):
    pdf_bytes = b"%PDF-1.4 clean invoice"
    client = FakeGmailClient(
        pages=[{"messages": [{"id": "m1"}]}],
        messages_by_id={"m1": {"payload": _pdf_part("invoice.pdf", "att1")}},
        attachments_by_id={"att1": base64.urlsafe_b64encode(pdf_bytes).decode()},
    )
    calls = []

    def _capturing_stub(path, session, *, source_filename=None, source=None):
        calls.append(source)
        return _stub_process_invoice_success(path, session, source_filename=source_filename, source=source)

    monkeypatch.setattr(gmail, "get_settings", _settings_for_poll)
    monkeypatch.setattr(gmail, "get_gmail_client", lambda: client)
    monkeypatch.setattr(gmail, "process_invoice", _capturing_stub)

    result = poll_inbox(session=None)

    assert result.checked_messages == 1
    assert len(result.processed_invoice_ids) == 1
    assert result.failed_message_ids == []
    # Gmail intake must always tag persisted invoices with source=gmail, not the
    # process_invoice() default of manual_upload.
    assert calls == [gmail.IntakeSource.GMAIL]
    assert client.modify_calls == [("m1", ("Label_1",))]
    assert [label["name"] for label in client.labels] == ["invoice-processed", "invoice-intake-failed"]


def test_poll_inbox_labels_extraction_failure_as_failed(monkeypatch):
    pdf_bytes = b"%PDF-1.4 broken invoice"
    client = FakeGmailClient(
        pages=[{"messages": [{"id": "m1"}]}],
        messages_by_id={"m1": {"payload": _pdf_part("invoice.pdf", "att1")}},
        attachments_by_id={"att1": base64.urlsafe_b64encode(pdf_bytes).decode()},
    )
    monkeypatch.setattr(gmail, "get_settings", _settings_for_poll)
    monkeypatch.setattr(gmail, "get_gmail_client", lambda: client)
    monkeypatch.setattr(gmail, "process_invoice", _stub_process_invoice_failure)

    result = poll_inbox(session=None)

    assert result.processed_invoice_ids == []
    assert result.failed_message_ids == ["m1"]
    # The failed label was created second, so its id is Label_2.
    assert client.modify_calls == [("m1", ("Label_2",))]


def test_poll_inbox_labels_message_with_no_pdf_attachment_as_failed(monkeypatch):
    client = FakeGmailClient(
        pages=[{"messages": [{"id": "m1"}]}],
        messages_by_id={"m1": {"payload": {"filename": "", "mimeType": "text/plain", "body": {}}}},
    )
    monkeypatch.setattr(gmail, "get_settings", _settings_for_poll)
    monkeypatch.setattr(gmail, "get_gmail_client", lambda: client)

    result = poll_inbox(session=None)

    assert result.failed_message_ids == ["m1"]
    assert result.processed_invoice_ids == []


def test_poll_inbox_is_a_noop_over_zero_candidate_messages(monkeypatch):
    client = FakeGmailClient(pages=[{"messages": []}])
    monkeypatch.setattr(gmail, "get_settings", _settings_for_poll)
    monkeypatch.setattr(gmail, "get_gmail_client", lambda: client)

    result = poll_inbox(session=None)

    assert result.checked_messages == 0
    assert result.processed_invoice_ids == []
    assert result.failed_message_ids == []
    assert client.modify_calls == []
