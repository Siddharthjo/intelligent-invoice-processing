import base64
import logging
import sys
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from sqlalchemy.orm import Session

from invoice_processing.config import get_settings
from invoice_processing.domain.enums import IntakeSource
from invoice_processing.extraction.base import ExtractionError
from invoice_processing.parsing.mapper import MappingError
from invoice_processing.pipeline.process_invoice import process_invoice

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GmailNotConfiguredError(Exception):
    """Raised when Gmail intake is disabled or its OAuth credentials aren't fully set."""


@lru_cache
def get_gmail_client() -> Resource:
    settings = get_settings()
    if not settings.gmail_enabled:
        raise GmailNotConfiguredError("GMAIL_ENABLED is not true; Gmail intake is disabled.")
    if not (settings.gmail_client_id and settings.gmail_client_secret and settings.gmail_refresh_token):
        raise GmailNotConfiguredError(
            "GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET/GMAIL_REFRESH_TOKEN are not all set; "
            "Gmail intake is not configured. Run `poetry run gmail-authorize` to obtain "
            "a refresh token."
        )
    credentials = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        token_uri=_TOKEN_URI,
        scopes=GMAIL_SCOPES,
    )
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _effective_query() -> str:
    settings = get_settings()
    return (
        f"{settings.gmail_query} "
        f"-label:{settings.gmail_processed_label} -label:{settings.gmail_failed_label}"
    )


def list_candidate_messages(client: Resource) -> list[str]:
    """List message IDs matching the intake query, excluding already-labeled ones.

    Paginates -- a demo inbox that hasn't been polled in a while can plausibly have
    more than one page's worth of unlabeled matches.
    """
    message_ids: list[str] = []
    page_token: str | None = None
    while True:
        response = (
            client.users()
            .messages()
            .list(userId="me", q=_effective_query(), pageToken=page_token)
            .execute()
        )
        message_ids.extend(m["id"] for m in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return message_ids


def _iter_parts(payload: dict) -> Iterator[dict]:
    """Walk a (possibly nested multipart) Gmail message payload, yielding leaf parts."""
    parts = payload.get("parts")
    if not parts:
        yield payload
        return
    for part in parts:
        yield from _iter_parts(part)


def download_pdf_attachments(client: Resource, message_id: str) -> list[tuple[str, bytes]]:
    """Return (filename, bytes) for every genuine PDF attachment on a message.

    Filters on both filename and actual part mimeType -- the search query only
    matches on filename text, which isn't proof the attachment really is a PDF.
    Silently skips attachments over the configured upload size limit rather than
    failing the whole message over one oversized attachment.
    """
    settings = get_settings()
    message = client.users().messages().get(userId="me", id=message_id, format="full").execute()
    attachments: list[tuple[str, bytes]] = []
    for part in _iter_parts(message.get("payload", {})):
        filename = part.get("filename") or ""
        if not filename.lower().endswith(".pdf") or part.get("mimeType") != "application/pdf":
            continue
        attachment_id = part.get("body", {}).get("attachmentId")
        if attachment_id is None:
            continue
        attachment = (
            client.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        data = base64.urlsafe_b64decode(attachment["data"])
        if len(data) > settings.max_upload_size_bytes:
            logger.warning(
                "Skipping oversized attachment %r (%d bytes) on Gmail message %s",
                filename,
                len(data),
                message_id,
            )
            continue
        attachments.append((filename, data))
    return attachments


def _get_or_create_label_id(client: Resource, label_name: str) -> str:
    labels = client.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == label_name:
            return label["id"]
    created = (
        client.users()
        .labels()
        .create(
            userId="me",
            body={"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        )
        .execute()
    )
    return created["id"]


def _apply_label(client: Resource, message_id: str, label_id: str) -> None:
    client.users().messages().modify(userId="me", id=message_id, body={"addLabelIds": [label_id]}).execute()


@dataclass
class GmailPollResult:
    checked_messages: int
    processed_invoice_ids: list[uuid.UUID] = field(default_factory=list)
    failed_message_ids: list[str] = field(default_factory=list)


def poll_inbox(session: Session) -> GmailPollResult:
    """Find unlabeled candidate emails, run every PDF attachment through the exact same
    process_invoice() a manual upload uses, and label each message by outcome.

    Labeling (not read/unread) is what makes this idempotent: a message only gets
    re-considered on the next poll if it still lacks both the processed and failed
    labels. A message with multiple attachments where only some succeed is still
    labeled failed as a whole -- the invoices that did process are already persisted
    (that's not undone), but the message needs a human look, so "processed" would be
    the wrong signal.
    """
    client = get_gmail_client()
    settings = get_settings()
    processed_label_id = _get_or_create_label_id(client, settings.gmail_processed_label)
    failed_label_id = _get_or_create_label_id(client, settings.gmail_failed_label)

    message_ids = list_candidate_messages(client)
    result = GmailPollResult(checked_messages=len(message_ids))

    for message_id in message_ids:
        attachments = download_pdf_attachments(client, message_id)
        if not attachments:
            logger.warning("Gmail message %s matched the query but had no usable PDF attachment", message_id)
            _apply_label(client, message_id, failed_label_id)
            result.failed_message_ids.append(message_id)
            continue

        message_had_failure = False
        for filename, data in attachments:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(data)
                tmp.flush()
                try:
                    pipeline_result = process_invoice(
                        Path(tmp.name), session, source_filename=filename, source=IntakeSource.GMAIL
                    )
                    result.processed_invoice_ids.append(pipeline_result.invoice_id)
                except (ExtractionError, MappingError):
                    logger.exception(
                        "Failed to process Gmail attachment %r from message %s", filename, message_id
                    )
                    message_had_failure = True

        _apply_label(client, message_id, failed_label_id if message_had_failure else processed_label_id)
        if message_had_failure:
            result.failed_message_ids.append(message_id)

    return result


def authorize_cli() -> None:
    """One-time interactive OAuth bootstrap.

    Run locally (`poetry run gmail-authorize`): opens a browser for you to log into
    Google and grant access, then prints a refresh token to paste into .env as
    GMAIL_REFRESH_TOKEN. Requires GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET already set.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    settings = get_settings()
    if not (settings.gmail_client_id and settings.gmail_client_secret):
        print("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env before running this.", file=sys.stderr)
        raise SystemExit(1)

    client_config = {
        "installed": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=GMAIL_SCOPES)
    credentials = flow.run_local_server(port=0)
    print("\nAuthorization complete. Add this to your .env:\n")
    print(f"GMAIL_REFRESH_TOKEN={credentials.refresh_token}\n")
