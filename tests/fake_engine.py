"""Real stdio MCP fixture, independent of Blender and external services."""

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

server = Server("test-engine")


async def list_tools(request):
    if request is not None and request.params and request.params.cursor:
        result = types.ListToolsResult(
            tools=[types.Tool(name="failure", inputSchema={"type": "object"})]
        )
    else:
        result = types.ListToolsResult(
            tools=[
                types.Tool(
                    name="get_scene_info",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                )
            ],
            nextCursor="page2",
        )
    return types.ServerResult(result)


server.request_handlers[types.ListToolsRequest] = list_tools


@server.call_tool()
async def call_tool(name, arguments):
    if name == "failure":
        return types.CallToolResult(
            isError=True,
            content=[types.TextContent(type="text", text="expected failure")],
        )
    return types.CallToolResult(
        content=[
            types.TextContent(type="text", text="scene"),
            types.ImageContent(type="image", mimeType="image/png", data="aGVsbG8="),
            types.ResourceLink(
                type="resource_link", uri="blender://scene", name="Scene"
            ),
        ],
        structuredContent={"objects": ["Cube"]},
        _meta={"fixture": True},
    )


@server.list_resources()
async def list_resources():
    return [types.Resource(uri="blender://scene", name="Scene")]


@server.list_resource_templates()
async def templates():
    return [
        types.ResourceTemplate(uriTemplate="blender://objects/{name}", name="Object")
    ]


async def read_resource(request):
    return types.ServerResult(
        types.ReadResourceResult(
            contents=[
                types.BlobResourceContents(
                    uri=request.params.uri,
                    mimeType="application/octet-stream",
                    blob="aGVsbG8=",
                    _meta={"fixture": True},
                )
            ]
        )
    )


server.request_handlers[types.ReadResourceRequest] = read_resource


@server.list_prompts()
async def list_prompts():
    return [types.Prompt(name="inspect", description="Inspect scene")]


@server.get_prompt()
async def get_prompt(name, arguments):
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text="Use get_scene_info"),
            )
        ]
    )


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
