from fastapi import APIRouter, HTTPException, status

from invoice_processing.api.deps import SessionDep
from invoice_processing.api.schemas import GmailCheckResultOut
from invoice_processing.intake.gmail import GmailNotConfiguredError, poll_inbox

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.post("/check-now", response_model=GmailCheckResultOut)
async def check_now(session: SessionDep) -> GmailCheckResultOut:
    try:
        result = poll_inbox(session)
    except GmailNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return GmailCheckResultOut.from_result(result)
