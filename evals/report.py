import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from evals.runner import EvalCaseResult

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _total_tokens(result: EvalCaseResult) -> int | None:
    if result.prompt_tokens is None or result.completion_tokens is None:
        return None
    return result.prompt_tokens + result.completion_tokens


def print_report(results: list[EvalCaseResult], *, model: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    print(
        f"=== Agent Evaluation Report ===\n"
        f"Run at: {timestamp} | Model: {model} | Cases: {len(results)}\n"
    )

    header = (
        f"{'Case':<28} {'Category':<16} {'Expected':<17} {'Actual':<17} "
        f"{'Result':<10} {'Tools':<6} {'Tokens':<7}"
    )
    print(header)
    for result in results:
        actual = result.actual_recommendation.value if result.actual_recommendation else "—"
        tools = result.tool_call_count if result.tool_call_count is not None else "—"
        tokens = _total_tokens(result)
        print(
            f"{result.name:<28} {result.category:<16} {result.expected_recommendation.value:<17} "
            f"{actual:<17} {result.grade:<10} {str(tools):<6} {str(tokens if tokens is not None else '—'):<7}"
        )

    total = len(results)
    passed = sum(1 for r in results if r.grade == "PASS")
    safe = sum(1 for r in results if r.grade in {"PASS", "SOFT-FAIL"})
    tool_counts = [r.tool_call_count for r in results if r.tool_call_count is not None]
    token_totals = [t for r in results if (t := _total_tokens(r)) is not None]
    prompt_totals = [r.prompt_tokens for r in results if r.prompt_tokens is not None]
    completion_totals = [r.completion_tokens for r in results if r.completion_tokens is not None]
    overrides_fired = [r.name for r in results if r.override_fired]

    print("\n--- Summary ---")
    print(f"Strict accuracy:   {passed}/{total} ({100 * passed / total:.1f}%)")
    print(f"Safe-outcome rate: {safe}/{total} ({100 * safe / total:.1f}%)")
    if tool_counts:
        print(f"Avg tool calls: {sum(tool_counts) / len(tool_counts):.1f}")
    if token_totals:
        avg_prompt = sum(prompt_totals) / len(prompt_totals) if prompt_totals else 0
        avg_completion = sum(completion_totals) / len(completion_totals) if completion_totals else 0
        print(
            f"Avg tokens: {sum(token_totals) / len(token_totals):.1f} "
            f"(prompt: {avg_prompt:.1f}, completion: {avg_completion:.1f})"
        )
    overrides_suffix = f" ({', '.join(overrides_fired)})" if overrides_fired else ""
    print(f"Policy overrides fired: {len(overrides_fired)}{overrides_suffix}")

    failures = [r for r in results if r.grade != "PASS"]
    if failures:
        print("\n--- Failures & soft-fails (full reasoning shown) ---")
        for result in failures:
            actual = result.actual_recommendation.value if result.actual_recommendation else "ERROR"
            print(
                f"{result.name} [{result.grade}]: "
                f"expected {result.expected_recommendation.value}, got {actual}"
            )
            print(f"  reasoning: {result.reasoning_summary}")


def write_json_report(results: list[EvalCaseResult], *, model: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    path = RESULTS_DIR / f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}.json"

    def _serialize(result: EvalCaseResult) -> dict:
        data = asdict(result)
        data["expected_recommendation"] = result.expected_recommendation.value
        data["actual_recommendation"] = (
            result.actual_recommendation.value if result.actual_recommendation else None
        )
        data["expected_decision_status"] = result.expected_decision_status.value
        data["actual_decision_status"] = (
            result.actual_decision_status.value if result.actual_decision_status else None
        )
        return data

    total = len(results)
    passed = sum(1 for r in results if r.grade == "PASS")
    safe = sum(1 for r in results if r.grade in {"PASS", "SOFT-FAIL"})

    payload = {
        "run_at": timestamp.isoformat(),
        "model": model,
        "cases": len(results),
        "strict_accuracy": passed / total if total else None,
        "safe_outcome_rate": safe / total if total else None,
        "results": [_serialize(r) for r in results],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path
