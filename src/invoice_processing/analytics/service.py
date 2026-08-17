from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from invoice_processing.config import get_settings
from invoice_processing.persistence.orm_models import (
    AgentInvestigationRecord,
    InvoiceRecord,
    ValidationIssueRecord,
)


@dataclass
class StatusCount:
    decision_status: str | None
    count: int


@dataclass
class ExceptionReason:
    step: str
    rule_code: str
    count: int


@dataclass
class DailyUsage:
    date: str
    investigations: int
    total_tokens: int
    estimated_cost_usd: Decimal


def get_status_counts(session: Session) -> list[StatusCount]:
    status_col = InvoiceRecord.decision_status
    count_col = func.count().label("count")
    stmt = select(status_col, count_col).group_by(status_col).order_by(count_col.desc())
    return [
        StatusCount(decision_status=row.decision_status, count=row.count)
        for row in session.execute(stmt).all()
    ]


def get_exception_reasons(session: Session, *, limit: int = 20) -> list[ExceptionReason]:
    count_col = func.count().label("count")
    stmt = (
        select(ValidationIssueRecord.step, ValidationIssueRecord.rule_code, count_col)
        .group_by(ValidationIssueRecord.step, ValidationIssueRecord.rule_code)
        .order_by(count_col.desc())
        .limit(limit)
    )
    return [
        ExceptionReason(step=row.step, rule_code=row.rule_code, count=row.count)
        for row in session.execute(stmt).all()
    ]


def get_usage_by_day(session: Session, *, days: int = 30) -> list[DailyUsage]:
    settings = get_settings()
    day_col = func.date_trunc("day", AgentInvestigationRecord.created_at).label("day")
    stmt = (
        select(
            day_col,
            func.count().label("investigations"),
            func.coalesce(func.sum(AgentInvestigationRecord.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AgentInvestigationRecord.completion_tokens), 0).label(
                "completion_tokens"
            ),
        )
        .group_by(day_col)
        .order_by(day_col.desc())
        .limit(days)
    )
    results: list[DailyUsage] = []
    for row in session.execute(stmt).all():
        cost = (
            (Decimal(row.prompt_tokens) / 1000) * settings.agent_cost_per_1k_prompt_tokens
            + (Decimal(row.completion_tokens) / 1000) * settings.agent_cost_per_1k_completion_tokens
        )
        results.append(
            DailyUsage(
                date=row.day.date().isoformat(),
                investigations=row.investigations,
                total_tokens=row.prompt_tokens + row.completion_tokens,
                estimated_cost_usd=cost.quantize(Decimal("0.0001")),
            )
        )
    return results
