"""Per-registration functional audit through the real public MCP endpoint."""

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import anyio
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from blender_unified.audit_cases import BASE, CHECKS, COMMON, EXTRA, OVERRIDES


def decode(result):
    if result.structuredContent is not None:
        return result.structuredContent
    texts = [c.text for c in result.content if c.type == "text"]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except ValueError:
            return texts[0]
    return texts


def problem(result):
    data = decode(result)
    if result.isError:
        return str(data)[:1800]
    while isinstance(data, dict):
        if (
            data.get("status") == "error"
            or data.get("success") is False
            or data.get("error")
        ):
            return str(data)[:1800]
        if "result" not in data:
            break
        data = data["result"]
    if isinstance(data, str) and data.startswith(
        ("Error", "Failed", "Could not", "Rejected")
    ):
        return data[:1800]
    return None


def summary(result):
    data = decode(result)
    if isinstance(data, dict):
        return {
            k: v
            for k, v in data.items()
            if k not in ("base64", "image_data") and len(str(v)) < 1200
        }
    return str(data)[:1200]


def make_case(engine, name, schema, directory):
    required = schema.get("required", [])
    args = {k: COMMON[k] for k in required if k in COMMON}
    extra = EXTRA.get(name, "") if engine == "modeling" else ""
    check = CHECKS.get(name) if engine == "modeling" else None
    blocked = None
    if engine == "modeling":
        args.update(OVERRIDES.get(name, {}))
        if name.startswith("booltool_"):
            args.update(object_name="AuditMesh", target_name="AuditTarget")
        if name == "execute_blender_code":
            args["code"] = (
                "import bpy\nbpy.data.objects['AuditMesh']['audit_executed']=True\nprint('AUDIT_EXECUTED')"
            )
            check = "bpy.data.objects['AuditMesh'].get('audit_executed') is True"
        if name in (
            "render_image",
            "render_animation",
            "capture_viewport",
            "save_file",
            "open_file",
            "export_file",
            "import_file",
        ):
            suffix = (
                ".blend"
                if name in ("save_file", "open_file")
                else ".glb"
                if name in ("export_file", "import_file")
                else ".png"
            )
            path = directory / (name + suffix)
            if name in ("open_file", "import_file"):
                path = directory / ("base.blend" if name == "open_file" else "base.glb")
            args["filepath"] = str(path)
            if name in ("export_file", "import_file"):
                args["type"] = "GLTF"
            if name not in (
                "open_file",
                "import_file",
                "capture_viewport",
                "render_animation",
            ):
                check = f"os.path.isfile({str(path)!r}) and os.path.getsize({str(path)!r}) > 0"
        if name == "add_texture_node":
            args["image_path"] = str(directory / "texture.png")
    else:
        if name == "get_scene_info":
            pass
        elif name == "execute_blender_code":
            args["code"] = (
                "import bpy\nbpy.data.objects['AuditMesh']['audit_executed']=True\nresult={'executed':True}\nprint('AUDIT_EXECUTED')"
            )
            check = "bpy.data.objects['AuditMesh'].get('audit_executed') is True"
        elif name == "get_addon_status":
            pass
        elif name == "disable_telemetry":
            pass
        elif name == "record_trajectory_feedback":
            args["feedback"] = "accept"
            blocked = "Feedback persistence requires telemetry consent; audit keeps telemetry disabled. No feedback was persisted."
        elif name == "bpy_api_lookup":
            args["query"] = "bpy.types.Object"
        elif name == "describe_node_type":
            args["bl_idname"] = "ShaderNodeBsdfPrincipled"
        elif name == "get_viewport_screenshot":
            args["max_size"] = 128
        elif name == "export_scene":
            args.update(
                filepath=str(directory / "community.glb"),
                format="glb",
                object_names=["AuditMesh"],
            )
            check = f"os.path.getsize({args['filepath']!r}) > 0"
        elif name == "get_object_info":
            pass
        elif name in (
            "get_polyhaven_categories",
            "search_polyhaven_assets",
            "get_polyhaven_asset_preview",
            "download_polyhaven_asset",
            "set_texture",
        ):
            extra = "scene.blendermcp_use_polyhaven=True\n"
            if name in ("get_polyhaven_categories", "search_polyhaven_assets"):
                args["asset_type"] = "textures"
                if engine == "assets" and name == "search_polyhaven_assets":
                    args.update(query="wood", limit=2)
            elif name in ("get_polyhaven_asset_preview", "download_polyhaven_asset"):
                args["asset_id"] = "wood_floor"
                if name == "download_polyhaven_asset":
                    args.update(
                        asset_type="textures", resolution="1k", file_format="jpg"
                    )
                    check = "any('wood_floor' in m.name for m in bpy.data.materials) and any('wood_floor' in i.name and i.packed_file and i.packed_file.size > 0 for i in bpy.data.images)"
            else:
                args["texture_id"] = "audit_texture"
                extra += "img=bpy.data.images.load(os.path.join(AUDIT_DIR,'texture.png'),check_existing=False)\nimg.name='audit_texture_diffuse'\nimg['polyhaven_id']='audit_texture'\nimg['polyhaven_map']='Diffuse'\nimg['polyhaven_role']='base_color'\n"
                check = "any('audit_texture' in m.name and any(n.type=='TEX_IMAGE' and n.image is not None for n in m.node_tree.nodes) for m in bpy.data.objects['AuditMesh'].data.materials)"
        elif engine == "reference":
            if name.endswith("_for_cli"):
                args["blend_file"] = str(directory / "base.blend")
            if name == "execute_blender_code_for_cli":
                args["code"] = (
                    "import bpy\nresult={'object_exists':'AuditMesh' in bpy.data.objects}"
                )
            if name == "get_python_api_docs":
                args["identifier"] = "bpy.types.Object"
            if name.startswith("search_"):
                args.update(query="material", max_results=2)
            if name in ("get_object_detail_summary", "jump_to_view3d_object_by_name"):
                args["name"] = "AuditMesh"
            if name == "jump_to_view3d_object_data_by_name":
                args["name"] = "AuditMeshData"
            if name == "jump_to_tab_by_name":
                args["name"] = "Layout"
            if name == "jump_to_tab_by_space_type":
                args["space_type"] = "VIEW_3D"
            if name == "get_screenshot_of_area_as_image":
                args.update(area_ui_type="VIEW_3D", size_limit_in_bytes=1000000)
            if name == "get_screenshot_of_window_as_image":
                args["size_limit_in_bytes"] = 1000000
            if name.startswith("render_"):
                args["output_path"] = str(directory / (name + ".png"))
                check = f"os.path.isfile({args['output_path']!r}) and os.path.getsize({args['output_path']!r})>0"
        elif name.startswith("get_") and name.endswith("_status"):
            pass
        else:
            blocked = "External provider success path requires enabled integration and/or credentials and real asset/job IDs. No paid job or remote import was submitted."
    return args, extra, check, blocked


