import uuid

from invoice_processing.agent.tools import (
    TOOL_REGISTRY,
    ToolContext,
    ToolPermission,
    dispatch_tool,
    get_allowed_tool_schemas,
)

_CONTEXT = ToolContext(session=None, invoice_id=uuid.uuid4(), raw_text="")

_READ_TOOLS = {"get_supplier", "get_purchase_order", "check_duplicate", "calculate_variance"}
_WRITE_TOOLS = {"post_invoice", "return_to_vendor"}


def test_registry_has_the_expected_read_and_write_tools():
    assert TOOL_REGISTRY, "registry should not be empty"
    read_names = {name for name, d in TOOL_REGISTRY.items() if d.permission == ToolPermission.READ}
    write_names = {name for name, d in TOOL_REGISTRY.items() if d.permission == ToolPermission.WRITE}
    assert read_names == _READ_TOOLS
    assert write_names == _WRITE_TOOLS


def test_allowed_schemas_for_read_only_exclude_write_tools():
    names = {s["function"]["name"] for s in get_allowed_tool_schemas(frozenset({ToolPermission.READ}))}
    assert names == _READ_TOOLS | {"submit_recommendation"}
    assert not names & _WRITE_TOOLS


def test_allowed_schemas_for_write_only_exclude_read_tools():
    names = {s["function"]["name"] for s in get_allowed_tool_schemas(frozenset({ToolPermission.WRITE}))}
    assert names == _WRITE_TOOLS | {"submit_recommendation"}
    assert not names & _READ_TOOLS


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


def test_dispatch_rejects_write_tools_under_read_only_permissions():
    """The investigating agent's default permission set must never reach a write tool."""
    dispatch = dispatch_tool(
        "post_invoice",
        {"invoice_id": str(uuid.uuid4())},
        _CONTEXT,
        frozenset({ToolPermission.READ}),
    )
    assert dispatch.permitted is False
    assert dispatch.result["error"] == "tool_not_permitted"


def test_dispatch_rejects_read_tools_under_write_only_permissions():
    dispatch = dispatch_tool(
        "get_supplier",
        {"name": "Acme"},
        _CONTEXT,
        frozenset({ToolPermission.WRITE}),
    )
    assert dispatch.permitted is False
