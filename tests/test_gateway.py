import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from blender_unified.config import Config, EngineConfig
from blender_unified.gateway import Gateway, pages, public_uri

FIXTURE = Path(__file__).with_name("fake_engine.py")


async def test_complete_stdio_protocol_roundtrip(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "engines": [
                    {
                        "name": "modeling",
                        "command": sys.executable,
                        "args": [str(FIXTURE)],
                    }
                ]
            }
        )
    )
    async with stdio_client(
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "blender_unified.server", "--config", str(config)],
        )
    ) as transport:
        async with ClientSession(*transport) as client:
            await client.initialize()
            tools = (await client.list_tools()).tools
            assert {t.name for t in tools} == {
                "system.status",
                "system.find_tools",
                "system.describe_tool",
                "scene.inspect",
                "extension.modeling.failure",
            }
            result = await client.call_tool("scene.inspect", {})
            assert not result.isError
            assert result.structuredContent == {"objects": ["Cube"]}
            assert result.meta == {"fixture": True}
            assert result.content[1].data == "aGVsbG8="
            assert str(result.content[2].uri) == public_uri(
                "modeling", "blender://scene"
            )
            assert (await client.call_tool("scene.inspect", {"wrong": 1})).isError
            assert (await client.call_tool("extension.modeling.failure", {})).isError
            status = await client.call_tool("system.status", {})
            assert status.structuredContent["implementation_routes"] == 2
            found = await client.call_tool("system.find_tools", {"query": "scene"})
            assert found.structuredContent["tools"][0]["name"] == "scene.inspect"
            desc = await client.call_tool(
                "system.describe_tool", {"name": "scene.inspect"}
            )
            assert (
                desc.structuredContent["implementations"][0]["tool_name"]
                == "get_scene_info"
            )
            resources = (await client.list_resources()).resources
            assert len(resources) == 2
            binary = await client.read_resource(resources[1].uri)
            assert binary.contents[0].blob == "aGVsbG8="
            assert binary.contents[0].meta == {"fixture": True}
            assert (
                "{name}"
                in (await client.list_resource_templates())
                .resourceTemplates[0]
                .uriTemplate
            )
            prompt = await client.get_prompt("workflow.inspect")
            assert "scene.inspect" in prompt.messages[0].content.text
            assert prompt.messages[1].content.text == "Use get_scene_info"
            inventory = await client.read_resource("blender-unified://inventory")
            assert json.loads(inventory.contents[0].text)["implementation_routes"] == 2


async def test_repeated_pagination_cursor_is_rejected():
    async def fetch(cursor=None):
        return SimpleNamespace(tools=[], nextCursor="repeat")

    with pytest.raises(ValueError, match="repeated"):
        await pages(fetch, "tools")


async def test_failed_mutation_never_retries_or_falls_back():
    gateway = Gateway(Config([], ["modeling", "authenticated"]))
    calls = []

    class Session:
        async def call_tool(self, name, args, **kwargs):
            calls.append(name)
            raise TimeoutError("already sent")

    for engine in ["modeling", "authenticated"]:
        gateway.sessions[engine] = Session()
        gateway.health[engine] = {}
        gateway.catalog.add(
            engine,
            types.Tool(name="execute_blender_code", inputSchema={"type": "object"}),
        )
    result = await gateway.call("code.execute", {})
    assert result.isError
    assert len(calls) == 1
    assert "may have started" in result.content[0].text


async def test_calls_to_different_engines_are_serialized():
    gateway = Gateway(Config([], ["modeling", "authenticated"]))
    active, maximum = 0, 0

    class Session:
        async def call_tool(self, name, args, **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            return types.CallToolResult(content=[])

    for engine in ["modeling", "authenticated"]:
        gateway.sessions[engine] = Session()
        gateway.catalog.add(
            engine, types.Tool(name="get_scene_info", inputSchema={"type": "object"})
        )
    await asyncio.gather(
        gateway.call("scene.inspect", {}),
        gateway.call("scene.inspect", {"implementation": "authenticated"}),
    )
    assert maximum == 1


async def test_required_missing_engine_fails_closed():
    gateway = Gateway(Config([EngineConfig("missing", "/nonexistent/blender-engine")]))
    with pytest.raises(RuntimeError, match="Required engine"):
        async with gateway.connect():
            pytest.fail("must not start")


async def test_optional_missing_engine_is_visible_but_has_no_tools():
    gateway = Gateway(
        Config([EngineConfig("missing", "/nonexistent/blender-engine", required=False)])
    )
    async with gateway.connect():
        assert gateway.status()["engines"]["missing"]["connected"] is False
        assert gateway.catalog.actions == {}


async def test_screenshot_json_becomes_native_image_without_losing_structured_data():
    gateway = Gateway(Config([], ["modeling"]))
    payload = {"base64": "aGVsbG8=", "width": 1, "height": 1, "format": "png"}

    class Session:
        async def call_tool(self, *args, **kwargs):
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(payload))],
                structuredContent=payload,
            )

    gateway.sessions["modeling"] = Session()
    gateway.catalog.add(
        "modeling",
        types.Tool(name="get_viewport_screenshot", inputSchema={"type": "object"}),
    )
    result = await gateway.call("viewport.screenshot", {})
    assert result.content[0].type == "image"
    assert result.content[0].data == payload["base64"]
    assert "base64" not in result.content[1].text
    assert result.structuredContent == payload


async def test_elicitation_forwards_user_answer_with_request_identity():
    gateway = Gateway(Config([], ["assets"]))
    forwarded = []
    answer = types.ElicitResult(action="decline")

    class Frontend:
        async def elicit(self, message, schema, related_request_id):
            forwarded.append((message, schema, related_request_id))
            return answer

    params = types.ElicitRequestFormParams(
        message="Confirm?", requestedSchema={"type": "object", "properties": {}}
    )

    class Session:
        async def call_tool(self, *args, **kwargs):
            response = await gateway.elicit(None, params)
            assert response is answer
            return types.CallToolResult(content=[])

    gateway.sessions["assets"] = Session()
    gateway.catalog.add(
        "assets", types.Tool(name="get_scene_info", inputSchema={"type": "object"})
    )
    await gateway.call(
        "scene.inspect",
        {},
        request_context=SimpleNamespace(session=Frontend(), request_id=42),
    )
    assert forwarded == [("Confirm?", params.requestedSchema, 42)]
    assert gateway.active_request is None
    assert (await gateway.elicit(None, params)).action == "cancel"
