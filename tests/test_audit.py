import pytest
from mcp.types import CallToolResult, TextContent

from blender_unified.audit import problem


@pytest.mark.parametrize(
    "payload",
    [
        {"result": "Error: rejected input"},
        {"status": "ok", "result": {"status": "error", "message": "failed"}},
        {"result": {"success": False}},
    ],
)
def test_nested_component_errors_do_not_pass_audit(payload):
    result = CallToolResult(content=[], structuredContent=payload)
    assert problem(result)


def test_successful_text_and_images_are_not_errors():
    result = CallToolResult(content=[TextContent(type="text", text="done")])
    assert problem(result) is None
