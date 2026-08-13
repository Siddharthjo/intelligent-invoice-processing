import json


def to_trace_steps(trace: list[dict]) -> list[dict]:
    """Project the raw OpenAI-format message trace into a UI-friendly list of investigation steps.

    Pairs each investigation tool call with its result and skips system/user messages and the
    terminal submit_recommendation call (that's surfaced separately as the top-level recommendation).
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
            steps.append(
                {
                    "step": len(steps) + 1,
                    "tool": name,
                    "arguments": arguments,
                    "result": tool_results_by_call_id.get(tool_call.get("id")),
                }
            )
    return steps
