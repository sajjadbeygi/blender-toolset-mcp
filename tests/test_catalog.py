import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from mcp import types

from blender_unified.catalog import Catalog


def tool(name="get_scene_info", schema=None):
    return types.Tool(
        name=name,
        inputSchema=schema
        or {"type": "object", "properties": {}, "additionalProperties": False},
    )


def test_consolidation_preserves_all_pinned_upstream_tools():
    inventory = json.loads((Path(__file__).parents[1] / "inventory.json").read_text())
    catalog = Catalog(["blend_ai", "secure", "lab", "community"], {})
    count = 0
    for action in inventory["tools"]:
        for variant in action["implementations"]:
            catalog.add(
                variant["engine"],
                tool(variant["upstream_tool"], variant["inputSchema"]),
            )
            count += 1
    assert count == 270
    assert len(catalog.actions) == 243
    assert not any(name.startswith("extension.") for name in catalog.actions)
    for name in catalog.actions:
        Draft202012Validator.check_schema(catalog.definition(name).inputSchema)


def test_explicit_variants_keep_different_required_arguments_and_defs():
    catalog = Catalog(["blend_ai", "secure"], {})
    catalog.add("blend_ai", tool())
    nested = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/Point"}},
        "$defs": {"Point": {"type": "integer", "minimum": 1}},
        "required": ["value"],
        "additionalProperties": False,
    }
    catalog.add("secure", tool(schema=nested))
    schema = catalog.definition("scene.inspect").inputSchema
    validate = Draft202012Validator(schema).validate
    validate({})
    validate({"implementation": "secure", "value": 2})
    for invalid in [
        {"value": 2},
        {"implementation": "secure"},
        {"implementation": "secure", "value": 0},
        {"implementation": "absent"},
    ]:
        with pytest.raises(ValidationError):
            validate(invalid)
    selected, params = catalog.resolve(
        "scene.inspect", {"implementation": "secure", "value": 3}
    )
    assert selected.engine == "secure"
    assert params == {"value": 3}
    assert "implementation" not in nested["properties"]


def test_routes_and_annotations_are_conservative():
    catalog = Catalog(["blend_ai", "secure"], {"scene.inspect": "secure"})
    readonly = tool().model_copy(
        update={
            "annotations": types.ToolAnnotations(
                readOnlyHint=True, destructiveHint=False
            )
        }
    )
    catalog.add("blend_ai", readonly)
    catalog.add("secure", tool())
    catalog.validate_routes()
    assert catalog.resolve("scene.inspect", {})[0].engine == "secure"
    assert catalog.definition("scene.inspect").annotations.readOnlyHint is False
    assert catalog.definition("scene.inspect").annotations.destructiveHint is True
    with pytest.raises(ValueError):
        catalog.add("secure", tool())
    catalog.routes["missing"] = "secure"
    with pytest.raises(ValueError):
        catalog.validate_routes()
