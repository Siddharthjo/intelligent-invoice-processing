import json
import logging
import time

from openai import APITimeoutError, OpenAI
from sqlalchemy.orm import Session

from invoice_processing.agent.client import get_openai_client
from invoice_processing.agent.prompts import SYSTEM_PROMPT
from invoice_processing.agent.result import AgentInvestigationResult, Recommendation, TerminationReason
from invoice_processing.agent.tools import (
    SUBMIT_RECOMMENDATION_TOOL_NAME,
    ToolContext,
    ToolPermission,
    dispatch_tool,
    get_allowed_tool_schemas,
)
from invoice_processing.config import get_settings
from invoice_processing.persistence.repository import StoredInvoice

logger = logging.getLogger(__name__)

_NO_PO_REFERENCE_CONCERN = "NO_PO_REFERENCE_FOUND"
_SUPPLIER_BLOCKED_CONCERN = "SUPPLIER_BLOCKED"
DEFAULT_ALLOWED_PERMISSIONS: frozenset[ToolPermission] = frozenset({ToolPermission.READ})


def _apply_policy_overrides(
    recommendation: Recommendation, reasoning_summary: str, concerns: list[str]
) -> tuple[Recommendation, str]:
    """Deterministic backstop for policies the model doesn't reliably self-enforce via prompting alone."""
    if _NO_PO_REFERENCE_CONCERN in concerns and recommendation == Recommendation.AUTO_APPROVE:
        overridden_reasoning = (
            f"{reasoning_summary} [Overridden to human_review: policy requires human review "
            "whenever no PO reference was found in the invoice text, regardless of the "
            "model's own recommendation.]"
        )
        return Recommendation.HUMAN_REVIEW, overridden_reasoning
    if _SUPPLIER_BLOCKED_CONCERN in concerns and recommendation in (
        Recommendation.AUTO_APPROVE,
        Recommendation.RETURN_TO_VENDOR,
    ):
        overridden_reasoning = (
            f"{reasoning_summary} [Overridden to human_review: policy requires human review "
            "whenever the supplier is blocked, regardless of the model's own recommendation -- "
            "a block is typically a compliance/legal hold, not a vendor-side invoice defect, "
            "so it shouldn't be resolved to auto_approve or return_to_vendor without a human "
            "look.]"
        )
        return Recommendation.HUMAN_REVIEW, overridden_reasoning
    return recommendation, reasoning_summary


def _build_user_message(stored: StoredInvoice, raw_text: str) -> str:
    invoice = stored.invoice
    payload = {
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor.name,
        "issue_date": invoice.issue_date.isoformat(),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "currency": invoice.currency,
        "subtotal": str(invoice.subtotal) if invoice.subtotal is not None else None,
        "tax_amount": str(invoice.tax_amount) if invoice.tax_amount is not None else None,
        "total_amount": str(invoice.total_amount),
        "line_items": [
            {
                "description": item.description,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "extended_price": str(item.extended_price),
            }
            for item in invoice.line_items
        ],
        "existing_validation_issues": [
            {
                "step": issue.step,
                "rule_code": issue.rule_code,
                "severity": issue.severity,
                "message": issue.message,
            }
            for issue in stored.validation_issues
        ],
        "raw_extracted_text": raw_text,
    }
    return json.dumps(payload, indent=2)


def _fallback_result(
    *,
    termination_reason: TerminationReason,
    reasoning_summary: str,
    concern: str,
    messages: list[dict],
    tool_call_count: int,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    step_timestamps_ms: list[int],
) -> AgentInvestigationResult:
    return AgentInvestigationResult(
        recommendation=Recommendation.HUMAN_REVIEW,
        reasoning_summary=reasoning_summary,
        concerns=[concern],
        trace=messages,
        tool_call_count=tool_call_count,
        model=model,
        prompt_tokens=prompt_tokens or None,
        completion_tokens=completion_tokens or None,
        termination_reason=termination_reason,
        latency_ms=latency_ms,
        step_timestamps_ms=step_timestamps_ms,
    )


