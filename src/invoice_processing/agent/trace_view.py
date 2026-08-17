import json


def to_trace_steps(trace: list[dict], step_timestamps_ms: list[int] | None = None) -> list[dict]:
    """Project the raw OpenAI-format message trace into a UI-friendly list of investigation steps.

    Pairs each investigation tool call with its result and skips system/user messages and the
    terminal submit_recommendation call (that's surfaced separately as the top-level recommendation).

    step_timestamps_ms, if given, is a parallel list of wall-clock epoch-ms captured at each real
    tool dispatch in agent/runner.py -- same order and count as the steps built here (both skip
    submit_recommendation identically), so index i lines up with step i. None/missing entries
    (e.g. investigations recorded before this was added) fall back to a null timestamp.
    """
    tool_results_by_call_id: dict[str, dict] = {}
    for message in trace:
        if message.get("role") == "tool" and message.get("tool_call_id"):
            try:
                tool_results_by_call_id[message["tool_call_id"]] = json.loads(message["content"])
            except (TypeError, json.JSONDecodeError):
                tool_results_by_call_id[message["tool_call_id"]] = {"raw": message.get("content")}

    steps: list[dict] = []
    for message in trace:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function", {})
            name = function.get("name")
            if name == "submit_recommendation":
                continue
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            index = len(steps)
            timestamp_ms = (
                step_timestamps_ms[index]
                if step_timestamps_ms is not None and index < len(step_timestamps_ms)
                else None
            )
            steps.append(
                {
                    "step": index + 1,
                    "tool": name,
                    "arguments": arguments,
                    "result": tool_results_by_call_id.get(tool_call.get("id")),
                    "timestamp_ms": timestamp_ms,
                }
            )
    return steps
