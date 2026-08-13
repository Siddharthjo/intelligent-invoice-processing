import json

from openai import OpenAI
from sqlalchemy.orm import Session

from invoice_processing.agent.client import get_openai_client
from invoice_processing.agent.prompts import SYSTEM_PROMPT
from invoice_processing.agent.result import AgentInvestigationResult, Recommendation
from invoice_processing.agent.tools import (
    SUBMIT_RECOMMENDATION_TOOL_NAME,
    TOOL_HANDLERS,
    TOOL_SCHEMAS,
    ToolContext,
)
from invoice_processing.config import get_settings
from invoice_processing.persistence.repository import StoredInvoice


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
            {"rule_code": issue.rule_code, "severity": issue.severity, "message": issue.message}
            for issue in stored.validation_issues
        ],
        "raw_extracted_text": raw_text,
    }
    return json.dumps(payload, indent=2)


def _fallback_to_human_review(
    messages: list[dict], tool_call_count: int, model: str, prompt_tokens: int, completion_tokens: int
) -> AgentInvestigationResult:
    return AgentInvestigationResult(
        recommendation=Recommendation.HUMAN_REVIEW,
        reasoning_summary=(
            "Agent did not call submit_recommendation before the investigation loop ended; "
            "defaulting to human review."
        ),
        concerns=["AGENT_DID_NOT_SUBMIT_RECOMMENDATION"],
        trace=messages,
        tool_call_count=tool_call_count,
        model=model,
        prompt_tokens=prompt_tokens or None,
        completion_tokens=completion_tokens or None,
    )


def run_investigation(
    stored: StoredInvoice, raw_text: str, session: Session, *, client: OpenAI | None = None
) -> AgentInvestigationResult:
    settings = get_settings()
    client = client or get_openai_client()
    context = ToolContext(session=session, invoice_id=stored.id)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(stored, raw_text)},
    ]

    tool_call_count = 0
    prompt_tokens = 0
    completion_tokens = 0

    for _ in range(settings.agent_max_tool_turns):
        response = client.chat.completions.create(
            model=settings.agent_model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
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
                return AgentInvestigationResult(
                    recommendation=Recommendation(arguments["recommendation"]),
                    reasoning_summary=arguments["reasoning"],
                    concerns=arguments.get("concerns", []),
                    trace=messages,
                    tool_call_count=tool_call_count,
                    model=settings.agent_model,
                    prompt_tokens=prompt_tokens or None,
                    completion_tokens=completion_tokens or None,
                )

            result = TOOL_HANDLERS[tool_call.function.name](arguments, context)
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)}
            )

    return _fallback_to_human_review(
        messages, tool_call_count, settings.agent_model, prompt_tokens, completion_tokens
    )
