import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from evals.cases import EVAL_CASES, EvalCase
from invoice_processing.agent.investigate import investigate_invoice
from invoice_processing.agent.result import Recommendation
from invoice_processing.decision.apply import apply_decision
from invoice_processing.decision.policy import decide
from invoice_processing.decision.result import DecisionStatus
from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.erp_mock.seed import seed_mock_erp_data
from invoice_processing.pipeline.process_invoice import process_invoice


@dataclass
class EvalCaseResult:
    name: str
    category: str
    expected_recommendation: Recommendation
    actual_recommendation: Recommendation | None
    expected_decision_status: DecisionStatus
    actual_decision_status: DecisionStatus | None
    grade: str
    tool_call_count: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    reasoning_summary: str
    concerns: list[str]
    override_fired: bool
    invoice_id: str | None


def _grade(expected: Recommendation, actual: Recommendation) -> str:
    if actual == expected:
        return "PASS"
    if actual == Recommendation.AUTO_APPROVE:
        return "FAIL"
    return "SOFT-FAIL"


def _run_case(case: EvalCase, session: Session) -> EvalCaseResult:
    invoice_number = f"EVAL-{case.name.upper()}-{uuid.uuid4().hex[:6]}"
    pdf_kwargs = {**case.pdf_kwargs, "invoice_number": invoice_number}

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(tmp_dir) / "invoice.pdf"
        build_invoice_pdf(pdf_path, **pdf_kwargs)

        if case.pre_process_duplicate:
            process_invoice(pdf_path, session)  # seed the duplicate target
        invoice_id = process_invoice(pdf_path, session).invoice_id

    try:
        investigation = investigate_invoice(invoice_id, session)
        decision = apply_decision(invoice_id, investigation.id, investigation.recommendation, session)
    except Exception as exc:  # noqa: BLE001  (any failure here is a graded eval outcome, not a crash)
        return EvalCaseResult(
            name=case.name,
            category=case.category,
            expected_recommendation=case.expected_recommendation,
            actual_recommendation=None,
            expected_decision_status=decide(case.expected_recommendation),
            actual_decision_status=None,
            grade="ERROR",
            tool_call_count=None,
            prompt_tokens=None,
            completion_tokens=None,
            reasoning_summary=f"{type(exc).__name__}: {exc}",
            concerns=[],
            override_fired=False,
            invoice_id=str(invoice_id),
        )

    return EvalCaseResult(
        name=case.name,
        category=case.category,
        expected_recommendation=case.expected_recommendation,
        actual_recommendation=investigation.recommendation,
        expected_decision_status=decide(case.expected_recommendation),
        actual_decision_status=decision.decision_status,
        grade=_grade(case.expected_recommendation, investigation.recommendation),
        tool_call_count=investigation.tool_call_count,
        prompt_tokens=investigation.prompt_tokens,
        completion_tokens=investigation.completion_tokens,
        reasoning_summary=investigation.reasoning_summary,
        concerns=investigation.concerns,
        override_fired="[Overridden" in investigation.reasoning_summary,
        invoice_id=str(invoice_id),
    )


def run_all_cases(session: Session, cases: list[EvalCase] | None = None) -> list[EvalCaseResult]:
    seed_mock_erp_data(session)
    return [_run_case(case, session) for case in (cases or EVAL_CASES)]
