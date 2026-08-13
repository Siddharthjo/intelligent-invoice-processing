import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, status

from invoice_processing.agent.client import AgentNotConfiguredError
from invoice_processing.agent.investigate import InvoiceNotFoundError, investigate_invoice
from invoice_processing.api.deps import SessionDep
from invoice_processing.api.schemas import InvestigationOut, InvoiceOut, InvoiceSummaryOut
from invoice_processing.config import get_settings
from invoice_processing.decision.apply import apply_decision
from invoice_processing.extraction.base import ExtractionError
from invoice_processing.parsing.mapper import MappingError
from invoice_processing.persistence.repository import InvoiceRepository
from invoice_processing.pipeline.process_invoice import process_invoice

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def upload_invoice(file: UploadFile, session: SessionDep) -> InvoiceOut:
    if file.content_type != "application/pdf":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only application/pdf uploads are supported.")

    settings = get_settings()

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_size_bytes:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Uploaded file is too large.")
            tmp.write(chunk)
        tmp.flush()

        try:
            result = process_invoice(Path(tmp.name), session, source_filename=file.filename)
        except (ExtractionError, MappingError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return InvoiceOut.from_pipeline_result(result, source_filename=file.filename or Path(tmp.name).name)


@router.get("/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(invoice_id: UUID, session: SessionDep) -> InvoiceOut:
    stored = InvoiceRepository(session).get(invoice_id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No invoice found with id '{invoice_id}'.")
    return InvoiceOut.from_stored(stored)


@router.get("", response_model=list[InvoiceSummaryOut])
async def list_invoices(session: SessionDep, limit: int = 50, offset: int = 0) -> list[InvoiceSummaryOut]:
    stored = InvoiceRepository(session).list(limit=limit, offset=offset)
    return [InvoiceSummaryOut.from_stored(item) for item in stored]


@router.post("/{invoice_id}/investigate", response_model=InvestigationOut)
async def investigate(invoice_id: UUID, session: SessionDep) -> InvestigationOut:
    try:
        investigation = investigate_invoice(invoice_id, session)
    except InvoiceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except AgentNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    decision = apply_decision(invoice_id, investigation.id, investigation.recommendation, session)
    return InvestigationOut.from_results(invoice_id, investigation, decision)


@router.get("/{invoice_id}/investigation", response_model=InvestigationOut)
async def get_latest_investigation(invoice_id: UUID, session: SessionDep) -> InvestigationOut:
    repository = InvoiceRepository(session)
    if repository.get(invoice_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No invoice found with id '{invoice_id}'.")

    latest = repository.get_latest_investigation_and_decision(invoice_id)
    if latest is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No investigation has been run yet for invoice '{invoice_id}'."
        )

    investigation, decision = latest
    return InvestigationOut.from_records(invoice_id, investigation, decision)
