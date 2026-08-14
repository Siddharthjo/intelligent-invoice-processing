import uuid

from invoice_processing.agent.tools import (
    TOOL_REGISTRY,
    ToolContext,
    ToolPermission,
    dispatch_tool,
    get_allowed_tool_schemas,
)

_CONTEXT = ToolContext(session=None, invoice_id=uuid.uuid4(), raw_text="")


def test_all_registered_tools_are_read_only():
    assert TOOL_REGISTRY, "registry should not be empty"
    assert all(d.permission == ToolPermission.READ for d in TOOL_REGISTRY.values())


def test_allowed_schemas_include_registered_tools_plus_submit_recommendation():
    names = {s["function"]["name"] for s in get_allowed_tool_schemas(frozenset({ToolPermission.READ}))}
    assert names == set(TOOL_REGISTRY.keys()) | {"submit_recommendation"}


def test_allowed_schemas_exclude_tools_outside_the_permission_set():
    names = {s["function"]["name"] for s in get_allowed_tool_schemas(frozenset())}
    assert names == {"submit_recommendation"}
    assert "get_supplier" not in names


def test_dispatch_permits_a_registered_tool_within_the_allowed_set():
    dispatch = dispatch_tool(
        "calculate_variance",
        {"invoice_amount": 100, "po_amount": 100},
        _CONTEXT,
        frozenset({ToolPermission.READ}),
    )
    assert dispatch.permitted is True
    assert dispatch.result["within_tolerance"] is True


def test_dispatch_rejects_a_registered_tool_outside_the_allowed_set():
    dispatch = dispatch_tool(
        "get_supplier",
        {"name": "Acme"},
        _CONTEXT,
        frozenset(),  # nothing allowed, not even READ
    )
    assert dispatch.permitted is False
    assert dispatch.result["error"] == "tool_not_permitted"
    assert dispatch.result["tool"] == "get_supplier"


def test_dispatch_rejects_an_unregistered_tool_name():
    dispatch = dispatch_tool(
        "delete_invoice",
        {},
        _CONTEXT,
        frozenset({ToolPermission.READ, ToolPermission.WRITE}),
    )
    assert dispatch.permitted is False
    assert dispatch.result["error"] == "tool_not_permitted"
