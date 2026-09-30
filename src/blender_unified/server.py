"""Public stdio MCP endpoint and inventory CLI."""

import argparse
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import __version__
from .config import Config
from .gateway import Gateway


def system_tool(name, description, properties=None, required=None):
    return types.Tool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": properties or {},
            "required": required or [],
            "additionalProperties": False,
        },
        annotations=types.ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )


SYSTEM_TOOLS = [
    system_tool(
        "system.status",
        "Report engine discovery and tool counts. Does not verify Blender connectivity.",
    ),
    system_tool(
        "system.find_tools",
        "Find canonical tools by name or description.",
        {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        ["query"],
    ),
    system_tool(
        "system.describe_tool",
        "Get exact input/output schemas and source descriptions for every implementation of one tool.",
        {"name": {"type": "string"}},
        ["name"],
    ),
]


def create_server(gateway: Gateway):
    @asynccontextmanager
    async def lifespan(server):
        async with gateway.connect():
            yield gateway

    server = Server(
        "blender-unified",
        version=__version__,
        lifespan=lifespan,
        instructions=(
            "One consolidated Blender interface. Discover with system.find_tools and system.describe_tool. "
            "Tools use semantic category names. Each call uses one explicitly configured implementation; "
            "use its schema. All engines must target the intended scene. Never assume separate engines share "
            "a Blender instance. After a timeout inspect scene state before retrying. "
            "Upstream code execution has the privileges of Blender. Engine security properties differ."
        ),
    )

    @server.list_tools()
    async def list_tools():
        return SYSTEM_TOOLS + [
            gateway.catalog.definition(name) for name in sorted(gateway.catalog.actions)
        ]

    @server.call_tool()
    async def call_tool(name, arguments):
        if name == "system.status":
            return gateway.status()
        if name == "system.find_tools":
            terms = arguments["query"].casefold().split()
            found = []
            for action in sorted(gateway.catalog.actions):
                definition = gateway.catalog.definition(action)
                haystack = (action + " " + (definition.description or "")).casefold()
                if all(term in haystack for term in terms):
                    found.append(
                        {
                            "name": action,
                            "description": (definition.description or "").splitlines()[
                                0
                            ],
                            "default": gateway.catalog.ordered(action)[0].engine,
                        }
                    )
            return {"total": len(found), "tools": found[: arguments.get("limit", 20)]}
        if name == "system.describe_tool":
            action = arguments["name"]
            definition = gateway.catalog.definition(action)
            return {
                "tool": definition.model_dump(by_alias=True, exclude_none=True),
                "implementations": next(
                    item["implementations"]
                    for item in gateway.catalog.inventory()
                    if item["name"] == action
                ),
            }
        context = server.request_context
        token = context.meta.progressToken if context.meta else None

        async def progress(value, total=None, message=None):
            if token is not None:
                await context.session.send_progress_notification(
                    token, value, total, message
                )

        return await gateway.call(
            name, arguments, progress if token is not None else None, context
        )

    @server.list_resources()
    async def list_resources():
        return [
            types.Resource(
                uri="blender-unified://inventory",
                name="Unified capability inventory",
                mimeType="application/json",
            )
        ] + gateway.resources

    @server.list_resource_templates()
    async def list_resource_templates():
        return gateway.templates

    # Preserve binary/text content, per-item URIs, MIME types, and metadata.
    async def read_resource(request):
        return types.ServerResult(await gateway.read(request.params.uri))

    server.request_handlers[types.ReadResourceRequest] = read_resource

    @server.list_prompts()
    async def list_prompts():
        return [
            prompt.model_copy(update={"name": name})
            for name, (_, prompt) in sorted(gateway.prompts.items())
        ]

    @server.get_prompt()
    async def get_prompt(name, arguments):
        return await gateway.prompt(name, arguments)

    return server


async def run(config, inventory=False):
    gateway = Gateway(config)
    if inventory:
        async with gateway.connect():
            print(
                json.dumps(
                    {**gateway.status(), "tools": gateway.catalog.inventory()}, indent=2
                )
            )
        return
    server = create_server(gateway)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Discover live engine catalogs and print JSON; does not change Blender",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    anyio.run(run, Config.load(args.config), args.inventory)


if __name__ == "__main__":
    main()
