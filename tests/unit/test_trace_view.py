from invoice_processing.agent.trace_view import to_trace_steps

TRACE = [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "invoice payload"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_supplier", "arguments": '{"name": "Acme"}'},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {
                    "name": "check_duplicate",
                    "arguments": '{"vendor": "Acme", "invoice_number": "INV-1"}',
                },
            },
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": '{"found": true, "supplier": {"name": "Acme", "status": "active"}}',
    },
    {
        "role": "tool",
        "tool_call_id": "call_2",
        "content": '{"is_duplicate": false, "matching_invoice_id": null}',
    },
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_3",
                "type": "function",
                "function": {
                    "name": "submit_recommendation",
                    "arguments": '{"recommendation": "auto_approve", "reasoning": "ok", "concerns": []}',
                },
            }
        ],
    },
]


def test_pairs_tool_calls_with_their_results_in_order():
    steps = to_trace_steps(TRACE)
    assert [s["tool"] for s in steps] == ["get_supplier", "check_duplicate"]
    assert steps[0]["step"] == 1
    assert steps[0]["arguments"] == {"name": "Acme"}
    assert steps[0]["result"] == {"found": True, "supplier": {"name": "Acme", "status": "active"}}
    assert steps[1]["result"] == {"is_duplicate": False, "matching_invoice_id": None}


def test_excludes_submit_recommendation():
    steps = to_trace_steps(TRACE)
    assert all(s["tool"] != "submit_recommendation" for s in steps)


def test_handles_malformed_tool_result_content_gracefully():
    trace = [
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "get_supplier", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "not valid json"},
    ]
    steps = to_trace_steps(trace)
    assert steps[0]["result"] == {"raw": "not valid json"}


def test_empty_trace_returns_no_steps():
    assert to_trace_steps([]) == []


def test_merges_step_timestamps_by_index():
    steps = to_trace_steps(TRACE, [1000, 2000])
    assert steps[0]["timestamp_ms"] == 1000
    assert steps[1]["timestamp_ms"] == 2000


def test_missing_timestamps_default_to_none():
    assert all(s["timestamp_ms"] is None for s in to_trace_steps(TRACE))


def test_shorter_timestamps_list_defaults_missing_entries_to_none():
    steps = to_trace_steps(TRACE, [1000])
    assert steps[0]["timestamp_ms"] == 1000
    assert steps[1]["timestamp_ms"] is None
