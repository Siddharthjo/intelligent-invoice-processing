from fastapi import APIRouter

from invoice_processing.analytics.service import get_exception_reasons, get_status_counts, get_usage_by_day
from invoice_processing.api.deps import RequireManager, SessionDep
from invoice_processing.api.schemas import (
    AnalyticsSummaryOut,
    DailyUsageOut,
    ExceptionReasonOut,
    StatusCountOut,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def summary(session: SessionDep, current_user: RequireManager) -> AnalyticsSummaryOut:
    return AnalyticsSummaryOut(
        status_counts=[StatusCountOut.from_result(r) for r in get_status_counts(session)],
        exception_reasons=[ExceptionReasonOut.from_result(r) for r in get_exception_reasons(session)],
        usage_by_day=[DailyUsageOut.from_result(r) for r in get_usage_by_day(session)],
    )
