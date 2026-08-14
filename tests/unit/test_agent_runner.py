import json
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import httpx
from openai import APITimeoutError

from invoice_processing.agent.result import Recommendation, TerminationReason
from invoice_processing.agent.runner import run_investigation
from invoice_processing.config import Settings
from invoice_processing.domain.invoice import Invoice, Party
from invoice_processing.persistence.repository import StoredInvoice


def _stored_invoice() -> StoredInvoice:
    invoice = Invoice(
        invoice_number="INV-TEST-1",
        vendor=Party(name="Acme"),
        issue_date=date(2026, 1, 1),
        currency="USD",
        total_amount=Decimal("100.00"),
    )
    return StoredInvoice(
        id=uuid.uuid4(),
        invoice=invoice,
        source_filename="test.pdf",
        validation_issues=[],
        decision_status=None,
    )


class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, tool_calls: list[_FakeToolCall] | None = None) -> None:
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none: bool = True) -> dict:
        data: dict = {"role": "assistant"}
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in self.tool_calls
            ]
        return data


class _FakeUsage:
    def __init__(self, prompt_tokens: int = 10, completion_tokens: int = 5) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeResponse:
    def __init__(self, message: _FakeMessage, usage: _FakeUsage | None = None) -> None:
        self.choices = [Mock(message=message)]
        self.usage = usage or _FakeUsage()


class _FakeClient:
    """Minimal stand-in for openai.OpenAI exposing only client.chat.completions.create()."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.chat = Mock()
        self.chat.completions.create = Mock(side_effect=self._next)

    def _next(self, **kwargs):
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _submit_call(recommendation: str = "auto_approve", reasoning: str = "ok", concerns=None) -> _FakeToolCall:
    return _FakeToolCall(
        "call_submit",
        "submit_recommendation",
        json.dumps({"recommendation": recommendation, "reasoning": reasoning, "concerns": concerns or []}),
    )


def test_completes_normally_via_mock_client():
    stored = _stored_invoice()
    client = _FakeClient([_FakeResponse(_FakeMessage(tool_calls=[_submit_call()]))])

    result = run_investigation(stored, "raw text", session=None, client=client)

    assert result.recommendation == Recommendation.AUTO_APPROVE
    assert result.termination_reason == TerminationReason.COMPLETED
    assert result.tool_call_count == 1
    assert result.latency_ms >= 0


def test_hits_max_turns_and_falls_back_to_human_review(monkeypatch):
    fake_settings = Settings(
        agent_max_tool_turns=2, agent_model="test-model", agent_call_timeout_seconds=5.0
    )
    monkeypatch.setattr("invoice_processing.agent.runner.get_settings", lambda: fake_settings)

    stored = _stored_invoice()
    variance_call = _FakeToolCall(
        "call_variance", "calculate_variance", json.dumps({"invoice_amount": 100, "po_amount": 100})
    )
    client = _FakeClient(
        [
            _FakeResponse(_FakeMessage(tool_calls=[variance_call])),
            _FakeResponse(_FakeMessage(tool_calls=[variance_call])),
        ]
    )

    result = run_investigation(stored, "raw text", session=None, client=client)

    assert result.recommendation == Recommendation.HUMAN_REVIEW
    assert result.termination_reason == TerminationReason.MAX_TURNS_EXCEEDED
    assert "AGENT_MAX_TURNS_EXCEEDED" in result.concerns
    assert result.tool_call_count == 2


def test_openai_timeout_is_reported_distinctly(monkeypatch):
    fake_settings = Settings(
        agent_max_tool_turns=8, agent_model="test-model", agent_call_timeout_seconds=5.0
    )
    monkeypatch.setattr("invoice_processing.agent.runner.get_settings", lambda: fake_settings)

    stored = _stored_invoice()
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    client = _FakeClient([APITimeoutError(request=request)])

    result = run_investigation(stored, "raw text", session=None, client=client)

    assert result.recommendation == Recommendation.HUMAN_REVIEW
    assert result.termination_reason == TerminationReason.TIMEOUT
    assert "AGENT_CALL_TIMEOUT" in result.concerns
    assert result.tool_call_count == 0


def test_disallowed_tool_call_is_rejected_but_investigation_continues():
    stored = _stored_invoice()
    disallowed_call = _FakeToolCall("call_bad", "delete_invoice", json.dumps({}))
    client = _FakeClient(
        [
            _FakeResponse(_FakeMessage(tool_calls=[disallowed_call])),
            _FakeResponse(_FakeMessage(tool_calls=[_submit_call()])),
        ]
    )

    result = run_investigation(stored, "raw text", session=None, client=client)

    assert result.termination_reason == TerminationReason.COMPLETED
    assert result.tool_call_count == 2
    tool_messages = [m for m in result.trace if m.get("role") == "tool"]
    assert any("tool_not_permitted" in m["content"] for m in tool_messages)
