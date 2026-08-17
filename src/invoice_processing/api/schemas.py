from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from invoice_processing.agent.result import AgentInvestigationResult, Recommendation, TerminationReason
from invoice_processing.agent.trace_view import to_trace_steps
from invoice_processing.decision.result import ActionType, DecisionResult, DecisionStatus, ExecutionResult
from invoice_processing.domain.enums import IntakeSource, InvoiceStatus, UserRole
from invoice_processing.domain.invoice import Invoice
from invoice_processing.intake.gmail import GmailPollResult
from invoice_processing.persistence.orm_models import AgentInvestigationRecord, InvoiceDecisionRecord
from invoice_processing.persistence.repository import StatusHistoryEntry, StoredInvoice
from invoice_processing.pipeline.process_invoice import PipelineResult
from invoice_processing.validation.result import Severity, ValidationIssue


class LineItemOut(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    extended_price: Decimal


class ValidationIssueOut(BaseModel):
    step: str
    rule_code: str
    severity: Severity
    message: str


class StatusHistoryEntryOut(BaseModel):
    status: DecisionStatus
    reason: str | None
    created_at: datetime


class InvoiceOut(BaseModel):
    id: UUID
    invoice_number: str
    vendor_name: str
    bill_to_name: str | None
    po_number: str | None
    company_code: str | None
    issue_date: date
    due_date: date | None
    currency: str
    line_items: list[LineItemOut]
    subtotal: Decimal | None
    tax_amount: Decimal | None
    discount_amount: Decimal | None
    total_amount: Decimal
    status: InvoiceStatus
    decision_status: DecisionStatus | None
    source_filename: str | None
    source: IntakeSource
    validation_issues: list[ValidationIssueOut]
    status_history: list[StatusHistoryEntryOut]

    @classmethod
    def build(
        cls,
        *,
        id: UUID,
        invoice: Invoice,
        source_filename: str | None,
        source: str,
        validation_issues: list[ValidationIssue],
        decision_status: str | None = None,
        status_history: list[StatusHistoryEntry] | None = None,
    ) -> "InvoiceOut":
        return cls(
            id=id,
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor.name,
            bill_to_name=invoice.bill_to.name if invoice.bill_to else None,
            po_number=invoice.po_number,
            company_code=invoice.company_code,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            currency=invoice.currency,
            line_items=[LineItemOut(**item.model_dump()) for item in invoice.line_items],
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            discount_amount=invoice.discount_amount,
            total_amount=invoice.total_amount,
            status=invoice.status,
            decision_status=DecisionStatus(decision_status) if decision_status else None,
            source_filename=source_filename,
            source=IntakeSource(source),
            validation_issues=[ValidationIssueOut(**issue.model_dump()) for issue in validation_issues],
            status_history=[
                StatusHistoryEntryOut(
                    status=DecisionStatus(entry.status),
                    reason=entry.reason,
                    created_at=entry.created_at,
                )
                for entry in (status_history or [])
            ],
        )

    @classmethod
    def from_pipeline_result(cls, result: PipelineResult, *, source_filename: str) -> "InvoiceOut":
        return cls.build(
            id=result.invoice_id,
            invoice=result.invoice,
            source_filename=source_filename,
            source=result.source,
            validation_issues=result.validation_result.issues,
            decision_status=result.decision_status,
            status_history=result.status_history,
        )

    @classmethod
    def from_stored(cls, stored: StoredInvoice) -> "InvoiceOut":
        return cls.build(
            id=stored.id,
            invoice=stored.invoice,
            source_filename=stored.source_filename,
            source=stored.source,
            validation_issues=stored.validation_issues,
            decision_status=stored.decision_status,
            status_history=stored.status_history,
        )


class InvoiceSummaryOut(BaseModel):
    id: UUID
    invoice_number: str
    vendor_name: str
    issue_date: date
    currency: str
    total_amount: Decimal
    status: InvoiceStatus
    decision_status: DecisionStatus | None
    source: IntakeSource

    @classmethod
    def from_stored(cls, stored: StoredInvoice) -> "InvoiceSummaryOut":
        return cls(
            id=stored.id,
            invoice_number=stored.invoice.invoice_number,
            vendor_name=stored.invoice.vendor.name,
            issue_date=stored.invoice.issue_date,
            currency=stored.invoice.currency,
            total_amount=stored.invoice.total_amount,
            status=stored.invoice.status,
            decision_status=DecisionStatus(stored.decision_status) if stored.decision_status else None,
            source=IntakeSource(stored.source),
        )


class TraceStepOut(BaseModel):
    step: int
    tool: str
    arguments: dict
    result: dict | None
    timestamp_ms: int | None


class InvestigationOut(BaseModel):
    invoice_id: UUID
    agent_investigation_id: UUID
    model: str
    recommendation: Recommendation
    reasoning_summary: str
    concerns: list[str]
    tool_call_count: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    termination_reason: TerminationReason
    steps: list[TraceStepOut]
    decision_id: UUID
    decision_status: DecisionStatus
    decision_reasoning: str
    policy_version: str

    @classmethod
    def from_results(
        cls, invoice_id: UUID, investigation: AgentInvestigationResult, decision: DecisionResult
    ) -> "InvestigationOut":
        return cls(
            invoice_id=invoice_id,
            agent_investigation_id=investigation.id,
            model=investigation.model,
            recommendation=investigation.recommendation,
            reasoning_summary=investigation.reasoning_summary,
            concerns=investigation.concerns,
            tool_call_count=investigation.tool_call_count,
            prompt_tokens=investigation.prompt_tokens,
            completion_tokens=investigation.completion_tokens,
            total_tokens=_total_tokens(investigation.prompt_tokens, investigation.completion_tokens),
            latency_ms=investigation.latency_ms,
            termination_reason=investigation.termination_reason,
            steps=[
                TraceStepOut(**step)
                for step in to_trace_steps(investigation.trace, investigation.step_timestamps_ms)
            ],
            decision_id=decision.id,
            decision_status=decision.decision_status,
            decision_reasoning=decision.decision_reasoning,
            policy_version=decision.policy_version,
        )

    @classmethod
    def from_records(
        cls, invoice_id: UUID, investigation: AgentInvestigationRecord, decision: InvoiceDecisionRecord
    ) -> "InvestigationOut":
        return cls(
            invoice_id=invoice_id,
            agent_investigation_id=investigation.id,
            model=investigation.model,
            recommendation=Recommendation(investigation.recommendation),
            reasoning_summary=investigation.reasoning_summary,
            concerns=investigation.concerns,
            tool_call_count=investigation.tool_call_count,
            prompt_tokens=investigation.prompt_tokens,
            completion_tokens=investigation.completion_tokens,
            total_tokens=_total_tokens(investigation.prompt_tokens, investigation.completion_tokens),
            latency_ms=investigation.latency_ms,
            termination_reason=TerminationReason(investigation.termination_reason),
            steps=[
                TraceStepOut(**step)
                for step in to_trace_steps(investigation.trace, investigation.step_timestamps_ms)
            ],
            decision_id=decision.id,
            decision_status=DecisionStatus(decision.decision),
            decision_reasoning=decision.decision_reasoning,
            policy_version=decision.policy_version,
        )


def _total_tokens(prompt_tokens: int | None, completion_tokens: int | None) -> int | None:
    if prompt_tokens is None or completion_tokens is None:
        return None
    return prompt_tokens + completion_tokens


class ExecuteDecisionRequest(BaseModel):
    action: ActionType
    reason: str | None = None

    @model_validator(mode="after")
    def _require_reason_for_return(self) -> "ExecuteDecisionRequest":
        if self.action == ActionType.RETURN and not self.reason:
            raise ValueError("reason is required when action is 'return'.")
        return self


class DecisionExecutionOut(BaseModel):
    invoice_id: UUID
    decision_id: UUID
    action: ActionType
    reason: str | None
    resulting_decision_status: DecisionStatus
    executed_at: datetime

    @classmethod
    def from_result(cls, result: ExecutionResult) -> "DecisionExecutionOut":
        return cls(
            invoice_id=result.invoice_id,
            decision_id=result.decision_id,
            action=result.action,
            reason=result.reason,
            resulting_decision_status=result.resulting_decision_status,
            executed_at=result.executed_at,
        )


class GmailCheckResultOut(BaseModel):
    checked_messages: int
    processed_invoice_ids: list[UUID]
    failed_message_count: int

    @classmethod
    def from_result(cls, result: GmailPollResult) -> "GmailCheckResultOut":
        return cls(
            checked_messages=result.checked_messages,
            processed_invoice_ids=result.processed_invoice_ids,
            failed_message_count=len(result.failed_message_ids),
        )


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    role: UserRole