def run_investigation(
    stored: StoredInvoice,
    raw_text: str,
    session: Session,
    *,
    client: OpenAI | None = None,
    allowed_permissions: frozenset[ToolPermission] = DEFAULT_ALLOWED_PERMISSIONS,
) -> AgentInvestigationResult:
    settings = get_settings()
    client = client or get_openai_client()
    context = ToolContext(session=session, invoice_id=stored.id, raw_text=raw_text)
    tool_schemas = get_allowed_tool_schemas(allowed_permissions)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(stored, raw_text)},
    ]

    tool_call_count = 0
    prompt_tokens = 0
    completion_tokens = 0
    step_timestamps_ms: list[int] = []
    started_at = time.monotonic()

    def elapsed_ms() -> int:
        return int((time.monotonic() - started_at) * 1000)

    for turn in range(settings.agent_max_tool_turns):
        try:
            response = client.chat.completions.create(
                model=settings.agent_model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                timeout=settings.agent_call_timeout_seconds,
            )
        except APITimeoutError as exc:
            logger.warning(
                "Investigation for invoice %s timed out on turn %d after %dms (limit %ss): %s",
                stored.id,
                turn + 1,
                elapsed_ms(),
                settings.agent_call_timeout_seconds,
                exc,
            )
            return _fallback_result(
                termination_reason=TerminationReason.TIMEOUT,
                reasoning_summary=(
                    f"OpenAI call timed out after {settings.agent_call_timeout_seconds}s on turn "
                    f"{turn + 1}; defaulting to human review."
                ),
                concern="AGENT_CALL_TIMEOUT",
                messages=messages,
                tool_call_count=tool_call_count,
                model=settings.agent_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=elapsed_ms(),
                step_timestamps_ms=step_timestamps_ms,
            )

        if response.usage is not None:
            prompt_tokens += response.usage.prompt_tokens
            completion_tokens += response.usage.completion_tokens

        choice = response.choices[0].message
        messages.append(choice.model_dump(exclude_none=True))

        if not choice.tool_calls:
            break

        for tool_call in choice.tool_calls:
            tool_call_count += 1
            arguments = json.loads(tool_call.function.arguments)

            if tool_call.function.name == SUBMIT_RECOMMENDATION_TOOL_NAME:
                concerns = arguments.get("concerns", [])
                recommendation, reasoning_summary = _apply_policy_overrides(
                    Recommendation(arguments["recommendation"]), arguments["reasoning"], concerns
                )
                latency_ms = elapsed_ms()
                logger.info(
                    "Investigation for invoice %s completed: recommendation=%s tool_calls=%d "
                    "latency_ms=%d",
                    stored.id,
                    recommendation.value,
                    tool_call_count,
                    latency_ms,
                )
                return AgentInvestigationResult(
                    recommendation=recommendation,
                    reasoning_summary=reasoning_summary,
                    concerns=concerns,
                    trace=messages,
                    tool_call_count=tool_call_count,
                    model=settings.agent_model,
                    prompt_tokens=prompt_tokens or None,
                    completion_tokens=completion_tokens or None,
                    termination_reason=TerminationReason.COMPLETED,
                    latency_ms=latency_ms,
                    step_timestamps_ms=step_timestamps_ms,
                )

            dispatch = dispatch_tool(tool_call.function.name, arguments, context, allowed_permissions)
            if not dispatch.permitted:
                logger.warning(
                    "Investigation for invoice %s attempted a disallowed tool call: '%s'",
                    stored.id,
                    tool_call.function.name,
                )
            step_timestamps_ms.append(int(time.time() * 1000))
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(dispatch.result)}
            )

    latency_ms = elapsed_ms()
    logger.warning(
        "Investigation for invoice %s hit the %d-turn cap without a recommendation (latency_ms=%d)",
        stored.id,
        settings.agent_max_tool_turns,
        latency_ms,
    )
    return _fallback_result(
        termination_reason=TerminationReason.MAX_TURNS_EXCEEDED,
        reasoning_summary=(
            f"Agent did not call submit_recommendation within {settings.agent_max_tool_turns} turns; "
            "defaulting to human review."
        ),
        concern="AGENT_MAX_TURNS_EXCEEDED",
        messages=messages,
        tool_call_count=tool_call_count,
        model=settings.agent_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        step_timestamps_ms=step_timestamps_ms,
    )
