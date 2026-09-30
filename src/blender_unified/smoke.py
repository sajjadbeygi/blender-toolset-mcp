"""Exercise the complete MCP -> engine -> Blender path on a disposable scene."""

import argparse
import json
import sys
import traceback
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    checks = []
    try:
        async with stdio_client(
            StdioServerParameters(
                command=sys.executable,
                args=["-m", "blender_unified.server", "--config", str(args.config)],
            )
        ) as transport:
            async with ClientSession(*transport) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                assert len(tools) == 246, len(tools)
                checks.append("246 public tools discovered")

                async def call(name, parameters):
                    result = await client.call_tool(name, parameters)
                    assert not result.isError, (name, result.content)
                    text = "\n".join(c.text for c in result.content if c.type == "text")
                    assert not text.startswith("Error"), (name, text)
                    return result, text

                await call(
                    "object.create_object",
                    {"type": "CUBE", "name": "UnifiedSmokeCube", "location": [1, 2, 3]},
                )
                checks.append("create object via Blend AI")
                for engine in ("blend_ai", "community", "secure"):
                    _, text = await call(
                        "object.inspect",
                        {"object_name": "UnifiedSmokeCube", "implementation": engine},
                    )
                    assert "UnifiedSmokeCube" in text, (engine, text)
                    checks.append(f"same object inspected via {engine}")
                _, text = await call("scene.hierarchy", {})
                assert "UnifiedSmokeCube" in text, text
                checks.append("same scene inspected via Blender Lab")
                await call(
                    "transform.set_location",
                    {"object_name": "UnifiedSmokeCube", "location": [4, 5, 6]},
                )
                _, text = await call(
                    "code.execute",
                    {
                        "implementation": "lab",
                        "code": "import bpy\nresult = {'location': list(bpy.data.objects['UnifiedSmokeCube'].location)}",
                    },
                )
                assert "4.0" in text and "6.0" in text, text
                checks.append("transform via Blend AI verified via Lab code execution")
                _, text = await call("docs.lookup_api", {"query": "bpy.types.Object"})
                assert "Object" in text, text
                checks.append("live bpy lookup via community")
                _, text = await call("privacy.disable_telemetry", {})
                assert "OFF" in text, text[:200]
                checks.append("community telemetry opt-out control")
                _, text = await call(
                    "docs.search_api", {"query": "bpy.types.Object", "max_results": 2}
                )
                assert text, text
                checks.append("bundled API documentation search via Lab")
                screenshot, _ = await call(
                    "viewport.screenshot", {"implementation": "blend_ai"}
                )
                assert any(c.type == "image" for c in screenshot.content), [
                    c.type for c in screenshot.content
                ]
                checks.append("real viewport screenshot passed through gateway")
                resources = (await client.list_resources()).resources
                scene_uri = next(
                    r.uri
                    for r in resources
                    if "blend_ai" in str(r.uri) and "scene" in str(r.uri)
                )
                scene = await client.read_resource(scene_uri)
                assert "UnifiedSmokeCube" in scene.contents[0].text
                checks.append("live scene resource")
                prompts = (await client.list_prompts()).prompts
                assert prompts
                assert (await client.get_prompt(prompts[0].name)).messages
                checks.append("upstream workflow prompt")
                await call("object.delete_object", {"object_name": "UnifiedSmokeCube"})
                checks.append("temporary object deleted")
        args.report.write_text(
            json.dumps({"passed": True, "checks": checks}, indent=2) + "\n"
        )
    except BaseException:
        args.report.write_text(
            json.dumps(
                {"passed": False, "checks": checks, "error": traceback.format_exc()},
                indent=2,
            )
            + "\n"
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    anyio.run(run, parser.parse_args())