async def run(args):
    directory = (args.report.parent / ".runtime/tool-audit").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blender_version": None,
        "completed": False,
        "scope": "One positive-path case per registration where prerequisites are available; not every parameter combination.",
        "results": [],
        "system_tools": [],
    }

    def save():
        report["counts"] = dict(Counter(r["status"] for r in report["results"]))
        args.report.write_text(json.dumps(report, indent=2, default=str) + "\n")

    save()
    async with stdio_client(
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "blender_unified.server", "--config", str(args.config)],
        )
    ) as transport:
        async with ClientSession(*transport) as client:
            await client.initialize()
            inventory = json.loads(
                (await client.read_resource("blender-unified://inventory"))
                .contents[0]
                .text
            )
            report["expected_registrations"] = inventory["implementation_routes"]
            rows = [
                (t["name"], v) for t in inventory["tools"] for v in t["implementations"]
            ]
            # File loading goes last, because it changes Blender's scene lifecycle.
            rows.sort(
                key=lambda item: (
                    item[1]["tool_name"] == "open_file",
                    item[1]["engine"] != "modeling",
                    item[1]["tool_name"],
                    item[1]["engine"],
                )
            )
            if args.filter:
                rows = [
                    r for r in rows if r[1]["tool_name"] in args.filter.split(",")
                ]

            async def code(script):
                result = await client.call_tool(
                    "code.execute",
                    {"implementation": "reference", "code": "import bpy, os\n" + script},
                )
                error = problem(result)
                if error:
                    raise RuntimeError(error)
                return decode(result)

            async def reset(extra=""):
                return await code(
                    "AUDIT_DIR="
                    + repr(str(directory))
                    + "\n"
                    + BASE
                    + "\n"
                    + extra
                    + "\nresult={'ready':True,'blender':bpy.app.version_string}"
                )

            initial = await reset()
            report["blender_version"] = initial.get("result", initial)["blender"]
            await code(
                f"bpy.ops.wm.save_as_mainfile(filepath={str(directory / 'base.blend')!r})\nbpy.ops.export_scene.gltf(filepath={str(directory / 'base.glb')!r},export_format='GLB',use_selection=True)\nresult={{'saved':True}}"
            )
            for canonical, variant in rows:
                name = variant["tool_name"]
                engine = variant["engine"]
                row = {"engine": engine, "tool": name, "canonical": canonical}
                report["results"].append(row)
                start = time.monotonic()
                try:
                    params, extra, check, blocked = make_case(
                        engine, name, variant["inputSchema"], directory
                    )
                    row["arguments"] = params
                    if blocked:
                        row.update(status="blocked", reason=blocked, live_call=False)
                        continue
                    Draft202012Validator(variant["inputSchema"]).validate(params)
                    await reset(extra)
                    result = await client.call_tool(
                        canonical, params | {"implementation": engine}
                    )
                    row["live_call"] = True
                    error = problem(result)
                    if error:
                        row.update(status="failed", reason=error)
                        if "3D Print Toolbox extension is not enabled" in error:
                            row.update(status="blocked", reason=error)
                    else:
                        row["response"] = summary(result)
                        if engine == "reference" and name.startswith("render_"):
                            payload = decode(result)
                            output = payload.get("result", payload)["filepath"]
                            check = f"os.path.isfile({output!r}) and os.path.getsize({output!r}) > 0"
                        if check:
                            await code(
                                "import bpy,os\nassert "
                                + check
                                + ", 'Postcondition failed'\nresult={'verified':True}"
                            )
                            row["verification"] = (
                                "Blender state or output-file assertion"
                            )
                        else:
                            row["verification"] = (
                                "Valid live response; no independent state assertion"
                            )
                        if "screenshot" in name and "json" not in name:
                            assert any(c.type == "image" for c in result.content), (
                                "Expected native image content"
                            )
                        row["status"] = "passed"
                except Exception as exc:
                    row.update(
                        status="failed",
                        reason=f"{type(exc).__name__}: {str(exc)[:1800]}",
                    )
                finally:
                    row["seconds"] = round(time.monotonic() - start, 3)
                    save()
                    print(
                        f"[{len(report['results'])}/{len(rows)}] {engine}/{name}: {row['status']}",
                        flush=True,
                    )
            for name, params in [
                ("system.status", {}),
                ("system.find_tools", {"query": "mesh"}),
                ("system.describe_tool", {"name": "object.inspect"}),
            ]:
                result = await client.call_tool(name, params)
                report["system_tools"].append(
                    {"tool": name, "status": "failed" if problem(result) else "passed"}
                )
            report["completed"] = True
            report["completed_at"] = datetime.now(timezone.utc).isoformat()
            save()
            if report["counts"].get("failed", 0) or any(
                r["status"] == "failed" for r in report["system_tools"]
            ):
                raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--filter")
    anyio.run(run, p.parse_args())
