"""A deterministic, lossless mapping from component tools to semantic actions."""

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from importlib.resources import files

from jsonschema import Draft202012Validator
from mcp import types

ALIASES = json.loads(files("blender_unified").joinpath("names.json").read_text())


def canonical_name(engine: str, name: str) -> str:
    return ALIASES.get(engine, {}).get(name, f"extension.{engine}.{name}")


def relocate_refs(value, prefix):
    """Nested component schemas keep their own local $defs references."""
    if isinstance(value, dict):
        return {
            k: prefix + v[1:]
            if k == "$ref" and isinstance(v, str) and v.startswith("#/")
            else relocate_refs(v, prefix)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [relocate_refs(v, prefix) for v in value]
    return value


@dataclass
class Variant:
    engine: str
    tool: types.Tool


class Catalog:
    def __init__(self, priority: list[str], routes: dict[str, str]):
        self.priority = priority
        self.routes = routes
        self.actions: dict[str, list[Variant]] = {}

    def add(self, engine: str, tool: types.Tool):
        # Present one product identity while leaving source notices untouched.
        tool = tool.model_copy(deep=True)
        if tool.description:
            tool.description = re.sub(
                r"\b(?:blend-ai|Blend AI|Blender Lab|MCP for Blender|BlenderMCP|Blender-MCP|blender-mcp)\b",
                "Blender Toolset",
                tool.description,
            )
        name = canonical_name(engine, tool.name)
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", name) or name.startswith(
            "system."
        ):
            raise ValueError(f"Invalid or reserved canonical tool name: {name}")
        variants = self.actions.setdefault(name, [])
        if any(v.engine == engine for v in variants):
            raise ValueError(f"Ambiguous mapping: {engine}/{tool.name} -> {name}")
        if "implementation" in tool.inputSchema.get("properties", {}):
            raise ValueError(
                f"Reserved argument 'implementation': {engine}/{tool.name}"
            )
        Draft202012Validator.check_schema(tool.inputSchema)
        variants.append(Variant(engine, tool))

    def ordered(self, name: str) -> list[Variant]:
        def key(v):
            return (
                v.engine != self.routes.get(name),
                self.priority.index(v.engine)
                if v.engine in self.priority
                else len(self.priority),
                v.engine,
            )

        return sorted(self.actions[name], key=key)

    def validate_routes(self):
        for name, engine in self.routes.items():
            if name not in self.actions or not any(
                v.engine == engine for v in self.actions[name]
            ):
                raise ValueError(f"Configured route unavailable: {name} -> {engine}")

    def definition(self, name: str) -> types.Tool:
        variants = self.ordered(name)
        primary = variants[0]
        branches = []
        for index, v in enumerate(variants):
            schema = deepcopy(v.tool.inputSchema)
            schema.setdefault("properties", {})["implementation"] = {
                "type": "string",
                "const": v.engine,
                "description": "Select this engine explicitly; use its matching argument schema.",
            }
            if index:
                schema.setdefault("required", []).append("implementation")
            branches.append(relocate_refs(schema, f"#/anyOf/{index}"))
        # Do not assert a universal output schema across different implementations.
        # The selected component SDK validates its own structured result.
        description = primary.tool.description or name
        description += "\n\nDefault implementation: " + primary.engine + "."
        if len(variants) > 1:
            description += (
                " Alternatives: " + ", ".join(v.engine for v in variants[1:]) + "."
            )
            description += " Use implementation to select one; parameter and output shapes can differ."
        annotations = types.ToolAnnotations(
            readOnlyHint=all(
                v.tool.annotations is not None
                and v.tool.annotations.readOnlyHint is True
                for v in variants
            ),
            destructiveHint=any(
                v.tool.annotations is None
                or v.tool.annotations.destructiveHint is not False
                for v in variants
            ),
            idempotentHint=all(
                v.tool.annotations is not None
                and v.tool.annotations.idempotentHint is True
                for v in variants
            ),
            openWorldHint=any(
                v.tool.annotations is None
                or v.tool.annotations.openWorldHint is not False
                for v in variants
            ),
        )
        return types.Tool(
            name=name,
            description=description,
            inputSchema={"type": "object", "anyOf": branches},
            annotations=annotations,
        )

    def resolve(self, name: str, arguments: dict):
        variants = self.ordered(name)
        engine = arguments.get("implementation", variants[0].engine)
        variant = next((v for v in variants if v.engine == engine), None)
        if variant is None:
            raise ValueError(f"{name} has no implementation {engine!r}")
        params = {k: v for k, v in arguments.items() if k != "implementation"}
        # Validate against the original schema, too: no lost $refs or unknown
        # properties silently accepted by the consolidation layer.
        Draft202012Validator(variant.tool.inputSchema).validate(params)
        return variant, params

    def inventory(self):
        return [
            {
                "name": name,
                "default": self.ordered(name)[0].engine,
                "implementations": [
                    {
                        "engine": v.engine,
                        "tool_name": v.tool.name,
                        "inputSchema": v.tool.inputSchema,
                        "outputSchema": v.tool.outputSchema,
                        "description": v.tool.description,
                    }
                    for v in self.ordered(name)
                ],
            }
            for name in sorted(self.actions)
        ]
