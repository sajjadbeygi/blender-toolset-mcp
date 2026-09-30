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


def test_consolidation_preserves_all_pinned_implementation_routes():
    inventory = json.loads((Path(__file__).parents[1] / "inventory.json").read_text())
    catalog = Catalog(["modeling", "authenticated", "reference", "assets"], {})
    count = 0
    for action in inventory["tools"]:
        for variant in action["implementations"]:
            catalog.add(
                variant["engine"],
                tool(variant["tool_name"], variant["inputSchema"]),
            )
            count += 1
    assert count == 270
    assert len(catalog.actions) == 243
    assert not any(name.startswith("extension.") for name in catalog.actions)
    for name in catalog.actions:
        Draft202012Validator.check_schema(catalog.definition(name).inputSchema)


def test_explicit_variants_keep_different_required_arguments_and_defs():
    catalog = Catalog(["modeling", "authenticated"], {})
    catalog.add("modeling", tool())
    nested = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/Point"}},
        "$defs": {"Point": {"type": "integer", "minimum": 1}},
        "required": ["value"],
        "additionalProperties": False,
    }
    catalog.add("authenticated", tool(schema=nested))
    schema = catalog.definition("scene.inspect").inputSchema
    validate = Draft202012Validator(schema).validate
    validate({})
    validate({"implementation": "authenticated", "value": 2})
    for invalid in [
        {"value": 2},
        {"implementation": "authenticated"},
        {"implementation": "authenticated", "value": 0},
        {"implementation": "absent"},
    ]:
        with pytest.raises(ValidationError):
            validate(invalid)
    selected, params = catalog.resolve(
        "scene.inspect", {"implementation": "authenticated", "value": 3}
    )
    assert selected.engine == "authenticated"
    assert params == {"value": 3}
    assert "implementation" not in nested["properties"]


def test_routes_and_annotations_are_conservative():
    catalog = Catalog(["modeling", "authenticated"], {"scene.inspect": "authenticated"})
    readonly = tool().model_copy(
        update={
            "annotations": types.ToolAnnotations(
                readOnlyHint=True, destructiveHint=False
            )
        }
    )
    catalog.add("modeling", readonly)
    catalog.add("authenticated", tool())
    catalog.validate_routes()
    assert catalog.resolve("scene.inspect", {})[0].engine == "authenticated"
    assert catalog.definition("scene.inspect").annotations.readOnlyHint is False
    assert catalog.definition("scene.inspect").annotations.destructiveHint is True
    with pytest.raises(ValueError):
        catalog.add("authenticated", tool())
    catalog.routes["missing"] = "authenticated"
    with pytest.raises(ValueError):
        catalog.validate_routes()
